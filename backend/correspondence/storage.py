"""Durable, private file reservations with crash reconciliation.

A separate PostgreSQL connection commits the reservation BEFORE bytes are
written, even when the business transaction later rolls back or is SIGKILLed.
The connection holds a session advisory lock while writing. Cleanup touches
only journaled random paths after a grace period, never arbitrary media files.
"""
import os
import re
import uuid
from contextlib import contextmanager
from datetime import timedelta
from pathlib import Path

import psycopg
from django.conf import settings
from django.db import connections, transaction
from django.utils import timezone
from psycopg import sql

from .models import Attachment, Mailbox, Message, StorageReservation

GRACE_SECONDS = 15 * 60
SAFE_KEY = re.compile(r"(?:mail/[0-9a-f]{32}|originals/[0-9a-f]{32}\.(?:pdf|png|jpg|jpeg|docx|xlsx))\Z")


def lock_key(operation):
    # Positive signed bigint, separated by random operation UUIDs.
    return operation.int & ((1 << 63) - 1)


def referenced(key):
    from documents.models import Document
    return (Message.objects.filter(raw_file=key).exists()
            or Attachment.objects.filter(file=key).exists()
            or Document.objects.filter(file=key).exists())


def private_path(key):
    if not SAFE_KEY.fullmatch(key):
        raise ValueError("Dziennik plików zawiera nieobsługiwany klucz magazynu.")
    root = Path(settings.MEDIA_ROOT).resolve()
    path = root / key
    if not path.parent.resolve().is_relative_to(root):
        raise ValueError("Katalog pliku wykracza poza prywatny magazyn.")
    return path


class JournalWriter:
    def __init__(self, source_message_id=None, source_mailbox_id=None):
        self.operation = uuid.uuid4()
        self.source_message_id = source_message_id
        self.source_mailbox_id = source_mailbox_id
        self.connection = None
        self.keys = []

    def _connect(self):
        if self.connection is not None:
            return self.connection
        # get_connection_params uses the current runtime/test database, NOT the
        # environment's source database name. No credentials are logged.
        parameters = dict(connections["default"].get_connection_params())
        parameters.pop("autocommit", None)
        self.connection = psycopg.connect(**parameters, autocommit=True)
        self.connection.execute("SELECT pg_advisory_lock(%s)", [lock_key(self.operation)])
        return self.connection

    def reserve(self, kind, extension=""):
        if kind not in {"mail", "originals"}:
            raise ValueError("Nieobsługiwany rodzaj rezerwacji pliku.")
        key = f"{kind}/{uuid.uuid4().hex}{extension if kind == 'originals' else ''}"
        path = private_path(key)
        if path.exists():
            raise ValueError("Losowy klucz pliku już istnieje; nie nadpisano magazynu.")
        now = timezone.now()
        self._connect().execute(sql.SQL(
            "INSERT INTO {} (id, operation, storage_key, created_at, expires_at, source_message_id, source_mailbox_id) VALUES (%s, %s, %s, %s, %s, %s, %s)"
        ).format(sql.Identifier(StorageReservation._meta.db_table)),
            [uuid.uuid4(), self.operation, key, now, now + timedelta(seconds=GRACE_SECONDS), self.source_message_id, self.source_mailbox_id])
        self.keys.append(key)
        return key

    def write(self, data, kind="mail", extension=""):
        key = self.reserve(kind, extension)
        path = private_path(key)
        path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        # Exact path, no implicit Storage.save renaming and no overwrites/symlinks.
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
        with os.fdopen(os.open(path, flags, 0o600), "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        return key

    def release(self):
        if self.connection is None:
            return
        try:
            self.connection.execute(sql.SQL("DELETE FROM {} WHERE operation=%s").format(
                sql.Identifier(StorageReservation._meta.db_table)), [self.operation])
        except Exception:
            # Committed model references protect the bytes; a later cleanup removes
            # the journal row if connection loss prevented its release.
            pass

    def rollback(self):
        if self.connection is None or connections["default"].needs_rollback:
            return
        for key in self.keys:
            if not referenced(key):
                private_path(key).unlink(missing_ok=True)
        self.release()

    def close(self):
        if self.connection is not None:
            self.connection.close()  # Releases the session lock even after a failed write.
            self.connection = None


@contextmanager
def storage_operation(source_message_id=None, source_mailbox_id=None):
    writer = JournalWriter(source_message_id, source_mailbox_id)
    try:
        yield writer
    except BaseException:
        try:
            writer.rollback()
        except Exception:
            # The durable rows remain for reconciliation; preserve the real error.
            pass
        raise
    finally:
        writer.close()


def cleanup_stale_files(limit=100):
    """Idempotent, finite cleanup; advisory lock prevents deleting an active writer."""
    now = timezone.now()
    ids = list(StorageReservation.objects.filter(expires_at__lte=now).order_by("expires_at").values_list("pk", flat=True)[:limit])
    deleted = kept = 0
    for reservation_id in ids:
        with transaction.atomic():
            reservation = StorageReservation.objects.select_for_update(skip_locked=True).filter(pk=reservation_id, expires_at__lte=now).first()
            if reservation is None:
                continue
            with connections["default"].cursor() as cursor:
                cursor.execute("SELECT pg_try_advisory_xact_lock(%s)", [lock_key(reservation.operation)])
                if not cursor.fetchone()[0]:
                    continue
            if reservation.source_mailbox_id and Mailbox.objects.filter(pk=reservation.source_mailbox_id, lease_expires__gt=now, enabled=True).exists():
                continue
            # References are checked after reserving this cleanup transaction.
            if referenced(reservation.storage_key):
                kept += 1
            else:
                private_path(reservation.storage_key).unlink(missing_ok=True)
                deleted += 1
            reservation.delete()
    return {"deleted": deleted, "referenced_kept": kept}
