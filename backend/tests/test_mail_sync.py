"""Transactional synchronization tests; fake transport is only this unit layer."""
import copy
import uuid
from datetime import timedelta
from io import BytesIO
from pathlib import Path

import pytest
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, ValidationError

from correspondence.config import current_mailbox, load_config
from correspondence.imap_client import BoundedIMAP4SSL, FetchedMessage, FolderInfo, IMAPClient, MailError
from correspondence.models import Mailbox, Message
from correspondence.sync import LeaseLost, _persist_discovered, control, request_sync, reserve, synchronize, test_connection as connection_test
from extraction.services import VersionConflict

ROOT = Path(__file__).resolve().parents[2]
RAW = (ROOT / "fixtures/mail/newsletter.eml").read_bytes()


class UnitServer:
    def __init__(self):
        self.uidvalidity = 10
        self.uidnext = 1
        self.raw = {}
        self.received_at = timezone.now().replace(microsecond=0)
        self.calls = []
        self.on_open = None
        self.on_fetch = None
        self.extra_search_uids = []
        self.open_error = None

    def client(self, config):
        server = self

        class Transport:
            def __enter__(self):
                return self

            def __exit__(self, *args):
                pass

            def open_folder(self):
                server.calls.append(("EXAMINE",))
                if server.open_error:
                    raise server.open_error
                response = FolderInfo(server.uidvalidity, server.uidnext)
                if server.on_open:
                    server.on_open()
                return response

            def search_uids(self, low, high):
                server.calls.append(("SEARCH", low, high))
                return sorted(uid for uid in server.raw if low <= uid <= high) + server.extra_search_uids

            def fetch_message(self, uid):
                server.calls.append(("FETCH", uid))
                if server.on_fetch:
                    server.on_fetch(uid)
                result = server.raw[uid]
                if isinstance(result, Exception):
                    raise result
                return FetchedMessage(result, server.received_at, len(result))

        return Transport()


@pytest.fixture
def sync_config(monkeypatch):
    monkeypatch.setenv("MAIL_SYNC_ENABLED", "true")
    monkeypatch.setenv("MAIL_HOST", "imap.example.invalid")
    monkeypatch.setenv("MAIL_PORT", "993")
    monkeypatch.setenv("MAIL_USERNAME", "shared@example.invalid")
    monkeypatch.setenv("MAIL_PASSWORD", "DANE-TESTOWE-password")
    monkeypatch.delenv("MAIL_PASSWORD_FILE", raising=False)
    monkeypatch.delenv("MAIL_CA_FILE", raising=False)
    return load_config()


@pytest.fixture
def server(monkeypatch, sync_config):
    server = UnitServer()
    monkeypatch.setattr("correspondence.sync.IMAPClient", server.client)
    return server


@pytest.fixture
def mailbox(server):
    mailbox = current_mailbox()
    mailbox.enabled = True
    mailbox.save()
    return mailbox


def resume_after_backoff(mailbox):
    Mailbox.objects.filter(pk=mailbox.pk).update(next_attempt_at=timezone.now() - timedelta(seconds=1))
    Message.objects.filter(mailbox=mailbox, next_retry_at__isnull=False).update(next_retry_at=timezone.now() - timedelta(seconds=1))


@pytest.mark.django_db
def test_first_boundary_is_atomic_mail_arriving_during_init_is_not_lost(mailbox, server):
    server.uidnext = 5
    server.raw = {1: RAW, 4: RAW}

    def arrival():
        server.raw[5] = RAW
        server.uidnext = 6

    server.on_open = arrival
    assert synchronize(mailbox.pk)["status"] == "completed"
    mailbox.refresh_from_db()
    assert mailbox.boundary_uid == mailbox.discovered_uid == 4
    assert not Message.objects.exists()
    assert server.calls == [("EXAMINE",)]
    server.on_open = None
    assert synchronize(mailbox.pk)["status"] == "completed"
    message = Message.objects.get()
    assert message.uid == 5 and message.status == "todo" and message.fetch_state == "ready"
    mailbox.refresh_from_db()
    assert mailbox.boundary_uid == 4 and mailbox.discovered_uid == 5 and mailbox.last_success
    synchronize(mailbox.pk)
    assert Message.objects.count() == 1
    assert sum(call[0] == "FETCH" for call in server.calls) == 1


