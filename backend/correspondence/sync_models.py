"""Konfiguracja i stan odbioru bez sekretów; jeden aktywny zewnętrzny importer."""
from django.db import models


class Mailbox(models.Model):
    kind = models.CharField(max_length=8, default="imap")
    key = models.CharField(max_length=100, unique=True)
    folder = models.CharField(max_length=255, default="INBOX")
    config_fingerprint = models.CharField(max_length=64, blank=True)
    enabled = models.BooleanField(default=False)
    state = models.CharField(max_length=30, default="disabled")
    error_code = models.CharField(max_length=60, blank=True)
    error_message = models.CharField(max_length=500, blank=True)
    uidvalidity = models.PositiveBigIntegerField(null=True)
    boundary_uid = models.PositiveBigIntegerField(null=True)
    discovered_uid = models.PositiveBigIntegerField(null=True)
    pending_uidvalidity = models.PositiveBigIntegerField(null=True)
    last_success = models.DateTimeField(null=True)
    last_attempt = models.DateTimeField(null=True)
    last_requested = models.DateTimeField(null=True)
    queued_until = models.DateTimeField(null=True)
    next_attempt_at = models.DateTimeField(null=True)
    failures = models.PositiveIntegerField(default=0)
    lease_token = models.UUIDField(null=True)
    lease_expires = models.DateTimeField(null=True)
    version = models.PositiveIntegerField(default=1)
    rebuild_requested = models.BooleanField(default=False)
    rebuilding = models.BooleanField(default=False)
    recovery_history = models.JSONField(default=list)

    class Meta:
        app_label = "correspondence"
        constraints = [models.UniqueConstraint(fields=["kind"], condition=models.Q(kind="imap", enabled=True), name="one_enabled_imap_mailbox")]
