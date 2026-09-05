from concurrent.futures import ThreadPoolExecutor
from datetime import date
from email.message import EmailMessage
from pathlib import Path
from threading import Barrier
from unittest.mock import patch
import uuid

import pytest
from django.conf import settings
from django.db import close_old_connections
from django.utils import timezone
from rest_framework.test import APIClient
from accounts.models import User
from clients.models import Client
from common.api import Conflict
from common.models import AuditEvent
from correspondence.ingest import import_bytes
from correspondence.mime import MimeLimitError, parse_mail
from correspondence.models import Attachment, Mailbox, Message, ReadReceipt
from documents.models import Document
from policies.models import Policy, PolicyParticipant

pytestmark = pytest.mark.django_db


@pytest.fixture
def box():
    return Mailbox.objects.create(key="synthetic", kind="demo", state="demo", uidvalidity=1, boundary_uid=0, discovered_uid=0)


def raw_fixture(name="application"):
    return (Path(settings.ROOT_DIR) / f"fixtures/mail/{name}.eml").read_bytes()


def incoming(box, name="application", uid=1):
    obj = Message.objects.create(mailbox=box, folder="INBOX", uidvalidity=1, uid=uid)
    return import_bytes(obj.pk, raw_fixture(name), timezone.now())


def post(api, obj, endpoint, **data):
    return api.post(f"/api/messages/{obj.pk}/{endpoint}/", data, format="json")


def claim(api, obj):
    response = post(api, obj, "claim", version=obj.version)
    assert response.status_code == 200, response.data
    obj.refresh_from_db()
    return response


def test_personal_open_never_changes_work_or_version(api, user, box):
    obj = incoming(box)
    assert not api.get(f"/api/messages/{obj.pk}/").data["is_read"]
    api.get("/api/messages/")
    assert ReadReceipt.objects.count() == 0
    for _ in range(4):
        assert post(api, obj, "read").status_code == 200
    obj.refresh_from_db()
    assert obj.version == 1 and obj.status == "todo" and obj.owner is None
    assert ReadReceipt.objects.count() == 1
    assert api.get(f"/api/messages/{obj.pk}/").data["is_read"]
    other = User.objects.create_user(username="second")
    api.force_login(other)
    assert not api.get(f"/api/messages/{obj.pk}/").data["is_read"]
    assert AuditEvent.objects.filter(action__contains="read").count() == 0


def test_claim_work_permissions_versions_and_explicit_reopen(api, user, box):
    obj = incoming(box)
    assert post(api, obj, "work", version=1, note="Niedozwolona edycja").status_code == 403
    claim(api, obj)
    assert obj.owner_id == user.pk and obj.status == "in_progress"
    assert post(api, obj, "claim", version=1).status_code == 409
    assert post(api, obj, "work", version=2, status="waiting").status_code == 400
    assert post(api, obj, "work", version=2, status="waiting", note="Czekamy na zakres").status_code == 200
    assert post(api, obj, "work", version=3, note="").status_code == 400
    assert post(api, obj, "work", version=2, note="Stara wersja").status_code == 409
    assert post(api, obj, "work", version=3, status="done").status_code == 200
    obj.refresh_from_db()
    assert obj.completed_by_id == user.pk and obj.completed_at
    assert post(api, obj, "work", version=4, status="in_progress").status_code == 400
    assert post(api, obj, "work", version=4, action="reopen").status_code == 200
    obj.refresh_from_db()
    assert obj.completed_at is None and obj.status == "in_progress" and obj.owner_id == user.pk
    assert post(api, obj, "work", version=5, action="release").status_code == 200
    obj.refresh_from_db()
    assert obj.owner is None and obj.status == "todo"
    assert AuditEvent.objects.filter(object_id=obj.pk, object_type="message").count() == 6


def test_admin_transfer_requires_active_user_and_retains_history(api, user, box):
    obj = incoming(box)
    claim(api, obj)
    replacement = User.objects.create_user(username="replacement")
    assert post(api, obj, "work", version=2, action="assign", owner=replacement.pk).status_code == 403
    user.role = "ADMIN"
    user.save()
    api.force_login(user)
    replacement.is_active = False
    replacement.save()
    assert post(api, obj, "work", version=2, action="assign", owner=replacement.pk).status_code == 400
    replacement.is_active = True
    replacement.save()
    assert post(api, obj, "work", version=2, action="assign", owner=replacement.pk).status_code == 200
    replacement.is_active = False
    replacement.save()
    detail = api.get(f"/api/messages/{obj.pk}/").data
    assert detail["owner"]["is_active"] is False
    assert post(api, obj, "work", version=3, status="done").status_code == 400
    assert post(api, obj, "work", version=3, action="assign", owner=user.pk).status_code == 200


