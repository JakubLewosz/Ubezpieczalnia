import uuid
from datetime import timedelta

from celery import shared_task
from django.conf import settings
from django.db import transaction
from django.utils import timezone

from .acquisition import AcquisitionError, acquire_document
from .engine import BrokerMotorEngine, ExtractionLimitError
from .models import EngineResult, ExtractionJob, ReviewDraft


def dispatch_job(job_id):
    try:
        process_document.delay(job_id)
    except Exception:
        ExtractionJob.objects.filter(pk=job_id, status="queued").update(
            status="failed", error="Nie udało się przekazać zadania do kolejki. Sprawdź Redis i ponów odczyt.",
            finished_at=timezone.now(), lease_until=None,
        )


@shared_task(acks_late=True, reject_on_worker_lost=True, soft_time_limit=240, time_limit=270)
def process_document(job_id):
    token = uuid.uuid4()
    with transaction.atomic():
        job = ExtractionJob.objects.select_for_update().select_related("document").get(pk=job_id)
        if job.status == "succeeded" or EngineResult.objects.filter(job=job).exists():
            return
        if job.status == "failed":
            return
        if job.status == "running" and job.lease_until and job.lease_until > timezone.now():
            return
        job.status = "running"
        job.started_at = timezone.now()
        job.finished_at = None
        job.error = ""
        job.lease_until = timezone.now() + timedelta(seconds=getattr(settings, "EXTRACTION_LEASE_SECONDS", 300))
        job.attempt_token = token
        job.attempts += 1
        job.save()
    try:
        pages = acquire_document(job.document)
        parsed = BrokerMotorEngine().extract(pages)
        with transaction.atomic():
            locked = ExtractionJob.objects.select_for_update().get(pk=job.pk)
            if locked.attempt_token != token or locked.status != "running":
                return
            result = EngineResult.objects.create(job=locked, **parsed)
            if result.profile:
                ReviewDraft.objects.get_or_create(
                    document=job.document, defaults={"engine_result": result, "fields": result.fields}
                )
            locked.status = "succeeded"
            locked.finished_at = timezone.now()
            locked.lease_until = None
            locked.save()
    except Exception as exc:
        message = str(exc) if isinstance(exc, (AcquisitionError, ExtractionLimitError)) else "Odczyt nie powiódł się lub przekroczył limit czasu. Ponów zadanie."
        ExtractionJob.objects.filter(pk=job.pk, attempt_token=token, status="running").update(
            status="failed", error=message[:500], finished_at=timezone.now(), lease_until=None,
        )


@shared_task
def recover_stale_jobs():
    """Celery beat runs this every minute, including after a worker hard termination."""
    now = timezone.now()
    queued_age = now - timedelta(seconds=getattr(settings, "EXTRACTION_LEASE_SECONDS", 300))
    candidates = ExtractionJob.objects.filter(status="running", lease_until__lte=now).values_list("pk", flat=True)
    queued = ExtractionJob.objects.filter(status="queued", created_at__lte=queued_age).values_list("pk", flat=True)
    for job_id in list(candidates) + list(queued):
        with transaction.atomic():
            job = ExtractionJob.objects.select_for_update().get(pk=job_id)
            if job.status not in {"queued", "running"}:
                continue
            if job.status == "running" and job.lease_until and job.lease_until > timezone.now():
                continue
            if job.attempts >= 3:
                job.status = "failed"
                job.error = "Proces odczytu był wielokrotnie przerwany. Sprawdź zasoby i ponów odczyt ręcznie."
                job.finished_at = timezone.now()
            else:
                job.status = "queued"
                job.attempt_token = None
                job.lease_until = None
                transaction.on_commit(lambda pk=job.pk: dispatch_job(pk))
            job.save()
