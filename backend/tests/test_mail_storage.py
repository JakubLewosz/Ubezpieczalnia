"""Crash recovery tests use an actual killed process and PostgreSQL commits."""
import json
import os
import subprocess
import sys
from datetime import timedelta
from pathlib import Path

import pytest
from django.db import connections, transaction
from django.utils import timezone

from correspondence.models import Mailbox, Message, StorageReservation
from correspondence.storage import JournalWriter, cleanup_stale_files, private_path, storage_operation

pytestmark = pytest.mark.django_db(transaction=True)
ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def pending_message():
    box = Mailbox.objects.create(key="DANE TESTOWE storage", kind="demo", state="demo")
    return Message.objects.create(mailbox=box, folder="INBOX", uidvalidity=1, uid=1)


def expire_journal(key):
    StorageReservation.objects.filter(storage_key=key).update(expires_at=timezone.now() - timedelta(seconds=1))


def test_journal_commit_precedes_business_transaction_and_active_writer_is_protected(settings):
    with storage_operation() as writer:
        with transaction.atomic():
            key = writer.write(b"DANE TESTOWE raw")
            assert StorageReservation.objects.filter(storage_key=key).exists()
            expire_journal(key)
            assert cleanup_stale_files() == {"deleted": 0, "referenced_kept": 0}
            assert private_path(key).exists()
    assert cleanup_stale_files() == {"deleted": 1, "referenced_kept": 0}
    assert not private_path(key).exists()


def test_reference_committed_before_journal_release_never_gets_deleted(pending_message):
    with storage_operation() as writer:
        key = writer.write(b"DANE TESTOWE raw")
        pending_message.raw_file.name = key
        pending_message.save(update_fields=["raw_file"])
        # Simulate a process ending after business commit but before release callback.
    expire_journal(key)
    assert cleanup_stale_files() == {"deleted": 0, "referenced_kept": 1}
    assert private_path(key).read_bytes() == b"DANE TESTOWE raw"
    assert not StorageReservation.objects.filter(storage_key=key).exists()


def test_normal_exception_cleans_bytes_and_durable_reservation(pending_message):
    key = None
    with pytest.raises(RuntimeError):
        with storage_operation() as writer:
            with transaction.atomic():
                key = writer.write(b"DANE TESTOWE rollback")
                pending_message.raw_file.name = key
                pending_message.save(update_fields=["raw_file"])
                raise RuntimeError("DANE TESTOWE rollback")
    assert not private_path(key).exists()
    assert not StorageReservation.objects.filter(storage_key=key).exists()
    pending_message.refresh_from_db()
    assert not pending_message.raw_file


def test_actual_sigkill_between_file_write_and_business_commit_recovers_only_owned_file(settings, pending_message):
    config = connections["default"].settings_dict
    env = {**os.environ, "POSTGRES_DB": config["NAME"], "POSTGRES_USER": config["USER"],
           "POSTGRES_PASSWORD": config["PASSWORD"], "POSTGRES_HOST": config["HOST"], "POSTGRES_PORT": str(config["PORT"]),
           "MEDIA_ROOT": str(settings.MEDIA_ROOT), "DJANGO_SETTINGS_MODULE": "config.settings", "PYTHONPATH": str(ROOT / "backend")}
    code = '''
import json, signal, sys, django
django.setup()
from django.db import transaction
from correspondence.models import Message
from correspondence.storage import storage_operation
with storage_operation(source_message_id=int(sys.argv[1])) as writer:
    with transaction.atomic():
        key = writer.write(b"DANE TESTOWE killed writer")
        Message.objects.filter(pk=int(sys.argv[1])).update(raw_file=key)
        print(json.dumps({"key":key}), flush=True)
        signal.pause()
'''
    process = subprocess.Popen([sys.executable, "-c", code, str(pending_message.pk)], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=env, cwd=ROOT)
    try:
        ready = process.stdout.readline()
        assert ready, "Proces testowy nie utworzył trwałej rezerwacji."
        key = json.loads(ready)["key"]
        assert StorageReservation.objects.filter(storage_key=key).exists()
        assert private_path(key).exists()
        sentinel = Path(settings.MEDIA_ROOT) / "unrelated-test-file"
        sentinel.write_bytes(b"DANE TESTOWE do not remove")
        process.kill()
        process.wait(timeout=10)
        assert process.returncode < 0
        pending_message.refresh_from_db()
        assert not pending_message.raw_file  # Actual interrupted DB transaction rolled back.
        expire_journal(key)
        assert cleanup_stale_files() == {"deleted": 1, "referenced_kept": 0}
        assert not private_path(key).exists()
        assert sentinel.read_bytes() == b"DANE TESTOWE do not remove"
        assert cleanup_stale_files() == {"deleted": 0, "referenced_kept": 0}
    finally:
        if process.poll() is None:
            process.kill()
            process.wait(timeout=10)
        process.stdout.close()
        process.stderr.close()


def test_cleanup_keeps_active_mailbox_lease(pending_message):
    pending_message.mailbox.enabled = True
    pending_message.mailbox.lease_expires = timezone.now() + timedelta(seconds=240)
    pending_message.mailbox.save()
    writer = JournalWriter(source_mailbox_id=pending_message.mailbox_id)
    key = writer.write(b"DANE TESTOWE lease")
    writer.close()
    expire_journal(key)
    assert cleanup_stale_files()["deleted"] == 0
    assert private_path(key).exists()
    Mailbox.objects.filter(pk=pending_message.mailbox_id).update(lease_expires=timezone.now() - timedelta(seconds=1))
    assert cleanup_stale_files()["deleted"] == 1