@pytest.mark.django_db
def test_empty_folder_gaps_old_uid_trap_and_finite_batches(mailbox, server, monkeypatch):
    assert synchronize(mailbox.pk)["status"] == "completed"
    mailbox.refresh_from_db()
    assert mailbox.boundary_uid == 0
    server.raw = {3: RAW, 9: RAW, 19: RAW}
    server.uidnext = 20
    server.extra_search_uids = [0, 99]  # Malformed/out-of-range server response cannot cause a fetch.
    monkeypatch.setenv("MAIL_BATCH_SIZE", "2")
    assert synchronize(mailbox.pk)["status"] == "completed"
    assert set(Message.objects.values_list("uid", flat=True)) <= {3, 9}
    assert synchronize(mailbox.pk)["status"] == "completed"
    assert set(Message.objects.values_list("uid", flat=True)) == {3, 9, 19}
    assert all(call[1] in {3, 9, 19} for call in server.calls if call[0] == "FETCH")
    assert all(call[1] <= call[2] < 20 for call in server.calls if call[0] == "SEARCH")


@pytest.mark.django_db
def test_cursor_never_crosses_identity_that_was_not_durably_saved(mailbox, server, monkeypatch):
    synchronize(mailbox.pk)
    server.raw, server.uidnext = {1: RAW, 2: RAW}, 3
    original = Message.objects.get_or_create

    def fail_second(*args, **kwargs):
        if kwargs.get("uid") == 2:
            raise RuntimeError("DANE TESTOWE temporary DB error")
        return original(*args, **kwargs)

    monkeypatch.setattr(Message.objects, "get_or_create", fail_second)
    assert synchronize(mailbox.pk)["status"] == "error"
    mailbox.refresh_from_db()
    assert mailbox.discovered_uid == 0
    assert not Message.objects.exists()
    monkeypatch.setattr(Message.objects, "get_or_create", original)
    resume_after_backoff(mailbox)
    assert synchronize(mailbox.pk)["status"] == "completed"
    assert Message.objects.count() == 2


@pytest.mark.django_db
def test_disconnect_keeps_identity_and_retry_is_idempotent(mailbox, server):
    synchronize(mailbox.pk)
    server.raw = {1: MailError("connection_lost", "Przerwano odbiór DANE TESTOWE."), 2: RAW}
    server.uidnext = 3
    assert synchronize(mailbox.pk)["status"] == "error"
    mailbox.refresh_from_db()
    assert mailbox.discovered_uid == 2
    assert Message.objects.count() == 2
    failed = Message.objects.get(uid=1)
    assert failed.fetch_state == "error" and failed.next_retry_at and not failed.raw_file
    server.raw[1] = RAW
    resume_after_backoff(mailbox)
    assert synchronize(mailbox.pk)["status"] == "completed"
    assert list(Message.objects.order_by("uid").values_list("fetch_state", flat=True)) == ["ready", "ready"]
    assert Message.objects.count() == 2


@pytest.mark.django_db
def test_large_or_missing_message_is_visible_and_does_not_block_later(mailbox, server):
    synchronize(mailbox.pk)
    server.raw = {
        1: MailError("message_too_large", "Wiadomość przekracza limit.", permanent=True, message_specific=True),
        2: MailError("message_gone", "Wiadomość zniknęła z folderu.", permanent=True, message_specific=True),
        3: RAW,
    }
    server.uidnext = 4
    assert synchronize(mailbox.pk)["status"] == "completed"
    assert Message.objects.get(uid=1).fetch_state == Message.objects.get(uid=2).fetch_state == "error"
    assert Message.objects.get(uid=3).fetch_state == "ready"
    mailbox.refresh_from_db()
    assert mailbox.enabled


@pytest.mark.django_db
@pytest.mark.parametrize("code", ["authentication", "tls_certificate"])
def test_auth_or_certificate_failure_pauses_retries_without_leaking_content(mailbox, server, code, caplog):
    server.open_error = MailError(code, "Sprawdź bezpieczną konfigurację.", permanent=True)
    assert synchronize(mailbox.pk)["error_code"] == code
    mailbox.refresh_from_db()
    assert mailbox.enabled is False and mailbox.last_success is None and mailbox.state == "error"
    assert synchronize(mailbox.pk)["status"] == "not_reserved"
    assert "DANE-TESTOWE-password" not in caplog.text