def test_new_reply_and_duplicate_message_ids_are_new_todo(api, box):
    old = incoming(box)
    claim(api, old)
    assert post(api, old, "work", version=2, status="done").status_code == 200
    repeated = incoming(box, uid=2)
    reply = incoming(box, "reply", uid=3)
    assert repeated.message_id == old.message_id and repeated.status == reply.status == "todo"
    old.refresh_from_db()
    assert old.status == "done"
    related = api.get(f"/api/messages/{reply.pk}/").data["related_messages"]
    assert {r["id"] for r in related} == {old.pk, repeated.pk}


def test_sender_candidates_never_link_or_create_clients(api, customer, box):
    customer.email = "wspolny@example.invalid"
    customer.save()
    other = Client.objects.create(kind="person", first_name="Inna", last_name="Testowa", email=customer.email)
    obj = incoming(box, "candidates")
    body = api.get(f"/api/messages/{obj.pk}/").data
    assert body["client"] is None and Client.objects.count() == 2
    assert {c["id"] for c in body["client_candidates"]} == {customer.pk, other.pk}
    unknown = incoming(box, "no-client", 2)
    assert api.get(f"/api/messages/{unknown.pk}/").data["client_candidates"] == []
    assert Client.objects.count() == 2


def test_filters_counts_pagination_include_entire_dataset(api, user, customer, box):
    Message.objects.bulk_create([Message(mailbox=box, folder="INBOX", uidvalidity=1, uid=n, subject="DANE TESTOWE wspólny", client=customer) for n in range(1, 28)])
    page = api.get("/api/messages/", {"client": customer.pk, "page": 2}).data
    assert page["count"] == page["counts"]["todo"] == 27 and len(page["results"]) == 7
    obj = Message.objects.first()
    claim(api, obj)
    assert api.get("/api/messages/", {"queue": "unassigned"}).data["count"] == 26
    assert api.get("/api/messages/", {"queue": "mine"}).data["count"] == 1
    assert api.get("/api/dashboard/").data["mail_action_count"] == 27
    assert api.get("/api/messages/", {"client": "bad"}).status_code == 400


@pytest.mark.django_db(transaction=True)
def test_private_files_csrf_blocked_download_and_no_public_urls(api, user, box):
    obj = incoming(box)
    attachment = obj.attachments.get()
    anon = APIClient()
    for url in [f"/api/messages/{obj.pk}/raw/", f"/api/mail-attachments/{attachment.pk}/download/"]:
        assert anon.get(url).status_code == 403
        response = api.get(url)
        assert response.status_code == 200 and "no-store" in response["Cache-Control"]
        assert response["Content-Disposition"].startswith("attachment;")
        response.close()
    secure = APIClient(enforce_csrf_checks=True)
    secure.force_login(user)
    assert post(secure, obj, "claim", version=1).status_code == 403
    blocked = incoming(box, "blocked", 2).attachments.first()
    assert api.get(f"/api/mail-attachments/{blocked.pk}/download/").status_code == 400
    serialized = api.get(f"/api/messages/{obj.pk}/").data
    assert "raw_file" not in serialized and "file" not in serialized["attachments"][0]


def test_attachment_promotion_idempotent_and_source_never_moves(api, user, customer, box):
    obj = incoming(box)
    claim(api, obj)
    attachment = obj.attachments.get()
    url = f"/api/mail-attachments/{attachment.pk}/promote/"
    request = {"version": 2, "client": customer.pk, "policy": None}
    response = api.post(url, request, format="json")
    assert response.status_code == 201, response.data
    document = Document.objects.get()
    assert document.mail_source.pk == attachment.pk and document.jobs.count() == 0
    assert api.post(url, request, format="json").data["document"]["id"] == document.pk
    assert Document.objects.count() == 1
    other = Client.objects.create(kind="person", first_name="Inny", last_name="DANE TESTOWE")
    assert post(api, obj, "work", version=3, client=other.pk, policy=None).status_code == 200
    document.refresh_from_db()
    assert document.client_id == customer.pk
    assert api.get(f"/api/documents/{document.pk}/").data["mail_source"]["message"] == obj.pk


