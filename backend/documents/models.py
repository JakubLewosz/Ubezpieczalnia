import uuid
from pathlib import Path
from django.conf import settings
from django.db import models


def private_key(instance, filename):
    return f"originals/{uuid.uuid4().hex}{Path(filename).suffix.lower()}"


class Document(models.Model):
    client = models.ForeignKey("clients.Client", related_name="documents", on_delete=models.PROTECT)
    policy = models.ForeignKey(
        "policies.Policy", related_name="documents", null=True, blank=True, on_delete=models.PROTECT
    )
    file = models.FileField(upload_to=private_key, max_length=200)
    original_name = models.CharField(max_length=255)
    mime_type = models.CharField(max_length=100)
    size = models.PositiveBigIntegerField()
    checksum = models.CharField(max_length=64, db_index=True)
    category = models.CharField(max_length=100, default="Wniosek brokerski")
    page_count = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)

    class Meta:
        ordering = ["-created_at", "-id"]

    @property
    def supports_extraction(self):
        return self.mime_type in ["application/pdf", "image/jpeg", "image/png"]
