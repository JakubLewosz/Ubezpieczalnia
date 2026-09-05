"""Ograniczony numerowany wniosek brokerski z sześcioma sekcjami tematycznymi.

Brak słownika klientów, nazw plików i oczekiwanych odpowiedzi. Każde przypisanie
zachowuje rzeczywisty fragment strony; niejednoznaczne informacje pozostają puste.
"""
import re
import uuid

from .engine import SCHEMA, empty_field, normalized, typed_value

PROFILE = "broker_motor_application_v1"
ITEM_SCHEMA = [
    ("requested_scope", "Żądany zakres (wniosek)", "text", "", []),
    ("insured_sum", "Suma żądanego zakresu", "decimal", "PLN", []),
    ("variant", "Wariant / warunki zakresu", "text", "", []),
]
VEHICLE_EXTRA = ("seats", "Liczba miejsc", "integer", "", [])
ALLOWED_ROLES = {"policyholder", "insured", "owner"}


def schema(group):
    if group == "coverage_items":
        return ITEM_SCHEMA
    if group == "coverage":
        return [field for field in SCHEMA[group] if field[0] != "requested_scope"]
    if group == "vehicle":
        return [*SCHEMA[group], VEHICLE_EXTRA]
    return SCHEMA[group]


def blank_group(group, index, *, manual=False, user=None):
    group_id = str(uuid.uuid4())
    result = []
    for definition in schema(group):
        field = empty_field(group, index, definition)
        field["group_id"] = group_id
        if manual:
            from django.utils import timezone
            field.update(manual=True, method="manual", updated_by=user.username,
                         updated_at=timezone.now().isoformat(), origin={"kind": "manual_group"})
        result.append(field)
    return result


def blank_profile(*, manual=False, user=None):
    return [field for group in ["application", "participants", "vehicle", "coverage", "coverage_items", "previous", "payment"]
            for field in blank_group(group, 0, manual=manual, user=user)]


def heading_kind(text):
    value = normalized(text)
    if re.match(r"ubezpieczajacy|ubezpieczony|ubezpieczeni", value):
        return "participants"
    if re.match(r"przedmiot\s+ubezpieczenia|dane\s+pojazdu", value):
        return "vehicle"
    if re.match(r"(?:rodzaj[,\s]*)?zakres|rodzaj.*ubezpieczenia", value):
        return "coverage_items"
    if re.match(r"okres\s+(?:ubezpieczenia|ochrony)", value):
        return "coverage"
    if re.match(r"informacje\s+o\s+kliencie|poprzednie\s+ubezpieczenie", value):
        return "previous"
    if re.match(r"warunki\s+platnosci|platnosc|sposob\s+platnosci", value):
        return "payment"
    return None


