import copy
import hashlib
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from pathlib import Path
from threading import Barrier

import pytest
from django.core.files.base import ContentFile
from django.db import close_old_connections
from django.utils import timezone
from rest_framework.test import APIClient

from clients.models import Client
from documents.models import Document
from extraction.engine import BrokerMotorEngine, PageText
from extraction.models import ApprovedRevision, EngineResult, ExtractionJob, ReviewDraft
from extraction.tasks import process_document, recover_stale_jobs

def approval(api, document_id, version):
    review = api.get(f"/api/documents/{document_id}/review/").data
    draft = review.get("draft")
    return api.post(f"/api/documents/{document_id}/approve/", {
        "version": version, "warning_digest": draft["warning_digest"] if draft else "",
        "confirm_warnings": True, "note": "DANE TESTOWE: zweryfikowano źródło i kontrolowane braki.",
    }, format="json")


FIXTURES = Path(__file__).resolve().parents[2] / "fixtures" / "synthetic"


@pytest.fixture
def extraction_user(django_user_model):
    return django_user_model.objects.create_user(username="extraction-test", password=None)


@pytest.fixture
def extraction_api(extraction_user):
    api = APIClient()
    api.force_authenticate(extraction_user)
    return api


@pytest.fixture
def extraction_document(extraction_user, settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path
    client = Client.objects.create(kind="person", first_name="Alicja", last_name="DANE TESTOWE")
    payload = (FIXTURES / "application_text.pdf").read_bytes()
    return Document.objects.create(
        client=client, author=extraction_user, file=ContentFile(payload, name="synthetic.pdf"),
        original_name="DANE TESTOWE.pdf", mime_type="application/pdf", size=len(payload),
        checksum=hashlib.sha256(payload).hexdigest(), page_count=1,
    )


@pytest.fixture
def extraction_result(extraction_document, extraction_user):
    job = ExtractionJob.objects.create(document=extraction_document, requested_by=extraction_user)
    process_document(job.pk)
    job.refresh_from_db()
    assert job.status == "succeeded", job.error
    return job.result


@pytest.mark.django_db
def test_manual_correction_approval_export_and_reread_never_replace_snapshots(extraction_api, extraction_result, extraction_document, extraction_user):
    document_id = extraction_document.pk
    original = copy.deepcopy(extraction_result.fields)
    draft = ReviewDraft.objects.get(document=extraction_document)
    fields = copy.deepcopy(draft.fields)
    fields[0]["value"] = "000001-DANE TESTOWE"
    response = extraction_api.patch(f"/api/documents/{document_id}/review/", {"version": 1, "fields": fields}, format="json")
    assert response.status_code == 200, response.data
    assert response.data["version"] == 2
    changed = response.data["fields"][0]
    assert changed["manual"] and changed["page"] is None and changed["source"] == "" and changed["method"] == "manual"
    assert changed["origin"]["source"] and changed["updated_by"] == extraction_user.username
    extraction_result.refresh_from_db()
    assert extraction_result.fields == original
    assert extraction_api.patch(f"/api/documents/{document_id}/review/", {"version": 1, "fields": fields}, format="json").status_code == 409
    response = approval(extraction_api, document_id, 2)
    assert response.status_code == 201, response.data
    revision_id = response.data["id"]
    assert approval(extraction_api, document_id, 2).status_code == 409
    snapshot = ApprovedRevision.objects.get(pk=revision_id)
    assert snapshot.fields[0]["value"] == "000001-DANE TESTOWE"
    job = ExtractionJob.objects.create(document=extraction_document, requested_by=extraction_user)
    process_document(job.pk)
    process_document(job.pk)
    assert EngineResult.objects.filter(job=job).count() == 1
    draft.refresh_from_db()
    assert draft.version == 2 and draft.fields[0]["value"] == "000001-DANE TESTOWE"
    assert ApprovedRevision.objects.count() == 1
    exported = extraction_api.get(f"/api/revisions/{revision_id}/export/")
    assert exported.status_code == 200 and exported.content[:2] == b"PK"
    reset = extraction_api.post(f"/api/documents/{document_id}/review/reset/", {"version": 2}, format="json")
    assert reset.status_code == 200 and reset.data["version"] == 3
    snapshot.refresh_from_db()
    assert snapshot.fields[0]["value"] == "000001-DANE TESTOWE"
    assert approval(extraction_api, document_id, 3).status_code == 201
    assert ApprovedRevision.objects.count() == 2


@pytest.mark.django_db
def test_read_security_and_unapproved_export(extraction_document, extraction_result, extraction_api):
    anonymous = APIClient()
    for suffix in ["review/", "extract/", "approve/", "review/reset/"]:
        response = anonymous.get(f"/api/documents/{extraction_document.pk}/{suffix}") if suffix == "review/" else anonymous.post(f"/api/documents/{extraction_document.pk}/{suffix}", {})
        assert response.status_code == 403
    assert anonymous.get("/api/revisions/999/export/").status_code == 403
    assert extraction_api.get("/api/revisions/999/export/").status_code == 404
    assert extraction_api.get("/api/revisions/999/").status_code == 404


@pytest.mark.django_db
def test_field_identity_and_types_cannot_be_spoofed(extraction_document, extraction_result, extraction_api):
    fields = copy.deepcopy(extraction_result.fields)
    fields[0]["type"] = "decimal"
    url = f"/api/documents/{extraction_document.pk}/review/"
    assert extraction_api.patch(url, {"version": 1, "fields": fields}, format="json").status_code == 400
    fields = copy.deepcopy(extraction_result.fields)
    fields[0]["value"] = "niepusty"
    fields[0]["absent"] = True
    assert extraction_api.patch(url, {"version": 1, "fields": fields}, format="json").status_code == 400
    fields[0]["value"] = None
    saved = extraction_api.patch(url, {"version": 1, "fields": fields}, format="json")
    assert saved.status_code == 200 and saved.data["fields"][0]["absent"]


@pytest.mark.django_db
def test_immutable_models_reject_edits_and_deletes(extraction_result, extraction_document, extraction_api):
    approved = approval(extraction_api, extraction_document.pk, 1)
    revision = ApprovedRevision.objects.get(pk=approved.data["id"])
    for model in [extraction_result, revision]:
        with pytest.raises(ValueError, match="niezmienny"):
            model.save()
        with pytest.raises(ValueError, match="niezmienny"):
            type(model).objects.filter(pk=model.pk).update(fields=[])
        with pytest.raises(ValueError, match="niezmienny"):
            model.delete()


@pytest.mark.django_db
def test_controlled_retry_and_idempotent_queued_requests(extraction_document, extraction_api, monkeypatch, django_capture_on_commit_callbacks):
    dispatched = []
    monkeypatch.setattr("extraction.views.dispatch_job", lambda job_id: dispatched.append(job_id))
    with django_capture_on_commit_callbacks(execute=True):
        first = extraction_api.post(f"/api/documents/{extraction_document.pk}/extract/", {}, format="json")
        second = extraction_api.post(f"/api/documents/{extraction_document.pk}/extract/", {}, format="json")
    assert first.status_code == second.status_code == 202
    assert first.data["id"] == second.data["id"]
    assert len(dispatched) == 1


@pytest.mark.django_db
def test_worker_failure_recovery_has_expiring_lease_and_bounded_attempts(extraction_document, extraction_user, monkeypatch, django_capture_on_commit_callbacks):
    job = ExtractionJob.objects.create(document=extraction_document, requested_by=extraction_user,
        status="running", lease_until=timezone.now() - timedelta(seconds=1), attempts=1)
    dispatched = []
    monkeypatch.setattr("extraction.tasks.dispatch_job", lambda job_id: dispatched.append(job_id))
    with django_capture_on_commit_callbacks(execute=True):
        recover_stale_jobs()
    job.refresh_from_db()
    assert job.status == "queued" and dispatched == [job.pk]
    job.status = "running"
    job.attempts = 3
    job.lease_until = timezone.now() - timedelta(seconds=1)
    job.save()
    recover_stale_jobs()
    job.refresh_from_db()
    assert job.status == "failed" and job.finished_at


@pytest.mark.django_db
def test_unsupported_job_is_technical_success_without_approvable_draft(extraction_document, extraction_user, monkeypatch, extraction_api):
    monkeypatch.setattr("extraction.tasks.acquire_document", lambda _document: [PageText(1, "text", "DANE TESTOWE. Ubezpieczenie nieruchomości.")])
    job = ExtractionJob.objects.create(document=extraction_document, requested_by=extraction_user)
    process_document(job.pk)
    job.refresh_from_db()
    assert job.status == "succeeded" and job.result.profile is None
    assert not ReviewDraft.objects.filter(document=extraction_document).exists()
    assert approval(extraction_api, extraction_document.pk, 1).status_code == 404


@pytest.mark.django_db(transaction=True)
def test_two_simultaneous_approvals_create_only_one_revision(extraction_document, extraction_user):
    job = ExtractionJob.objects.create(document=extraction_document, requested_by=extraction_user, status="succeeded")
    result = EngineResult.objects.create(job=job, **BrokerMotorEngine().extract([PageText(1, "text", "DANE TESTOWE wniosek komunikacyjny\nNumer wniosku: 001")]))
    ReviewDraft.objects.create(document=extraction_document, engine_result=result, fields=result.fields)
    barrier = Barrier(2)
    def approve():
        close_old_connections()
        api = APIClient()
        api.force_authenticate(extraction_user)
        barrier.wait(timeout=5)
        try:
            return approval(api, extraction_document.pk, 1).status_code
        finally:
            close_old_connections()
    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(lambda _: approve(), range(2)))
    assert sorted(results) == [201, 409]
    assert ApprovedRevision.objects.filter(document=extraction_document).count() == 1


