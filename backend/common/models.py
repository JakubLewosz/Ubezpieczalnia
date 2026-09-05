from django.conf import settings
from django.db import models


class AuditEvent(models.Model):
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL)
    action = models.CharField(max_length=64)
    object_type = models.CharField(max_length=32)
    object_id = models.PositiveBigIntegerField()
    client = models.ForeignKey("clients.Client", null=True, blank=True, on_delete=models.PROTECT)
    metadata = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]
