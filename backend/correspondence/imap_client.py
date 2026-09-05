"""Bounded IMAP4rev1 client: EXAMINE and BODY.PEEK, never changes provider flags."""
import imaplib
import re
import ssl
from dataclasses import dataclass
from datetime import timezone
from email.utils import parsedate_to_datetime

from .config import MailConfigurationError

MAX_UID = 2**32 - 1


class MailError(Exception):
    def __init__(self, code, message, *, permanent=False, message_specific=False):
        self.code, self.message = code, message
        self.permanent, self.message_specific = permanent, message_specific
        super().__init__(message)


class BoundedIMAP4SSL(imaplib.IMAP4_SSL):
    """Reject oversized literals before imaplib allocates/reads them."""
    def __init__(self, *args, max_literal, **kwargs):
        self.max_literal = max_literal
        self.response_budget = 1024 * 1024
        super().__init__(*args, **kwargs)
        self.debug = 0

    def _log(self, line):
        # imaplib's diagnostic ring can retain LOGIN commands and response bodies.
        # Disable it even if a caller accidentally changes debug later.
        return None

    def _mesg(self, *args, **kwargs):
        return None

    def _command(self, name, *args):
        allowed = {"CAPABILITY", "LOGIN", "EXAMINE", "LOGOUT", "UID"}
        if name not in allowed or (name == "UID" and (not args or str(args[0]).upper() not in {"SEARCH", "FETCH"})):
            raise MailError("forbidden_command", "Klient odbioru nie obsługuje polecenia zmieniającego pocztę.", permanent=True)
        return super()._command(name, *args)

    def read(self, size):
        if size > self.max_literal or size > self.response_budget or size < 0:
            raise MailError("response_too_large", "Odpowiedź IMAP przekracza limit wiadomości przed odczytem treści.", permanent=True, message_specific=True)
        self.response_budget -= size
        payload = super().read(size)
        if len(payload) != size:
            raise MailError("connection_lost", "Połączenie przerwano w trakcie odbioru wiadomości.")
        return payload

    def readline(self):
        line = self.file.readline(min(65536, self.response_budget) + 1)
        if len(line) > 65536 or len(line) > self.response_budget:
            raise MailError("protocol_limit", "Odpowiedź serwera IMAP przekracza limit protokołu.")
        self.response_budget -= len(line)
        return line


@dataclass(frozen=True)
class FolderInfo:
    uidvalidity: int
    uidnext: int


@dataclass(frozen=True)
class FetchedMessage:
    raw: bytes
    received_at: object
    size: int