@pytest.mark.django_db(transaction=True)
def test_two_simultaneous_saves_keep_winner_and_report_conflict(extraction_document, extraction_user):
    job = ExtractionJob.objects.create(document=extraction_document, requested_by=extraction_user, status="succeeded")
    result = EngineResult.objects.create(job=job, **BrokerMotorEngine().extract([PageText(1, "text", "DANE TESTOWE wniosek komunikacyjny\nNumer wniosku: 001")]))
    ReviewDraft.objects.create(document=extraction_document, engine_result=result, fields=result.fields)
    barrier = Barrier(2)
    def save(number):
        close_old_connections()
        api = APIClient()
        api.force_authenticate(extraction_user)
        fields = copy.deepcopy(result.fields)
        fields[0]["value"] = f"DANE TESTOWE {number}"
        barrier.wait(timeout=5)
        try:
            response = api.patch(f"/api/documents/{extraction_document.pk}/review/", {"version": 1, "fields": fields}, format="json")
            return response.status_code, number
        finally:
            close_old_connections()
    with ThreadPoolExecutor(max_workers=2) as executor:
        outcomes = list(executor.map(save, range(2)))
    assert sorted(status for status, _number in outcomes) == [200, 409]
    winner = next(number for status, number in outcomes if status == 200)
    draft = ReviewDraft.objects.get(document=extraction_document)
    assert draft.version == 2
    assert draft.fields[0]["value"] == f"DANE TESTOWE {winner}"
