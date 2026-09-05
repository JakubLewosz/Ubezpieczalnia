"""Konfiguracja wyłącznie z serwera. Żadne hasło nie jest polem modelu/API."""
import hashlib
import json
import os
from dataclasses import dataclass, field
from pathlib import Path

from django.conf import settings
from django.db import transaction


class MailConfigurationError(ValueError):
    pass


def setting_int(name, default, minimum, maximum):
    try:
        value = int(os.environ.get(name, default))
    except (ValueError, TypeError) as exc:
        raise MailConfigurationError(f"Nieprawidłowe ustawienie {name}.") from exc
    if not minimum <= value <= maximum:
        raise MailConfigurationError(f"Ustawienie {name} jest poza dozwolonym zakresem.")
    return value


@dataclass(frozen=True)
class MailConfig:
    enabled: bool = False
    host: str = "poczta.interia.pl"
    port: int = 993
    username: str = ""
    password: str = field(default="", repr=False)
    folder: str = "INBOX"
    ca_file: str = ""
    timeout: int = 20
    max_message_bytes: int = 30 * 1024 * 1024
    batch_size: int = 25
    uid_window: int = 5000
    lease_seconds: int = 240
    retry_limit: int = 3
    poll_seconds: int = 60

    @property
    def fingerprint(self):
        value = [self.host.casefold(), self.port, self.username.casefold(), self.folder]
        return hashlib.sha256(json.dumps(value, ensure_ascii=True).encode()).hexdigest()

    def validate_connection(self):
        if not self.username or not self.password:
            raise MailConfigurationError("Brak loginu lub pliku sekretu po stronie serwera. Administrator wdrożenia musi uzupełnić konfigurację.")
        if any(c in self.username or c in self.host or c in self.folder for c in ["\r", "\n", "\x00"]):
            raise MailConfigurationError("Konfiguracja zawiera niedozwolone znaki sterujące.")
        if not self.folder.isascii() or len(self.folder) > 255:
            raise MailConfigurationError("Demonstracja obsługuje nazwę folderu ASCII, domyślnie INBOX.")


def load_config(*, load_secret=True):
    if getattr(settings, "MAIL_CONFIGURATION_ERRORS", []):
        raise MailConfigurationError("Nieprawidłowa konfiguracja limitów poczty. Administrator wdrożenia musi poprawić ustawienia serwera.")
    password = os.getenv("MAIL_PASSWORD", "")
    password_file = os.getenv("MAIL_PASSWORD_FILE", "")
    if password_file and load_secret:
        try:
            path = Path(password_file)
            if path.stat().st_size > 16_384:
                raise MailConfigurationError("Plik sekretu poczty przekracza dozwolony rozmiar.")
            password = path.read_text().rstrip("\r\n")
        except (OSError, UnicodeError) as exc:
            raise MailConfigurationError("Nie można odczytać pliku sekretu poczty. Sprawdź ścieżkę i uprawnienia na serwerze.") from exc
    return MailConfig(
        enabled=os.getenv("MAIL_SYNC_ENABLED", "false").casefold() == "true",
        host=os.getenv("MAIL_HOST", "poczta.interia.pl"), port=setting_int("MAIL_PORT", 993, 1, 65535),
        username=os.getenv("MAIL_USERNAME", ""), password=password,
        folder=os.getenv("MAIL_FOLDER", "INBOX"), ca_file=os.getenv("MAIL_CA_FILE", ""),
        timeout=setting_int("MAIL_TIMEOUT_SECONDS", 20, 1, 60),
        max_message_bytes=setting_int("MAIL_MAX_RAW_BYTES", 30 * 1024 * 1024, 1024, 30 * 1024 * 1024),
        batch_size=setting_int("MAIL_BATCH_SIZE", 25, 1, 100), uid_window=setting_int("MAIL_UID_WINDOW", 5000, 1, 50000),
        lease_seconds=240, retry_limit=setting_int("MAIL_RETRY_LIMIT", 3, 1, 5),
        poll_seconds=setting_int("MAIL_POLL_SECONDS", 60, 15, 3600),
    )


def current_mailbox():
    from .sync_models import Mailbox
    config = load_config(load_secret=False)
    with transaction.atomic():
        # Serialize configuration selection, including activation of a new account.
        list(Mailbox.objects.select_for_update().filter(kind="imap").values_list("pk", flat=True))
        old = Mailbox.objects.filter(kind="imap").exclude(config_fingerprint=config.fingerprint)
        old.filter(enabled=True).update(enabled=False, state="configuration_changed", lease_token=None, lease_expires=None, queued_until=None)
        mailbox, _ = Mailbox.objects.get_or_create(key=f"imap:{config.fingerprint}", defaults={
            "kind": "imap", "config_fingerprint": config.fingerprint, "folder": config.folder,
        })
        if not config.enabled and mailbox.enabled:
            mailbox.enabled = False
            mailbox.state = "disabled"
            mailbox.lease_token = None
            mailbox.lease_expires = None
            mailbox.queued_until = None
            mailbox.version += 1
            mailbox.save()
        return mailbox