@pytest.mark.django_db
def test_expired_lease_recovered_old_worker_cannot_advance(mailbox, server, sync_config):
    token = reserve(mailbox.pk, sync_config)
    assert reserve(mailbox.pk, sync_config) is None
    Mailbox.objects.filter(pk=mailbox.pk).update(lease_expires=timezone.now() - timedelta(seconds=1))
    new_token = reserve(mailbox.pk, sync_config)
    assert token != new_token
    with pytest.raises(LeaseLost):
        with __import__("django.db", fromlist=["transaction"]).transaction.atomic():
            _persist_discovered(mailbox.pk, token, FolderInfo(10, 2), [1], 1, 25)
    assert not Message.objects.exists()


@pytest.mark.django_db
def test_lost_lease_during_body_fetch_cannot_import_files_or_advance(mailbox, server):
    synchronize(mailbox.pk)
    server.raw, server.uidnext = {1: RAW}, 2
    server.on_fetch = lambda uid: Mailbox.objects.filter(pk=mailbox.pk).update(lease_token=uuid.uuid4())
    assert synchronize(mailbox.pk)["status"] == "lease_lost"
    message = Message.objects.get()
    assert not message.raw_file and message.fetch_state == "pending"


@pytest.mark.django_db
def test_three_worker_interruptions_become_visible_terminal_failure(mailbox, server):
    synchronize(mailbox.pk)
    Message.objects.create(mailbox=mailbox, folder="INBOX", uidvalidity=10, uid=1, fetch_attempts=3)
    Mailbox.objects.filter(pk=mailbox.pk).update(discovered_uid=1)
    server.uidnext = 2
    assert synchronize(mailbox.pk)["status"] == "completed"
    message = Message.objects.get()
    assert message.fetch_state == "error" and message.next_retry_at is None


@pytest.mark.django_db
def test_uidvalidity_change_stops_then_explicit_recovery_preserves_done_history(mailbox, server, user, monkeypatch):
    synchronize(mailbox.pk)
    server.raw, server.uidnext = {1: RAW}, 2
    synchronize(mailbox.pk)
    previous = Message.objects.get()
    previous.status = "done"
    previous.note = "DANE TESTOWE wykonano wcześniej"
    previous.save()
    historical = copy.deepcopy(previous.__dict__)
    server.uidvalidity = 99
    server.raw = {2: RAW, 3: RAW.replace(b"Newsletter", b"Nowa wiadomosc")}
    server.uidnext = 4
    assert synchronize(mailbox.pk)["status"] == "resync_required"
    mailbox.refresh_from_db()
    assert not mailbox.enabled and mailbox.uidvalidity == 10 and mailbox.pending_uidvalidity == 99
    user.role = "ADMIN"
    user.save()
    monkeypatch.setattr("correspondence.tasks.sync_mailbox.delay", lambda *_: None)
    with pytest.raises(ValidationError):
        control("start", user, mailbox.version)
    control("rebuild", user, mailbox.version)
    assert synchronize(mailbox.pk)["status"] == "completed"
    previous.refresh_from_db()
    assert previous.status == historical["status"] and previous.note == historical["note"]
    new = Message.objects.filter(uidvalidity=99).order_by("uid")
    assert new.count() == 2 and all(m.status == "todo" and m.recovery_status == "review" for m in new)
    assert previous.pk in new[0].recovery_candidates
    mailbox.refresh_from_db()
    assert mailbox.boundary_uid == 0 and mailbox.recovery_history[0]["uidvalidity"] == 10


@pytest.mark.django_db
def test_test_connection_does_not_activate_or_reset_boundary(server, user, monkeypatch):
    mailbox = current_mailbox()
    mailbox.uidvalidity, mailbox.boundary_uid, mailbox.discovered_uid = 10, 15, 20
    mailbox.save()
    user.role = "ADMIN"
    user.save()
    server.uidnext = 100
    response = connection_test(user)
    assert response["ok"] and server.calls == [("EXAMINE",)]
    mailbox.refresh_from_db()
    assert not mailbox.enabled and mailbox.boundary_uid == 15 and mailbox.discovered_uid == 20


