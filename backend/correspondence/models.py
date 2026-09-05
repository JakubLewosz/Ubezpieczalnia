"""A provider identity is one work item; reading it is a separate, personal record."""
import uuid
from django.conf import settings
from django.db import models
from .sync_models import Mailbox  # noqa: F401


def mail_key(instance, filename):
    return f"mail/{uuid.uuid4().hex}"


class Message(models.Model):
    class Status(models.TextChoices):
        TODO = "todo", "Do obsłużenia"
        IN_PROGRESS = "in_progress", "W trakcie"
        WAITING = "waiting", "Oczekujemy"
        DONE = "done", "Obsłużona"
        NO_ACTION = "no_action", "Nie wymaga działania"

    mailbox = models.ForeignKey("correspondence.Mailbox", on_delete=models.PROTECT, related_name="messages")
    folder = models.CharField(max_length=255)
    uidvalidity = models.PositiveBigIntegerField()
    uid = models.PositiveBigIntegerField()
    fetch_state = models.CharField(max_length=16, default="pending")
    fetch_error = models.CharField(max_length=500, blank=True)
    fetch_attempts = models.PositiveIntegerField(default=0)
    next_retry_at = models.DateTimeField(null=True, blank=True)
    raw_size = models.PositiveBigIntegerField(default=0)
    raw_sha256 = models.CharField(max_length=64, blank=True, db_index=True)
    raw_file = models.FileField(upload_to=mail_key, max_length=200, blank=True)
    subject = models.TextField(blank=True)
    sender_name = models.TextField(blank=True)
    sender_address = models.CharField(max_length=320, blank=True, db_index=True)
    message_id = models.TextField(blank=True)
    in_reply_to = models.TextField(blank=True)
    references = models.JSONField(default=list)
    headers = models.JSONField(default=list)
    body_text = models.TextField(blank=True)
    warnings = models.JSONField(default=list)
    received_at = models.DateTimeField(null=True, blank=True)
    declared_at = models.DateTimeField(null=True, blank=True)
    imported_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.TODO, db_index=True)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="mail_work")
    claimed_at = models.DateTimeField(null=True, blank=True)
    completed_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="mail_completed")
    completed_at = models.DateTimeField(null=True, blank=True)
    note = models.TextField(blank=True, max_length=10000)
    client = models.ForeignKey("clients.Client", null=True, blank=True, on_delete=models.PROTECT, related_name="correspondence")
    policy = models.ForeignKey("policies.Policy", null=True, blank=True, on_delete=models.PROTECT, related_name="correspondence")
    version = models.PositiveIntegerField(default=1)
    recovery_candidates = models.JSONField(default=list)
    recovery_status = models.CharField(max_length=20, default="none")

    class Meta:
        ordering = ["received_at", "imported_at", "id"]
        constraints = [models.UniqueConstraint(fields=["mailbox", "folder", "uidvalidity", "uid"], name="unique_mail_remote_identity")]


class Attachment(models.Model):
    message = models.ForeignKey(Message, on_delete=models.PROTECT, related_name="attachments")
    part_key = models.CharField(max_length=100)
    original_name = models.TextField()
    mime_type = models.CharField(max_length=100)
    size = models.PositiveBigIntegerField(default=0)
    checksum = models.CharField(max_length=64, blank=True)
    file = models.FileField(upload_to=mail_key, max_length=200, blank=True)
    blocked_reason = models.CharField(max_length=500, blank=True)
    document = models.OneToOneField("documents.Document", null=True, blank=True, on_delete=models.PROTECT, related_name="mail_source")

    class Meta:
        ordering = ["id"]
        constraints = [models.UniqueConstraint(fields=["message", "part_key"], name="unique_mail_mime_part")]


class ReadReceipt(models.Model):
    message = models.ForeignKey(Message, on_delete=models.CASCADE, related_name="reads")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    opened_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["message", "user"], name="unique_mail_personal_read")]


class StorageReservation(models.Model):
    """Durable crash journal. Numeric source IDs intentionally have no FK/locks."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    operation = models.UUIDField(db_index=True)
    storage_key = models.CharField(max_length=200, unique=True)
    created_at = models.DateTimeField()
    expires_at = models.DateTimeField(db_index=True)
    source_message_id = models.PositiveBigIntegerField(null=True)
    source_mailbox_id = models.PositiveBigIntegerField(null=True)
