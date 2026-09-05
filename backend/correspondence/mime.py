"""Bounded stdlib MIME decoding. Source bytes stay immutable; UI receives plain text only."""
from dataclasses import dataclass, field
from datetime import timezone as dt_timezone
from email import policy
from email.parser import BytesParser
from email.utils import getaddresses, parsedate_to_datetime
from html.parser import HTMLParser
from django.conf import settings
from exports.text import ExportValidationError, validate_xlsx_text


class MimeLimitError(ValueError):
    pass


def limit(name, default):
    return int(getattr(settings, name, default))


class PlainHTML(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []
        self.hidden = []

    def handle_starttag(self, tag, attrs):
        if tag in {"script", "style", "head", "template", "svg", "iframe", "object"}:
            self.hidden.append(tag)
        elif not self.hidden and tag in {"p", "div", "br", "li", "tr", "h1", "h2", "h3", "hr", "blockquote"}:
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if self.hidden:
            if tag == self.hidden[-1]:
                self.hidden.pop()
        elif tag in {"p", "div", "li", "tr", "blockquote"}:
            self.parts.append("\n")

    def handle_data(self, data):
        if not self.hidden:
            self.parts.append(data)


def visible_text(value, warnings):
    # Preserve exact headers/body in raw_file and declare this display-only normalization.
    normalized = value.replace("\r\n", "\n").replace("\r", "\n")
    clean = "".join(c if c in "\n\t" or ord(c) >= 32 else "�" for c in normalized)
    clean = clean.encode("utf-8", errors="replace").decode("utf-8")
    if clean != normalized and "Zastąpiono znaki sterujące w widoku; oryginał zachowany." not in warnings:
        warnings.append("Zastąpiono znaki sterujące w widoku; oryginał zachowany.")
    return clean


@dataclass
class Part:
    key: str
    name: str
    mime: str
    size: int = 0
    data: bytes | None = None
    blocked_reason: str = ""


@dataclass
class ParsedMail:
    subject: str = ""
    sender_name: str = ""
    sender_address: str = ""
    message_id: str = ""
    in_reply_to: str = ""
    references: list = field(default_factory=list)
    headers: list = field(default_factory=list)
    body_text: str = ""
    declared_at: object = None
    warnings: list = field(default_factory=list)
    attachments: list = field(default_factory=list)


def parse_mail(raw):
    if not isinstance(raw, bytes) or not raw:
        raise MimeLimitError("Pusta wiadomość.")
    if len(raw) > limit("MAIL_MAX_RAW_BYTES", 30 * 1024 * 1024):
        raise MimeLimitError("Wiadomość przekracza limit surowych bajtów.")
    header_end = raw.find(b"\r\n\r\n")
    if header_end < 0:
        header_end = raw.find(b"\n\n")
    if header_end < 0 or header_end > limit("MAIL_MAX_HEADER_BYTES", 128 * 1024):
        raise MimeLimitError("Brak końca nagłówków lub nagłówki przekraczają limit.")
    mail = BytesParser(policy=policy.default).parsebytes(raw)
    result = ParsedMail()
    warnings = result.warnings
    if mail.defects:
        warnings.append("Nagłówki lub struktura MIME zawierają błędy; sprawdź źródło.")
    def text(value):
        return visible_text(str(value or ""), warnings)
    result.headers = [[text(key), text(value)] for key, value in mail.items()]
    result.subject = text(mail.get("Subject"))
    try:
        senders = getaddresses([text(v) for v in mail.get_all("From", [])])
        if len(senders) == 1:
            result.sender_name, result.sender_address = senders[0]
            if len(result.sender_address) > 320:
                warnings.append("Adres nadawcy przekracza limit; nie proponujemy klienta.")
                result.sender_address = ""
        else:
            warnings.append("Brak jednoznacznego adresu nadawcy; sprawdź nagłówki.")
    except (ValueError, IndexError):
        warnings.append("Nie udało się odczytać adresu nadawcy.")
    mids = mail.get_all("Message-ID", [])
    if len(mids) != 1:
        warnings.append("Brak lub powielony nagłówek Message-ID. Tożsamość importu wynika z UID.")
    result.message_id = text(mids[0]) if len(mids) == 1 else ""
    result.in_reply_to = text(mail.get("In-Reply-To"))
    result.references = text(mail.get("References")).split()[:100]
    try:
        date = parsedate_to_datetime(str(mail.get("Date", "")))
        if date.tzinfo is None:
            warnings.append("Data nadawcy bez strefy; brak pewnej daty zadeklarowanej.")
        else:
            result.declared_at = date.astimezone(dt_timezone.utc)
    except (ValueError, TypeError, OverflowError):
        warnings.append("Brak poprawnej daty nadawcy; czas dostawcy przechowujemy osobno.")
    seen = 0
    attachment_total = 0
    max_parts = limit("MAIL_MAX_PARTS", 100)
    max_depth = limit("MAIL_MAX_DEPTH", 10)
    max_attachments = limit("MAIL_MAX_ATTACHMENTS", 30)
    max_attachment = min(limit("MAIL_MAX_ATTACHMENT_BYTES", settings.MAX_UPLOAD_BYTES), settings.MAX_UPLOAD_BYTES)
    max_total = limit("MAIL_MAX_DECODED_BYTES", 30 * 1024 * 1024)
    max_body = limit("MAIL_MAX_BODY_BYTES", 2 * 1024 * 1024)
    body_total = 0

    def blocked(key, name, mime, reason, size=0):
        result.attachments.append(Part(key, name, mime, size=size, blocked_reason=reason))

    def walk(node, key="1", depth=0):
        nonlocal seen, attachment_total, body_total
        seen += 1
        mime = node.get_content_type()
        original_name = node.get_filename()
        name = text(original_name) if original_name else f"część-{key}"
        name_problem = ""
        if original_name:
            try:
                validate_xlsx_text(original_name, "Nazwa załącznika")
                if len(original_name.replace("\\", "/").split("/")[-1]) > 255:
                    raise ExportValidationError("Nazwa przekracza 255 znaków.")
            except ExportValidationError:
                name_problem = "Nazwa załącznika ma niedozwolone znaki lub przekracza limit długości; źródło zachowano."
        if depth > max_depth:
            blocked(key, name, mime, "Przekroczono głębokość MIME; poddrzewo pominięte.")
            return ""
        if node.defects:
            warnings.append(f"Część {key}: uszkodzona struktura MIME lub kodowanie.")
        if mime == "message/rfc822" or node.get_content_maintype() == "message":
            blocked(key, name, mime, "Zagnieżdżone wiadomości nie są automatycznie otwierane.")
            return ""
        if node.is_multipart():
            texts = []
            for i, child in enumerate(node.iter_parts(), 1):
                if seen >= max_parts:
                    blocked(f"{key}.{i}", "Pozostałe części MIME", "application/octet-stream", "Przekroczono limit liczby części MIME.")
                    break
                texts.append((child.get_content_type(), walk(child, f"{key}.{i}", depth + 1)))
            if mime == "multipart/alternative":
                plain = [value for content_type, value in texts if content_type == "text/plain" and value.strip()]
                return "\n".join(plain or [value for _, value in texts])
            return "\n\n".join(value for _, value in texts if value.strip())
        data = node.get_payload(decode=True)
        if data is None:
            data = b""
        if node.defects:
            warnings.append(f"Część {key}: uszkodzona struktura MIME lub kodowanie.")
        is_attachment = bool(node.get_filename()) or node.get_content_disposition() == "attachment" or mime not in {"text/plain", "text/html"}
        if is_attachment:
            attachment_total += len(data)
            reason = name_problem
            if len(result.attachments) >= max_attachments:
                reason = "Przekroczono limit liczby załączników."
            elif len(data) > max_attachment:
                reason = "Załącznik przekracza limit pojedynczego dokumentu."
            elif attachment_total > max_total:
                reason = "Załączniki przekraczają łączny limit zdekodowanych danych."
            result.attachments.append(Part(key, name, mime, len(data), None if reason else data, reason))
            return ""
        body_total += len(data)
        if body_total > max_body:
            blocked(key, name, mime, "Treść przekracza limit wyświetlania; nie została obcięta po cichu.", len(data))
            return "[Część treści pominięta z powodu limitu; patrz ostrzeżenia załączników.]"
        charset = node.get_content_charset() or "utf-8"
        try:
            decoded = data.decode(charset, errors="strict")
        except (LookupError, UnicodeDecodeError):
            decoded = data.decode("utf-8", errors="replace")
            warnings.append(f"Część {key}: nieprawidłowy charset; widok używa UTF-8 z zastąpieniem błędów.")
        if mime == "text/html":
            converter = PlainHTML()
            converter.feed(decoded)
            decoded = "".join(converter.parts)
        return text(decoded)

    result.body_text = walk(mail)
    result.warnings = list(dict.fromkeys(warnings))
    return result
