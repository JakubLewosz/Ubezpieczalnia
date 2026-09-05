"""Short DB reservations, bounded read-only network work and fenced progress."""
import time
import uuid
from datetime import timedelta

from celery.exceptions import SoftTimeLimitExceeded
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, ValidationError

from common.audit import record
from extraction.services import VersionConflict

from .config import MailConfigurationError, current_mailbox, load_config
from .imap_client import IMAPClient, MailError
from .sync_models import Mailbox


class LeaseLost(Exception):
    pass


def _locked(mailbox_id, token):
    mailbox = Mailbox.objects.select_for_update().get(pk=mailbox_id)
    if not mailbox.enabled or mailbox.lease_token != token or not mailbox.lease_expires or mailbox.lease_expires <= timezone.now():
        raise LeaseLost()
    return mailbox


def _admin(actor):
    if actor is not None and (not actor.is_active or actor.role != "ADMIN"):
        raise PermissionDenied("Integracją może zarządzać wyłącznie aktywny administrator.")


def _state_error(mailbox_id, token, error):
    with transaction.atomic():
        mailbox = _locked(mailbox_id, token)
        mailbox.error_code = error.code
        mailbox.error_message = error.message
        mailbox.failures += 0 if error.message_specific else 1
        mailbox.state = "error"
        mailbox.next_attempt_at = timezone.now() + timedelta(seconds=min(3600, 60 * 2 ** min(mailbox.failures - 1, 6)))
        if (error.permanent and not error.message_specific) or mailbox.failures >= 3:
            mailbox.enabled = False
            mailbox.next_attempt_at = None
        mailbox.lease_token = None
        mailbox.lease_expires = None
        mailbox.queued_until = None
        mailbox.save()



def _configuration_failed(mailbox_id):
    """Invalid server settings may prevent reserving; fail closed without networking."""
    with transaction.atomic():
        mailbox = Mailbox.objects.select_for_update().filter(pk=mailbox_id, kind="imap").first()
        if mailbox is None:
            return
        if mailbox.error_code == "configuration" and not mailbox.enabled and mailbox.lease_token is None:
            return
        mailbox.enabled = False
        mailbox.state = "error"
        mailbox.error_code = "configuration"
        mailbox.error_message = "Konfiguracja IMAP jest nieprawidłowa. Administrator wdrożenia musi ją poprawić, a ADMIN świadomie wznowić import."
        mailbox.lease_token = mailbox.lease_expires = mailbox.queued_until = None
        mailbox.next_attempt_at = None
        mailbox.version += 1
        mailbox.save()

def test_connection(actor=None):
    _admin(actor)
    try:
        if actor is not None:
            mailbox = current_mailbox()
            with transaction.atomic():
                mailbox = Mailbox.objects.select_for_update().get(pk=mailbox.pk)
                now = timezone.now()
                if mailbox.last_requested and mailbox.last_requested > now - timedelta(seconds=30):
                    return {"ok": False, "state": mailbox.state, "error_code": "rate_limited",
                            "error_message": "Odczekaj 30 sekund przed kolejnym testem połączenia."}
                mailbox.last_requested = now
                mailbox.save(update_fields=["last_requested"])
        config = load_config()
        with IMAPClient(config) as client:
            folder = client.open_folder()
        if actor:
            mailbox = current_mailbox()
            record(actor, "mail_connection_tested", "mailbox", mailbox.pk, metadata={"ok": True})
        return {"ok": True, "state": "connected", "error_code": "", "error_message": "",
                "uidvalidity": folder.uidvalidity, "uidnext": folder.uidnext}
    except MailConfigurationError:
        return {"ok": False, "state": "error", "error_code": "configuration", "error_message": "Uzupełnij konfigurację IMAP i sekret na serwerze. Test nie uruchamia importu."}
    except MailError as exc:
        return {"ok": False, "state": "error", "error_code": exc.code, "error_message": exc.message}