@pytest.mark.django_db
def test_queue_deduplication_control_permissions_and_versions(mailbox, server, user, monkeypatch):
    enqueued = []
    monkeypatch.setattr("correspondence.tasks.sync_mailbox.delay", lambda pk: enqueued.append(pk))
    assert request_sync()["queued"]
    assert not request_sync()["queued"]
    assert enqueued == [mailbox.pk]
    with pytest.raises(PermissionDenied):
        control("pause", user, mailbox.version)
    user.role = "ADMIN"
    user.save()
    with pytest.raises(VersionConflict):
        control("pause", user, 999)
    control("pause", user, mailbox.version)
    assert not request_sync()["queued"]


@pytest.mark.django_db
def test_changed_account_folder_and_master_disable_cannot_reuse_cursor(mailbox, server, monkeypatch):
    synchronize(mailbox.pk)
    old_fingerprint = mailbox.config_fingerprint
    monkeypatch.setenv("MAIL_FOLDER", "Archive-test")
    replacement = current_mailbox()
    assert replacement.pk != mailbox.pk and replacement.config_fingerprint != old_fingerprint
    assert replacement.boundary_uid is replacement.discovered_uid is None
    mailbox.refresh_from_db()
    assert not mailbox.enabled and mailbox.state == "configuration_changed"
    replacement.enabled = True
    replacement.save()
    monkeypatch.setenv("MAIL_SYNC_ENABLED", "false")
    assert not current_mailbox().enabled


def test_imap_literal_is_rejected_before_any_body_read():
    connection = object.__new__(BoundedIMAP4SSL)
    connection.max_literal = 100
    connection.response_budget = 1000

    class NoRead:
        def read(self, size):
            pytest.fail("Oversized literal was read into memory")

    connection.file = NoRead()
    with pytest.raises(MailError) as raised:
        connection.read(101)
    assert raised.value.code == "response_too_large"


def test_cumulative_protocol_budget_cannot_be_exceeded():
    connection = object.__new__(BoundedIMAP4SSL)
    connection.max_literal = 100
    connection.response_budget = 5
    connection.file = BytesIO(b"abcde\n")
    with pytest.raises(MailError):
        connection.readline()


def test_uid_parser_empty_bounds_ignores_old_last_response(sync_config):
    client = IMAPClient(sync_config)
    calls = []
    client._call = lambda *args: calls.append(args) or [b"9 10 11 12 999"]
    assert client.search_uids(12, 11) == [] and calls == []
    assert client.search_uids(10, 12) == [10, 11, 12]
    assert calls == [("uid", "SEARCH", None, "UID", "10:12")]


def test_config_secret_is_not_repr_and_incorrect_settings_are_safe(sync_config, monkeypatch):
    assert "DANE-TESTOWE-password" not in repr(sync_config)
    monkeypatch.setenv("MAIL_PASSWORD_FILE", "/DANE-TESTOWE-missing-file")
    from correspondence.config import MailConfigurationError
    with pytest.raises(MailConfigurationError) as exc:
        load_config()
    assert "DANE-TESTOWE-missing-file" not in str(exc.value)


@pytest.mark.django_db
def test_missing_secret_file_pauses_existing_importer_without_exposing_path(mailbox, monkeypatch):
    monkeypatch.setenv("MAIL_PASSWORD_FILE", "/DANE-TESTOWE-private-missing")
    assert synchronize(mailbox.pk)["error_code"] == "configuration"
    mailbox.refresh_from_db()
    assert not mailbox.enabled and mailbox.state == "error"
    assert "private-missing" not in mailbox.error_message


@pytest.mark.django_db
def test_connection_test_is_throttled_and_pause_still_works_if_secret_is_missing(mailbox, server, user, monkeypatch):
    user.role = "ADMIN"
    user.save()
    assert connection_test(user)["ok"]
    assert connection_test(user)["error_code"] == "rate_limited"
    assert server.calls == [("EXAMINE",)]
    monkeypatch.setenv("MAIL_PASSWORD_FILE", "/DANE-TESTOWE-private-missing")
    result = control("pause", user, mailbox.version)
    assert not result.enabled and result.state == "paused"