class IMAPClient:
    def __init__(self, config):
        self.config = config
        self.connection = None

    def __enter__(self):
        self.config.validate_connection()
        try:
            context = ssl.create_default_context()
            if self.config.ca_file:
                try:
                    context.load_verify_locations(cafile=self.config.ca_file)
                except (OSError, ssl.SSLError) as exc:
                    raise MailConfigurationError("Nie można wczytać zaufanego certyfikatu CA. Administrator wdrożenia musi sprawdzić konfigurację.") from exc
            self.connection = BoundedIMAP4SSL(self.config.host, self.config.port,
                ssl_context=context, timeout=self.config.timeout, max_literal=self.config.max_message_bytes)
            self.connection.sock.settimeout(self.config.timeout)
            self._call("login", self.config.username, self.config.password)
        except MailError:
            self.__exit__(None, None, None)
            raise
        except ssl.SSLCertVerificationError as exc:
            self.__exit__(None, None, None)
            raise MailError("tls_certificate", "Nie zweryfikowano certyfikatu TLS. Sprawdź konfigurację serwera i zaufany urząd certyfikacji.", permanent=True) from exc
        except ssl.SSLError as exc:
            self.__exit__(None, None, None)
            raise MailError("tls_error", "Nie udało się uzgodnić bezpiecznego połączenia TLS. Sprawdź konfigurację przed wznowieniem importu.", permanent=True) from exc
        except (OSError, imaplib.IMAP4.error) as exc:
            self.__exit__(None, None, None)
            raise MailError("connection_error", "Nie udało się bezpiecznie połączyć z serwerem IMAP. Sprawdź ustawienia i łączność.") from exc
        return self

    def __exit__(self, exc_type, exc, traceback):
        if self.connection:
            try:
                # LOGOUT only. CLOSE/EXPUNGE are intentionally never used.
                self.connection.response_budget = 65536
                self.connection.logout()
            except Exception:
                try:
                    self.connection.shutdown()
                except Exception:
                    pass
            self.connection = None

    def _call(self, method, *args, body=False):
        self.connection.response_budget = self.config.max_message_bytes + 65536 if body else 1024 * 1024
        try:
            status, data = getattr(self.connection, method)(*args)
        except MailError:
            raise
        except imaplib.IMAP4.abort as exc:
            raise MailError("connection_lost", "Połączenie IMAP zostało przerwane. Odbiór zostanie ponowiony.") from exc
        except imaplib.IMAP4.error as exc:
            code = "authentication" if method == "login" else "protocol_error"
            message = "Serwer odrzucił logowanie. Sprawdź sekret i dostęp programu pocztowego; po poprawieniu wznów import." if method == "login" else "Serwer IMAP odrzucił operację odczytu. Sprawdź stan integracji."
            raise MailError(code, message, permanent=method == "login") from exc
        except ssl.SSLError as exc:
            raise MailError("tls_error", "Połączenie TLS zgłosiło błąd. Sprawdź konfigurację przed wznowieniem importu.", permanent=True) from exc
        except OSError as exc:
            raise MailError("connection_lost", "Połączenie IMAP zostało przerwane. Odbiór zostanie ponowiony.") from exc
        if status != "OK":
            raise MailError("protocol_error", "Serwer IMAP nie potwierdził operacji odczytu.")
        return data

    def open_folder(self):
        quoted = '"' + self.config.folder.replace("\\", "\\\\").replace('"', '\\"') + '"'
        # imaplib select(readonly=True) uses EXAMINE in rev1 and rev2.
        self.connection.response_budget = 1024 * 1024
        try:
            status, _ = self.connection.select(quoted, readonly=True)
            if status != "OK":
                raise MailError("folder_unavailable", "Nie można otworzyć skonfigurowanego folderu w trybie tylko do odczytu.", permanent=True)
            values = []
            for name in ["UIDVALIDITY", "UIDNEXT"]:
                _, items = self.connection.response(name)
                raw = items[0] if items else None
                if not raw or not re.fullmatch(rb"\d+", raw):
                    raise MailError("protocol_error", "Serwer nie podał wymaganej tożsamości UID folderu.")
                number = int(raw)
                if not 1 <= number <= MAX_UID:
                    raise MailError("protocol_error", "Serwer podał nieprawidłową tożsamość UID folderu.")
                values.append(number)
            return FolderInfo(*values)
        except ssl.SSLError as exc:
            raise MailError("tls_error", "Połączenie TLS zgłosiło błąd podczas otwierania folderu.", permanent=True) from exc
        except (OSError, imaplib.IMAP4.error) as exc:
            raise MailError("connection_lost", "Nie udało się odczytać stanu folderu IMAP.") from exc

    def search_uids(self, low, high):
        if low > high:
            return []
        if not 1 <= low <= high <= MAX_UID:
            raise MailConfigurationError("Nieprawidłowe granice UID.")
        data = self._call("uid", "SEARCH", None, "UID", f"{low}:{high}")
        uids = set()
        for chunk in data:
            if not isinstance(chunk, bytes):
                raise MailError("protocol_error", "Serwer zwrócił nieprawidłową listę UID.")
            for raw in chunk.split():
                if not re.fullmatch(rb"\d{1,10}", raw):
                    raise MailError("protocol_error", "Serwer zwrócił nieprawidłowy UID.")
                uid = int(raw)
                # Defend even against responses resembling the n:* old-last trap.
                if low <= uid <= high:
                    uids.add(uid)
        return sorted(uids)

    def fetch_message(self, uid):
        if not 1 <= uid <= MAX_UID:
            raise MailConfigurationError("Nieprawidłowy UID.")
        data = self._call("uid", "FETCH", str(uid), "(UID RFC822.SIZE INTERNALDATE)")
        envelope = next((item for item in data if isinstance(item, bytes) and re.search(rb"\bUID\s+" + str(uid).encode() + rb"\b", item)), None)
        if envelope is None:
            raise MailError("message_gone", "Wiadomość zniknęła z INBOX przed odczytem; mogła zostać przeniesiona lub usunięta w innym programie.", permanent=True, message_specific=True)
        size = re.search(rb"RFC822\.SIZE\s+(\d+)", envelope)
        internal = re.search(rb'INTERNALDATE\s+"([^"\r\n]+)"', envelope)
        if not size or not internal:
            raise MailError("protocol_error", "Serwer nie podał rozmiaru lub daty odbioru wiadomości.")
        size = int(size[1])
        if size > self.config.max_message_bytes:
            raise MailError("message_too_large", "Wiadomość przekracza limit rozmiaru. Treść nie została pobrana.", permanent=True, message_specific=True)
        try:
            received_at = parsedate_to_datetime(internal[1].decode("ascii").replace("-", " ", 2)).astimezone(timezone.utc)
        except (ValueError, TypeError, UnicodeError) as exc:
            raise MailError("protocol_error", "Data odbioru podana przez serwer ma nieprawidłowy format.") from exc
        data = self._call("uid", "FETCH", str(uid), "(UID BODY.PEEK[])", body=True)
        envelopes = b" ".join(item[0] if isinstance(item, tuple) and isinstance(item[0], bytes) else item for item in data if isinstance(item, bytes) or isinstance(item, tuple) and isinstance(item[0], bytes))
        response_uids = {int(value) for value in re.findall(rb"\bUID\s+(\d+)", envelopes)}
        payloads = [item[1] for item in data if isinstance(item, tuple) and isinstance(item[0], bytes) and b"BODY[" in item[0]]
        if response_uids != {uid} or len(payloads) != 1 or not isinstance(payloads[0], bytes):
            raise MailError("message_gone", "Nie otrzymano kompletnej wiadomości o żądanym UID.", message_specific=True)
        raw = payloads[0]
        if len(raw) > self.config.max_message_bytes:
            raise MailError("message_too_large", "Odebrana treść przekracza limit rozmiaru.", permanent=True, message_specific=True)
        if len(raw) != size:
            raise MailError("incomplete_message", "Rozmiar odebranej treści różni się od deklaracji serwera; wymagane ponowienie.", message_specific=True)
        return FetchedMessage(raw, received_at, size)