def control(action, actor, version, mailbox_id=None):
    _admin(actor)
    if actor is None:
        raise PermissionDenied("Zmiana integracji wymaga administratora.")
    if action not in {"start", "pause", "rebuild"}:
        raise ValidationError({"action": "Nieobsługiwana zmiana stanu integracji."})
    if action == "pause":
        config = None
        if mailbox_id is not None:
            mailbox = Mailbox.objects.filter(pk=mailbox_id, kind="imap").first()
        else:
            try:
                mailbox = current_mailbox()
            except MailConfigurationError:
                mailbox = Mailbox.objects.filter(kind="imap").order_by("-enabled", "-id").first()
        if mailbox is None:
            raise ValidationError({"detail": "Nie znaleziono źródła IMAP do wstrzymania."})
    else:
        try:
            config = load_config()
            mailbox = current_mailbox()
        except MailConfigurationError as exc:
            raise ValidationError({"detail": str(exc)}) from exc
        if mailbox_id is not None and mailbox.pk != mailbox_id:
            raise ValidationError({"detail": "To źródło nie jest aktualną konfiguracją IMAP."})
    with transaction.atomic():
        mailbox = Mailbox.objects.select_for_update().get(pk=mailbox.pk)
        _admin(actor)
        if mailbox.version != version:
            raise VersionConflict("Stan integracji zmienił się. Wczytaj aktualne dane.")
        if action != "pause":
            if not config.enabled:
                raise ValidationError({"detail": "Administrator wdrożenia musi jawnie ustawić MAIL_SYNC_ENABLED=true. Synchronizacja zewnętrzna jest wyłączona."})
            try:
                config.validate_connection()
            except MailConfigurationError as exc:
                raise ValidationError({"detail": str(exc)}) from exc
            if mailbox.state == "resync_required" and action != "rebuild":
                raise ValidationError({"detail": "Zmieniła się UIDVALIDITY. Wymagane jest jawne odbudowanie synchronizacji."})
            if action == "rebuild" and mailbox.state != "resync_required":
                raise ValidationError({"detail": "Odbudowanie jest dostępne po wykrytej zmianie UIDVALIDITY."})
        mailbox.enabled = action != "pause"
        mailbox.state = "resync_required" if action == "pause" and mailbox.pending_uidvalidity else "paused" if action == "pause" else "rebuilding" if action == "rebuild" else "ready"
        if mailbox.state != "resync_required":
            mailbox.error_code = mailbox.error_message = ""
        mailbox.failures = 0
        mailbox.next_attempt_at = None
        mailbox.queued_until = None
        mailbox.lease_token = None
        mailbox.lease_expires = None
        if action == "rebuild":
            mailbox.rebuild_requested = True
        mailbox.version += 1
        mailbox.save()
        record(actor, f"mail_sync_{action}", "mailbox", mailbox.pk, metadata={"version": mailbox.version})
        if mailbox.enabled:
            transaction.on_commit(lambda: request_sync(actor=None))
    return mailbox


def request_sync(actor=None):
    if actor is not None:
        _admin(actor)
    try:
        config = load_config()
        mailbox = current_mailbox()
    except MailConfigurationError:
        for mailbox_id in Mailbox.objects.filter(kind="imap", enabled=True).values_list("pk", flat=True):
            _configuration_failed(mailbox_id)
        return {"queued": False, "state": "error", "error_code": "configuration"}
    if not config.enabled:
        return {"queued": False, "state": "disabled"}
    now = timezone.now()
    with transaction.atomic():
        mailbox = Mailbox.objects.select_for_update().get(pk=mailbox.pk)
        if not mailbox.enabled:
            return {"queued": False, "state": mailbox.state}
        if ((mailbox.lease_expires and mailbox.lease_expires > now)
                or (mailbox.queued_until and mailbox.queued_until > now)
                or (mailbox.next_attempt_at and mailbox.next_attempt_at > now)
                or (actor is not None and mailbox.last_requested and mailbox.last_requested > now - timedelta(seconds=30))):
            return {"queued": False, "state": mailbox.state}
        mailbox.last_requested = now
        mailbox.queued_until = now + timedelta(seconds=120)
        mailbox.save(update_fields=["last_requested", "queued_until"])
    try:
        from .tasks import sync_mailbox
        sync_mailbox.delay(mailbox.pk)
    except Exception:
        with transaction.atomic():
            current = Mailbox.objects.select_for_update().get(pk=mailbox.pk)
            if current.queued_until == mailbox.queued_until:
                current.queued_until = None
                current.state = "error"
                current.error_code = "queue_unavailable"
                current.error_message = "Nie można zlecić odbioru. Sprawdź Redis i proces roboczy poczty."
                current.save(update_fields=["queued_until", "state", "error_code", "error_message"])
        return {"queued": False, "state": "error", "error_code": "queue_unavailable"}
    return {"queued": True, "state": mailbox.state}


