from django.conf import settings
from django.db import models


class ImmutableQuerySet(models.QuerySet):
    def update(self, **kwargs):
        raise ValueError("Zapis jest niezmienny; utwórz nową rewizję.")

    def delete(self):
        raise ValueError("Zapis jest niezmienny.")


class ImmutableModel(models.Model):
    objects = ImmutableQuerySet.as_manager()

    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise ValueError("Zapis jest niezmienny; utwórz nową rewizję.")
        if kwargs.get("force_update"):
            raise ValueError("Zapis jest niezmienny; utwórz nową rewizję.")
        kwargs["force_insert"] = True
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValueError("Zapis jest niezmienny.")


class ExtractionJob(models.Model):
    class Status(models.TextChoices):
        QUEUED = "queued", "W kolejce"
        RUNNING = "running", "Odczytywanie"
        SUCCEEDED = "succeeded", "Odczyt zakończony"
        FAILED = "failed", "Błąd odczytu"

    document = models.ForeignKey("documents.Document", on_delete=models.PROTECT, related_name="jobs")
    status = models.CharField(max_length=12, choices=Status, default=Status.QUEUED)
    error = models.CharField(max_length=500, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    started_at = models.DateTimeField(null=True)
    finished_at = models.DateTimeField(null=True)
    lease_until = models.DateTimeField(null=True)
    attempt_token = models.UUIDField(null=True, editable=False)
    attempts = models.PositiveIntegerField(default=0)
    requested_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)

    class Meta:
        ordering = ["-created_at", "-id"]
        constraints = [
            models.UniqueConstraint(
                fields=["document"],
                condition=models.Q(status__in=["queued", "running"]),
                name="one_active_extraction_per_document",
            )
        ]
        indexes = [models.Index(fields=["status", "lease_until"])]


class EngineResult(ImmutableModel):
    job = models.OneToOneField(ExtractionJob, on_delete=models.PROTECT, related_name="result")
    profile = models.CharField(max_length=100, null=True)
    fields = models.JSONField(default=list)
    warnings = models.JSONField(default=list)
    pages = models.JSONField(default=list)
    created_at = models.DateTimeField(auto_now_add=True)


class ReviewDraft(models.Model):
    document = models.OneToOneField("documents.Document", on_delete=models.PROTECT, related_name="draft")
    engine_result = models.ForeignKey(EngineResult, on_delete=models.PROTECT)
    fields = models.JSONField(default=list)
    version = models.PositiveIntegerField(default=1)
    approved_version = models.PositiveIntegerField(null=True)
    updated_at = models.DateTimeField(auto_now=True)


class ApprovedRevision(ImmutableModel):
    document = models.ForeignKey("documents.Document", on_delete=models.PROTECT, related_name="revisions")
    engine_result = models.ForeignKey(EngineResult, on_delete=models.PROTECT)
    number = models.PositiveIntegerField()
    draft_version = models.PositiveIntegerField()
    fields = models.JSONField(default=list)
    profile = models.CharField(max_length=100)
    document_name = models.CharField(max_length=255)
    document_checksum = models.CharField(max_length=64)
    warnings = models.JSONField(default=list)
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-number"]
        constraints = [
            models.UniqueConstraint(fields=["document", "number"], name="unique_document_revision"),
            models.UniqueConstraint(
                fields=["document", "draft_version"], name="unique_approved_draft_version"
            ),
        ]