def test_promotion_revalidates_upload_and_relations_and_cleans_rollback(api, user, customer, box):
    obj = incoming(box)
    claim(api, obj)
    attachment = obj.attachments.get()
    url = f"/api/mail-attachments/{attachment.pk}/promote/"
    policy = Policy.objects.create(insurer="TEST", number="TEST", insurance_type="TEST", start_date=date(2026, 1, 1), end_date=date(2027, 1, 1))
    payload = {"version": 2, "client": customer.pk, "policy": policy.pk}
    assert api.post(url, payload, format="json").status_code == 400
    PolicyParticipant.objects.create(policy=policy, client=customer, role="policyholder")
    before = set(Path(settings.MEDIA_ROOT).rglob("*"))
    with patch("correspondence.views.record", side_effect=RuntimeError("synthetic rollback")):
        with pytest.raises(RuntimeError):
            api.post(url, payload, format="json")
    assert Document.objects.count() == 0
    assert {p for p in Path(settings.MEDIA_ROOT).rglob("*") if p.is_file()} == {p for p in before if p.is_file()}
    attachment.refresh_from_db()
    assert attachment.document_id is None
    with attachment.file.open("wb") as handle:
        handle.write(b"DANE TESTOWE invalid PDF")
    assert api.post(url, payload, format="json").status_code == 400


def test_import_idempotence_and_file_cleanup(box):
    obj = incoming(box)
    existing = sorted(p for p in Path(settings.MEDIA_ROOT).rglob("*") if p.is_file())
    imported = import_bytes(obj.pk, raw_fixture(), timezone.now())
    assert imported.pk == obj.pk and Attachment.objects.count() == 1
    assert sorted(p for p in Path(settings.MEDIA_ROOT).rglob("*") if p.is_file()) == existing
    second = Message.objects.create(mailbox=box, folder="INBOX", uidvalidity=1, uid=2)
    with patch("correspondence.ingest.record", side_effect=RuntimeError("synthetic rollback")):
        with pytest.raises(RuntimeError):
            import_bytes(second.pk, raw_fixture(), timezone.now())
    assert sorted(p for p in Path(settings.MEDIA_ROOT).rglob("*") if p.is_file()) == existing
    second.refresh_from_db()
    assert not second.raw_file and Attachment.objects.count() == 1


def test_fenced_import_refuses_old_worker(box):
    box.kind = "imap"
    box.enabled = True
    box.lease_token = uuid.uuid4()
    box.lease_expires = timezone.now() + timezone.timedelta(minutes=1)
    box.save()
    obj = Message.objects.create(mailbox=box, folder="INBOX", uidvalidity=1, uid=1)
    with pytest.raises(Conflict):
        import_bytes(obj.pk, raw_fixture(), timezone.now(), token=uuid.uuid4())
    assert Attachment.objects.count() == 0
    import_bytes(obj.pk, raw_fixture(), timezone.now(), token=box.lease_token)
    assert Attachment.objects.count() == 1


@pytest.mark.parametrize("name", ["application", "no-client", "candidates", "newsletter", "html-only", "malformed", "blocked", "reply"])
def test_all_fixture_mime_sources_are_parsed_without_external_io(name):
    parsed = parse_mail(raw_fixture(name))
    assert "DANE TESTOWE" in parsed.subject
    if name == "html-only":
        assert "Zażółć" in parsed.body_text and "Drugi akapit" in parsed.body_text
        for hidden in ["alert", "tracker.example", "display:none", "<html>"]:
            assert hidden not in parsed.body_text
    if name == "malformed":
        assert parsed.declared_at is None and parsed.message_id == "" and parsed.warnings


def test_mime_size_count_depth_limits_and_nested_eml(settings, box):
    with pytest.raises(MimeLimitError):
        parse_mail(b"DANE TESTOWE without headers")
    settings.MAIL_MAX_RAW_BYTES = 100
    with pytest.raises(MimeLimitError):
        parse_mail(raw_fixture())
    settings.MAIL_MAX_RAW_BYTES = 30 * 1024 * 1024
    settings.MAIL_MAX_ATTACHMENT_BYTES = 1024
    obj = incoming(box, "oversized")
    assert obj.attachments.get().blocked_reason and not obj.attachments.get().file
    m = EmailMessage()
    m["Subject"] = "DANE TESTOWE"
    m.set_content("DANE TESTOWE")
    nested = EmailMessage()
    nested.set_content("DANE TESTOWE nie otwieraj")
    m.add_attachment(nested, filename="inside.eml")
    assert parse_mail(m.as_bytes()).attachments[0].blocked_reason
    settings.MAIL_MAX_PARTS = 1
    assert "limit" in parse_mail(m.as_bytes()).attachments[0].blocked_reason
    settings.MAIL_MAX_PARTS = 100
    settings.MAIL_MAX_DEPTH = 0
    assert all(p.blocked_reason for p in parse_mail(m.as_bytes()).attachments)