def extract_numbered(pages):
    from .engine import ExtractionLimitError
    # Quoted passages and ordinary e-mail envelopes cannot establish this profile.
    eligible = []
    for page in pages:
        for line in page.text.splitlines():
            if line.lstrip().startswith((">", '"', "„")):
                continue
            eligible.append((page, line))
    text = normalized("\n".join(line for _, line in eligible))
    if re.search(r"^(?:od|from|temat|subject|do|to):", text, re.M):
        return None
    title = re.search(r"^\s*wniosek\s+brokerski(?:\s+komunikacyjny)?\s+(?:nr\.?|numer)\s*[:.]?\s*\S+", text, re.M)
    if not title or re.search(r"^\s*(?:polisa|umowa ubezpieczenia|wniosek (?:ubezpieczenia )?(?:domu|mieszkania|nieruchomosci))\b", text, re.M):
        return None
    segments = []
    current = None
    for page, line in eligible:
        match = re.match(r"^\s*(?:\d{1,2}|[IVX]{1,4})\s*[.)-]\s*(.+)$", line, re.I)
        kind = heading_kind(match[1]) if match else None
        if kind:
            current = {"kind": kind, "lines": [(page, line)], "heading": match[1]}
            segments.append(current)
        elif current:
            current["lines"].append((page, line))
    kinds = {item["kind"] for item in segments}
    subject = " ".join(line for seg in segments if seg["kind"] == "vehicle" for _, line in seg["lines"])
    if not {"participants", "vehicle", "coverage_items", "coverage"}.issubset(kinds):
        return None
    if not re.search(r"\bsamochod\s+(?:osobowy|ciezarowy)|\bmotocykl\b", normalized(subject)) or not re.search(r"\bvin\b|\bnr\.?\s*rej", normalized(subject)):
        return None
    fields = blank_profile()
    by_key = {(f["group"], f["index"], f["code"]): f for f in fields}

    def put(group, code, raw, page, source, index=0):
        field = by_key[group, index, code]
        try:
            value = typed_value(raw.strip().rstrip(".;"), field["type"])
        except ValueError:
            value = None
        if field.get("conflict"):
            return
        if field["value"] is not None and value != field["value"]:
            field.update(value=None, conflict=True, source_conflict=True, warnings=["Sprzeczne wartości w źródle; sprawdź ręcznie."])
            return
        field.update(value=value, page=page.number, source=source.strip()[:2000], method=page.method,
                     absent=normalized(raw.strip().rstrip(".;")) in {"brak", "nie podano", "nie dotyczy"},
                     warnings=(["Tekst z OCR; sprawdź znaki w źródle."] if page.method == "ocr" and value is not None
                               else ["Wartość niewskazana lub niejednoznaczna w źródle."] if value is None else []))

    def find(group, code, pattern, lines, index=0, flags=re.I):
        for page, line in lines:
            match = re.search(pattern, line, flags)
            if match:
                put(group, code, match[1], page, match[0], index)

    find("application", "application_number", r"Wniosek\s+brokerski(?:\s+komunikacyjny)?\s+(?:nr\.?|numer)\s*[:.]?\s*([^\s,;]+)", eligible)
    # A place followed by a date is document metadata, never the insurance period.
    before_sections = eligible[:next((i for i, (_, line) in enumerate(eligible) if re.match(r"\s*(?:\d+|[IVX]+)[.)-]", line)), len(eligible))]
    find("application", "document_date", r"(?:,|data\s+(?:dokumentu|wniosku)\s*:?)\s*(\d{4}-\d{2}-\d{2}|\d{1,2}[./]\d{1,2}[./]\d{4})", before_sections)
    participant_index = -1
    item_index = -1
    for segment in segments:
        kind, lines = segment["kind"], segment["lines"]
        if kind == "participants":
            participant_index += 1
            if participant_index >= 100:
                raise ExtractionLimitError("Dokument przekracza limit 100 uczestników profilu pilotażowego.")
            if participant_index:
                new = blank_group(kind, participant_index)
                fields.extend(new)
                by_key.update({(f["group"], f["index"], f["code"]): f for f in new})
            roles = []
            h = normalized(segment["heading"])
            if re.search(r"ubezpieczajacy", h):
                roles.append("policyholder")
            if re.search(r"ubezpieczon[yi]", h):
                roles.append("insured")
            put(kind, "role", ",".join(roles), lines[0][0], lines[0][1], participant_index)
            body = [(p, line) for p, line in lines[1:] if line.strip()]
            tail = segment["heading"].partition(":")[2].strip()
            if tail:
                body.insert(0, (lines[0][0], tail))
            if body:
                page, first = body[0]
                candidate, separator, address = first.partition(",")
                # Restrict unlabelled name to letters/hyphens and at least two words.
                candidate = re.sub(r"^(?:imi[eę] i nazwisko|nazwa)\s*:\s*", "", candidate, flags=re.I).strip()
                if re.fullmatch(r"[^\W\d_]+(?:[ -][^\W\d_]+){1,5}", candidate, re.UNICODE):
                    put(kind, "name", candidate, page, first, participant_index)
                if separator and re.search(r"\d{2}-\d{3}|\bul\.", address):
                    put(kind, "address", address.strip(), page, first, participant_index)
            for code, pattern in {
                "pesel": r"PESEL\s*:\s*(nie\s+podano|brak|\d+)",
                "nip": r"NIP\s*:\s*(nie\s+podano|brak|[\d-]+)",
                "phone": r"(?:Tel(?:efon)?\.?)\s*[:.]?\s*([+\d][\d ()-]{5,})",
                "email": r"(?:e-mail|email)\s*:\s*([^\s,;]+)",
                "address": r"Adres\s*:\s*(.+)",
            }.items():
                find(kind, code, pattern, lines, participant_index)
        elif kind == "vehicle":
            for code, pattern in {
                "registration": r"(?:nr\.?\s*rej(?:estracyjny)?\.?|numer rejestracyjny)\s*[:.]?\s*([A-Z0-9-]+)",
                "vin": r"(?:nr\.?\s*)?VIN\s*:\s*([^\s,;.]+)",
                "year": r"rok\s*prod(?:ukcji)?\.?\s*[:.]?\s*(\d{4})",
                "seats": r"liczba\s+miejsc\s*[:.]?\s*(\d+)",
                "make": r"marka\s*:\s*([^,;]+)",
                "model": r"model\s*:\s*([^,;]+)",
            }.items():
                find(kind, code, pattern, lines)
            for page, line in lines:
                match = re.search(r"(?:samoch[oó]d\s+(?:osobowy|ci[eę][żz]arowy)|motocykl)\s+([^,;]+)", line, re.I)
                if match and not by_key[kind, 0, "make"]["value"] and not by_key[kind, 0, "model"]["value"]:
                    tokens = match[1].strip().split()
                    if len(tokens) == 2 and all(re.fullmatch(r"[\w-]+", t) for t in tokens):
                        put(kind, "make", tokens[0], page, match[0])
                        put(kind, "model", tokens[1], page, match[0])
        elif kind == "coverage":
            dates = []
            for page, line in lines:
                dates.extend((m[0], page, line) for m in re.finditer(r"\d{4}-\d{2}-\d{2}|\d{1,2}[./]\d{1,2}[./]\d{4}", line))
            if len(dates) == 2:
                for code, (value, page, line) in zip(["start_date", "end_date"], dates, strict=True):
                    put(kind, code, value, page, line)
        elif kind == "coverage_items":
            for page, line in lines:
                match = re.match(r"\s*(?:[a-z]\s*[.)]|[-•])?\s*(OC|AC|NNW|Assistance)\b\s*[:—–-]?\s*(.*)", line, re.I)
                if not match:
                    continue
                item_index += 1
                if item_index >= 30:
                    raise ExtractionLimitError("Dokument przekracza limit 30 pozycji żądanego zakresu.")
                if item_index:
                    new = blank_group(kind, item_index)
                    fields.extend(new)
                    by_key.update({(f["group"], f["index"], f["code"]): f for f in new})
                put(kind, "requested_scope", match[1], page, line, item_index)
                amount = re.fullmatch(r"([\d][\d .\u00a0,]*\s*(?:PLN|zł))\.?", match[2].strip(), re.I)
                if amount:
                    put(kind, "insured_sum", amount[1], page, line, item_index)
                elif match[2].strip():
                    put(kind, "variant", match[2], page, line, item_index)
                    if re.match(r"\d", match[2].strip()):
                        put(kind, "insured_sum", match[2], page, line, item_index)
                        by_key[kind, item_index, "insured_sum"]["unit_conflict"] = True
                        by_key[kind, item_index, "insured_sum"]["warnings"] = ["Niejednoznaczna kwota lub jednostka w źródle; przepisz po sprawdzeniu."]
        elif kind == "previous":
            find(kind, "insurer", r"(?:ostatni|poprzedni)\s+ubezpieczyciel\s*:\s*([^();]+)", lines)
            find(kind, "policy_number", r"\(\s*polisa\s*(?:nr\.?)?\s*[:.]?\s*([^()\s]+)\s*\)", lines)
        elif kind == "payment":
            for page, line in lines:
                match = re.search(r"(?:warunki|spos[oó]b)\s+płatno[śs]ci\s*:\s*(.+)", line, re.I)
                if match:
                    put(kind, "payment_method", match[1], page, line)
            if not by_key[kind, 0, "payment_method"]["value"] and len(lines) > 1:
                put(kind, "payment_method", lines[1][1], lines[1][0], lines[1][1])
    for field in fields:
        field.pop("conflict", None)
    return {"profile": PROFILE, "fields": fields,
            "warnings": ["Ograniczony numerowany wniosek brokerski komunikacyjny. Dane wymagają sprawdzenia; to nie jest zawarta polisa."],
            "pages": [{"number": page.number, "method": page.method} for page in pages]}
