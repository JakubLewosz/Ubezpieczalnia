"""Shared IMAP and explicit offline-demo import; no OCR or business links here."""
import hashlib
from dataclasses import fields
from django.core.files.base import ContentFile
from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError
from common.api import Conflict
from common.audit import record
from documents.validation import inspect_upload
from .mime import ParsedMail, MimeLimitError, parse_mail, limit
from .models import Attachment, Mailbox, Message
from .storage import storage_operation


def assert_lease(mailbox, token):
    if token is None and mailbox.kind == "demo":
        return
    if (not token or str(mailbox.lease_token) != str(token) or not mailbox.enabled
            or not mailbox.lease_expires or mailbox.lease_expires <= timezone.now()):
        raise Conflict("Dzierżawa importu wygasła; ten worker nie może zapisać postępu.")


def import_bytes(message_id, raw, received_at, token=None):
    """Idempotent by remote Message identity; cleanup all new storage objects on rollback."""
    if len(raw) > limit("MAIL_MAX_RAW_BYTES", 30 * 1024 * 1024):
        raise MimeLimitError("Wiadomość przekracza limit surowych bajtów.")
    error = ""
    try:
        parsed = parse_mail(raw)
    except (MimeLimitError, ValueError, RecursionError, UnicodeError):
        parsed = ParsedMail()
        error = "Nie można odczytać struktury MIME. Zachowano źródło do kontroli administratora."
    parts = []
    for part in parsed.attachments:
        metadata = None
        if not part.blocked_reason:
            try:
                metadata = inspect_upload(ContentFile(part.data, name=part.name))
            except ValidationError:
                # Never put library exceptions containing payload/headers into logs or DB diagnostics.
                part.blocked_reason = "Typ, nazwa, zawartość lub rozmiar nie spełnia reguł dokumentów (PDF/JPEG/PNG/DOCX/XLSX)."
        parts.append((part, metadata))
    mailbox_id = Message.objects.values_list("mailbox_id", flat=True).get(pk=message_id)
    with storage_operation(message_id, mailbox_id) as writer:
        with transaction.atomic():
            mailbox_id = Message.objects.values_list("mailbox_id", flat=True).get(pk=message_id)
            mailbox = Mailbox.objects.select_for_update().get(pk=mailbox_id)
            assert_lease(mailbox, token)
            message = Message.objects.select_for_update().get(pk=message_id)
            if message.raw_file or message.fetch_state == "ready":
                return message
            message.raw_file.name = writer.write(raw)
            message.raw_sha256 = hashlib.sha256(raw).hexdigest()
            message.raw_size = len(raw)
            message.received_at = received_at
            for definition in fields(ParsedMail):
                if definition.name != "attachments":
                    setattr(message, definition.name, getattr(parsed, definition.name))
            message.fetch_state = "error" if error else "ready"
            message.fetch_error = error
            message.next_retry_at = None
            # UIDVALIDITY recovery never inherits work state; candidates are context for a human.
            if message.recovery_status == "review":
                candidates = Message.objects.filter(
                    mailbox=mailbox, raw_sha256=message.raw_sha256, raw_size=len(raw),
                    subject=message.subject, sender_address=message.sender_address,
                    received_at=message.received_at, fetch_state="ready",
                ).exclude(uidvalidity=message.uidvalidity).order_by("id")
                message.recovery_candidates = list(candidates.values_list("pk", flat=True)[:50])
            message.save()
            for part, metadata in parts:
                attachment = Attachment(
                    message=message, part_key=part.key, original_name=part.name,
                    mime_type=part.mime[:100], size=part.size, blocked_reason=part.blocked_reason,
                )
                if metadata:
                    attachment.checksum = metadata["checksum"]
                    attachment.mime_type = metadata["mime_type"]
                    attachment.file.name = writer.write(part.data)
                attachment.save()
            record(None, "mail.imported", "message", message.pk, metadata={
                "mailbox": mailbox.pk, "attachment_count": len(parts), "fetch_state": message.fetch_state,
                "recovery_status": message.recovery_status,
            })
            assert_lease(mailbox, token)
            transaction.on_commit(writer.release)
            return message