def reserve(mailbox_id, config):
    now = timezone.now()
    with transaction.atomic():
        mailbox = Mailbox.objects.select_for_update().get(pk=mailbox_id)
        if not config.enabled or not mailbox.enabled or mailbox.kind != "imap" or mailbox.config_fingerprint != config.fingerprint:
            return None
        if (mailbox.lease_expires and mailbox.lease_expires > now) or (mailbox.next_attempt_at and mailbox.next_attempt_at > now):
            return None
        mailbox.lease_token = uuid.uuid4()
        mailbox.lease_expires = now + timedelta(seconds=config.lease_seconds)
        mailbox.last_attempt = now
        mailbox.queued_until = None
        mailbox.state = "syncing"
        mailbox.save(update_fields=["lease_token", "lease_expires", "last_attempt", "queued_until", "state"])
        return mailbox.lease_token


def _initialize(mailbox_id, token, info):
    with transaction.atomic():
        mailbox = _locked(mailbox_id, token)
        if mailbox.rebuild_requested:
            history = list(mailbox.recovery_history)
            history.append({"uidvalidity": mailbox.uidvalidity, "boundary_uid": mailbox.boundary_uid,
                            "discovered_uid": mailbox.discovered_uid, "at": timezone.now().isoformat()})
            mailbox.recovery_history = history
            mailbox.uidvalidity = info.uidvalidity
            mailbox.boundary_uid = mailbox.discovered_uid = 0
            mailbox.rebuild_requested = False
            mailbox.rebuilding = True
            mailbox.pending_uidvalidity = None
        elif mailbox.uidvalidity is None:
            # UIDNEXT from the first successful EXAMINE establishes one boundary.
            # Mail arriving after that response has a higher UID and is imported.
            mailbox.uidvalidity = info.uidvalidity
            mailbox.boundary_uid = mailbox.discovered_uid = info.uidnext - 1
        elif mailbox.uidvalidity != info.uidvalidity:
            mailbox.pending_uidvalidity = info.uidvalidity
            mailbox.enabled = False
            mailbox.state = "resync_required"
            mailbox.error_code = "uidvalidity_changed"
            mailbox.error_message = "UIDVALIDITY folderu zmieniła się. Wymagane jawne odbudowanie synchronizacji; dotychczasowa historia jest zachowana."
            mailbox.lease_token = None
            mailbox.lease_expires = None
            mailbox.version += 1
            mailbox.save()
            return None
        mailbox.save()
        return mailbox


def _persist_discovered(mailbox_id, token, info, uids, high, batch_size):
    from .models import Message
    with transaction.atomic():
        mailbox = _locked(mailbox_id, token)
        low = (mailbox.discovered_uid or 0) + 1
        bounded = sorted({uid for uid in uids if low <= uid <= high})
        selected = bounded[:batch_size]
        for uid in selected:
            Message.objects.get_or_create(mailbox=mailbox, folder=mailbox.folder, uidvalidity=info.uidvalidity, uid=uid,
                                          defaults={"recovery_status": "review" if mailbox.rebuilding else "none"})
        # Cursor advances only after every UID it covers is durably represented.
        mailbox.discovered_uid = selected[-1] if len(bounded) > len(selected) and selected else high
        mailbox.save(update_fields=["discovered_uid"])


def _mark_message_failure(mailbox_id, token, message_id, error, retry_limit):
    from .models import Message
    with transaction.atomic():
        _locked(mailbox_id, token)
        message = Message.objects.select_for_update().get(pk=message_id)
        if message.fetch_state == "ready":
            return
        message.fetch_state = "error"
        message.fetch_error = error.message
        message.next_retry_at = None if error.permanent or message.fetch_attempts >= retry_limit else timezone.now() + timedelta(seconds=60 * 2 ** max(0, message.fetch_attempts - 1))
        message.save(update_fields=["fetch_state", "fetch_error", "next_retry_at"])


def _recovery_candidates(mailbox_id, token, message_id):
    from .models import Message
    with transaction.atomic():
        mailbox = _locked(mailbox_id, token)
        if not mailbox.rebuilding:
            return
        message = Message.objects.select_for_update().get(pk=message_id)
        if message.fetch_state != "ready":
            return
        candidates = Message.objects.filter(mailbox=mailbox, folder=mailbox.folder, raw_sha256=message.raw_sha256,
            raw_size=message.raw_size, received_at=message.received_at, sender_address=message.sender_address,
            subject=message.subject, fetch_state="ready").exclude(uidvalidity=message.uidvalidity)
        message.recovery_candidates = list(candidates.order_by("id").values_list("pk", flat=True)[:25])
        message.recovery_status = "review"
        message.save(update_fields=["recovery_candidates", "recovery_status"])