def test_invalid_ca_file_and_all_tls_negotiation_failures_stop_retry(sync_config, monkeypatch):
    import ssl
    from dataclasses import replace

    from correspondence.config import MailConfigurationError
    with pytest.raises(MailConfigurationError):
        with IMAPClient(replace(sync_config, ca_file="/DANE-TESTOWE-missing-ca")):
            pytest.fail("Missing CA was accepted")

    def broken_tls(*args, **kwargs):
        raise ssl.SSLError("DANE TESTOWE server handshake")

    monkeypatch.setattr("correspondence.imap_client.BoundedIMAP4SSL", broken_tls)
    with pytest.raises(MailError) as raised:
        with IMAPClient(sync_config):
            pytest.fail("Broken TLS was accepted")
    assert raised.value.permanent and raised.value.code == "tls_error"
    assert "server handshake" not in raised.value.message


def test_body_fetch_checks_actual_bytes_and_uid_even_when_uid_follows_literal(sync_config):
    client = IMAPClient(sync_config)
    replies = iter([
        [b'1 (UID 5 RFC822.SIZE 3 INTERNALDATE "05-Sep-2026 10:00:00 +0200")'],
        [(b'1 (BODY[] {3}', b'abc'), b' UID 5)'],
    ])
    client._call = lambda *args, **kwargs: next(replies)
    result = client.fetch_message(5)
    assert result.raw == b"abc" and result.received_at.hour == 8
    replies = iter([
        [b'1 (UID 5 RFC822.SIZE 10 INTERNALDATE "05-Sep-2026 10:00:00 +0200")'],
        [(b'1 (UID 5 BODY[] {3}', b'abc'), b')'],
    ])
    with pytest.raises(MailError) as raised:
        client.fetch_message(5)
    assert raised.value.code == "incomplete_message"


def test_advertised_size_is_checked_before_body_fetch(sync_config):
    client = IMAPClient(sync_config)
    calls = []
    client._call = lambda *args, **kwargs: calls.append(args) or [b'1 (UID 1 RFC822.SIZE 999999999 INTERNALDATE "05-Sep-2026 10:00:00 +0200")']
    with pytest.raises(MailError) as raised:
        client.fetch_message(1)
    assert raised.value.code == "message_too_large"
    assert calls == [("uid", "FETCH", "1", "(UID RFC822.SIZE INTERNALDATE)")]


@pytest.mark.django_db
def test_invalid_integer_before_lease_pauses_fences_and_requires_explicit_resume(mailbox, server, monkeypatch):
    mailbox.state = "connected"
    mailbox.lease_token = uuid.uuid4()
    mailbox.lease_expires = timezone.now() + timedelta(seconds=200)
    mailbox.save()
    monkeypatch.setenv("MAIL_PORT", "DANE TESTOWE invalid")
    assert synchronize(mailbox.pk)["error_code"] == "configuration"
    mailbox.refresh_from_db()
    assert not mailbox.enabled and mailbox.state == "error" and mailbox.lease_token is None
    assert server.calls == []
    monkeypatch.setenv("MAIL_PORT", "993")
    assert synchronize(mailbox.pk)["status"] == "not_reserved"


@pytest.mark.django_db
def test_periodic_request_invalid_limits_cannot_leave_connected_state(mailbox, settings):
    mailbox.state = "connected"
    mailbox.save()
    settings.MAIL_CONFIGURATION_ERRORS = ["MAIL_MAX_PARTS"]
    assert request_sync()["error_code"] == "configuration"
    mailbox.refresh_from_db()
    assert mailbox.state == "error" and mailbox.enabled is False


@pytest.mark.django_db
def test_admin_can_pause_specific_source_despite_broken_port_and_shared_limits(mailbox, user, monkeypatch, settings):
    user.role = "ADMIN"
    user.save()
    monkeypatch.setenv("MAIL_PORT", "DANE TESTOWE invalid")
    settings.MAIL_CONFIGURATION_ERRORS = ["MAIL_POLL_SECONDS"]
    response = control("pause", user, mailbox.version, mailbox_id=mailbox.pk)
    assert not response.enabled and response.state == "paused"