def test_path_names_never_become_storage_paths(box):
    m = EmailMessage()
    m["Subject"] = "DANE TESTOWE"
    m.set_content("DANE TESTOWE")
    m.add_attachment((Path(settings.ROOT_DIR) / "fixtures/remediation/numbered.pdf").read_bytes(), maintype="application", subtype="pdf", filename="../../DANE TESTOWE.pdf")
    obj = Message.objects.create(mailbox=box, folder="INBOX", uidvalidity=1, uid=1)
    obj = import_bytes(obj.pk, m.as_bytes(), timezone.now())
    attachment = obj.attachments.get()
    assert attachment.file.name.startswith("mail/") and ".." not in attachment.file.name
    assert len(attachment.file.name) == 37


@pytest.mark.django_db(transaction=True)
def test_atomic_two_claims_and_promotion_replay(box, customer, user):
    obj = incoming(box)
    users = [user, User.objects.create_user(username="concurrent")]
    barrier = Barrier(2)
    def run_claim(index):
        close_old_connections()
        api = APIClient()
        api.force_login(User.objects.get(pk=users[index].pk))
        barrier.wait(timeout=10)
        try:
            return post(api, obj, "claim", version=1).status_code
        finally:
            close_old_connections()
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(run_claim, range(2)))
    assert sorted(results) == [200, 409]
    obj.refresh_from_db()
    attachment = obj.attachments.get()
    barrier = Barrier(2)
    def promote(_):
        close_old_connections()
        api = APIClient()
        api.force_login(User.objects.get(pk=obj.owner_id))
        barrier.wait(timeout=10)
        try:
            return api.post(f"/api/mail-attachments/{attachment.pk}/promote/", {"version": 2, "client": customer.pk}, format="json").status_code
        finally:
            close_old_connections()
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(promote, range(2)))
    assert sorted(results) == [200, 201] and Document.objects.count() == 1


def test_current_integration_visible_after_many_old_configurations(api, user):
    from correspondence.config import current_mailbox
    current = current_mailbox()
    for n in range(25):
        Mailbox.objects.create(key=f"old-{n}", kind="imap", config_fingerprint=f"{n:064x}")
    page = api.get("/api/mailboxes/").data
    assert page["count"] == 26 and page["results"][0]["id"] == current.pk
    assert page["results"][0]["is_current"]
    for record in page["results"]:
        assert not {"password", "username", "lease_token", "config_fingerprint", "key"} & record.keys()
    assert api.post(f"/api/mailboxes/{current.pk}/control/", {"version": 1, "action": "start"}, format="json").status_code == 403
    user.role = "ADMIN"
    user.save()
    api.force_login(user)
    assert api.post(f"/api/mailboxes/{current.pk}/control/", {"version": 99, "action": "test"}, format="json").status_code == 409
    assert api.post(f"/api/mailboxes/{current.pk}/control/", {"version": 1, "action": "test", "host": "unknown.example.invalid"}, format="json").status_code == 400


def test_malformed_work_payload_and_search_rejected(api, box):
    obj = incoming(box)
    assert api.post(f"/api/messages/{obj.pk}/claim/", [], format="json").status_code == 400
    assert api.get("/api/messages/", {"search": "bad\x00query"}).status_code == 400
    assert post(api, obj, "claim", version=True).status_code == 400


def test_mime_invalid_filename_not_silently_promoted(box):
    raw = b'Subject: DANE TESTOWE\r\nMIME-Version: 1.0\r\nContent-Type: application/pdf\r\nContent-Disposition: attachment; filename="bad\x01.pdf"\r\n\r\n%PDF-1.4 DANE TESTOWE'
    parsed = parse_mail(raw)
    assert parsed.attachments[0].blocked_reason
    obj = Message.objects.create(mailbox=box, folder="INBOX", uidvalidity=1, uid=1)
    result = import_bytes(obj.pk, raw, timezone.now())
    assert result.fetch_state == "ready" and result.attachments.get().blocked_reason
    assert result.raw_file.read() == raw


def test_plain_crlf_is_a_line_ending_not_a_corrupt_character():
    parsed = parse_mail(raw_fixture("html-only"))
    assert "�" not in parsed.body_text
    assert not any("sterujące" in warning for warning in parsed.warnings)