def synchronize(mailbox_id):
    from .ingest import import_bytes
    from .models import Message
    token = None
    try:
        config = load_config(load_secret=False)
        token = reserve(mailbox_id, config)
        if token is None:
            return {"status": "not_reserved"}
        config = load_config()
        started = time.monotonic()
        with IMAPClient(config) as client:
            info = client.open_folder()
            mailbox = _initialize(mailbox_id, token, info)
            if mailbox is None:
                return {"status": "resync_required"}
            low = (mailbox.discovered_uid or 0) + 1
            high = min(info.uidnext - 1, low + config.uid_window - 1)
            if low <= high:
                uids = client.search_uids(low, high)
                _persist_discovered(mailbox_id, token, info, uids, high, config.batch_size)
            now = timezone.now()
            with transaction.atomic():
                _locked(mailbox_id, token)
                Message.objects.filter(mailbox_id=mailbox_id, uidvalidity=info.uidvalidity,
                    fetch_state="pending", fetch_attempts__gte=config.retry_limit).update(fetch_state="error",
                        fetch_error="Odbiór był wielokrotnie przerywany; limit automatycznych prób został wyczerpany.", next_retry_at=None)
            ids = list(Message.objects.filter(mailbox_id=mailbox_id, folder=config.folder, uidvalidity=info.uidvalidity)
                .filter(Q(fetch_state="pending") | Q(fetch_state="error", next_retry_at__lte=now))
                .filter(fetch_attempts__lt=config.retry_limit).order_by("uid").values_list("pk", flat=True)[:config.batch_size])
            for message_id in ids:
                if time.monotonic() - started > 175:
                    break
                with transaction.atomic():
                    mailbox = _locked(mailbox_id, token)
                    message = Message.objects.select_for_update().get(pk=message_id)
                    if message.fetch_state == "ready":
                        continue
                    message.fetch_attempts += 1
                    message.save(update_fields=["fetch_attempts"])
                try:
                    fetched = client.fetch_message(message.uid)
                    import_bytes(message_id, fetched.raw, received_at=fetched.received_at, token=token)
                    _recovery_candidates(mailbox_id, token, message_id)
                except MailError as exc:
                    _mark_message_failure(mailbox_id, token, message_id, exc, config.retry_limit)
                    if not exc.message_specific or exc.code == "response_too_large":
                        raise
                except LeaseLost:
                    raise
                except SoftTimeLimitExceeded as exc:
                    error = MailError("time_limit", "Przekroczono limit czasu przebiegu. Niedokończona wiadomość zostanie ponowiona.")
                    _mark_message_failure(mailbox_id, token, message_id, error, config.retry_limit)
                    raise error from exc
                except Exception:
                    # Parser/storage details may contain untrusted message content.
                    # Record only a fixed problem label, retain the pending identity.
                    _mark_message_failure(mailbox_id, token, message_id,
                        MailError("import_error", "Nie udało się utrwalić lub przetworzyć wiadomości. Wymagane ponowienie."), config.retry_limit)
        with transaction.atomic():
            mailbox = _locked(mailbox_id, token)
            mailbox.last_success = timezone.now()
            mailbox.failures = 0
            mailbox.error_code = mailbox.error_message = ""
            mailbox.state = "connected"
            if mailbox.rebuilding and (mailbox.discovered_uid or 0) >= info.uidnext - 1:
                has_retries = Message.objects.filter(mailbox_id=mailbox_id, uidvalidity=info.uidvalidity).filter(
                    Q(fetch_state="pending") | Q(fetch_state="error", next_retry_at__isnull=False)).exists()
                if not has_retries:
                    mailbox.rebuilding = False
            mailbox.next_attempt_at = None
            mailbox.lease_token = mailbox.lease_expires = None
            mailbox.save()
        return {"status": "completed"}
    except LeaseLost:
        return {"status": "lease_lost"}
    except (MailConfigurationError, MailError) as exc:
        error = exc if isinstance(exc, MailError) else MailError("configuration", "Konfiguracja serwera IMAP jest niekompletna lub nieprawidłowa.", permanent=True)
        if token:
            try:
                _state_error(mailbox_id, token, error)
            except LeaseLost:
                pass
        elif isinstance(exc, MailConfigurationError):
            _configuration_failed(mailbox_id)
        return {"status": "error", "error_code": error.code}
    except Exception:
        if token:
            try:
                _state_error(mailbox_id, token, MailError("sync_error", "Odbiór przerwano. Sprawdź proces roboczy i ponów po usunięciu problemu."))
            except LeaseLost:
                pass
        return {"status": "error", "error_code": "sync_error"}
