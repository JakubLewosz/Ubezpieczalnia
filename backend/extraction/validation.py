"""Bieżąca walidacja szkicu; zgodność formatu nie dowodzi prawdziwości danych."""
import hashlib
import json
import re
from decimal import InvalidOperation

from .engine import typed_value


def field_identity(field):
    return f"{field.get('group_id', field['group'] + ':' + str(field['index']))}:{field['code']}"


def draft_warnings(fields):
    warnings = []

    def warn(field, code, message, note=False):
        identity = field_identity(field)
        warnings.append({"id": f"{identity}:{code}", "field": identity, "code": code,
                         "message": f"{field['label']} (pozycja {field['index'] + 1}): {message}", "requires_note": note})

    dates = {}
    for field in fields:
        value, code = field.get("value"), field["code"]
        if field.get("source_conflict") or (field.get("method") != "manual" and any("sprzeczne" in str(w).lower() for w in field.get("warnings", []))):
            warn(field, "source_conflict", "sprzeczne wartości w dokumencie.", True)
        if field.get("unit_conflict"):
            warn(field, "ambiguous_amount_unit", "kwota lub jednostka w źródle jest niejednoznaczna; sprawdź fragment dokumentu.", True)
        if value is None:
            if not field.get("absent"):
                warn(field, "missing", "nie odczytano wartości; uzupełnij albo oznacz brak w dokumencie.")
            continue
        if not value.strip():
            warn(field, "empty", "pusty tekst nie oznacza zera ani potwierdzonego braku w dokumencie.")
        if field["type"] != "text":
            try:
                parsed = typed_value(value, field["type"])
                if parsed is None:
                    raise ValueError
                if field["type"] == "date":
                    dates[code] = (parsed, field)
            except (ValueError, InvalidOperation):
                warn(field, "invalid_type_value", f"wartość nie ma prawidłowego formatu {field['type']}; przy wiernym przepisaniu błędu ze źródła podaj notatkę.", True)
        if code == "vin" and not re.fullmatch(r"[A-HJ-NPR-Z0-9]{17}", value.upper()):
            warn(field, "invalid_vin", "VIN wymaga 17 znaków bez I, O, Q; sprawdź źródło.", True)
        if code == "email" and not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", value):
            warn(field, "invalid_email", "nieprawidłowy format adresu e-mail.", True)
        if code in {"pesel", "nip"}:
            length = 11 if code == "pesel" else 10
            if not re.fullmatch(r"\d{" + str(length) + "}", value):
                warn(field, "invalid_identifier", f"identyfikator powinien zawierać {length} cyfr; walidacja formatu nie potwierdza jego prawdziwości.", True)
        if field["type"] == "decimal" and field.get("unit") != "PLN":
            warn(field, "invalid_unit", "ten profil obsługuje kwoty PLN; sprawdź jednostkę.", True)
        if field.get("method") == "ocr":
            warn(field, "ocr_source", "wartość pochodzi z OCR; sprawdź znaki w źródle.")
    if dates.get("end_date") and dates.get("start_date") and dates["end_date"][0] < dates["start_date"][0]:
        warn(dates["end_date"][1], "date_order", "koniec ochrony poprzedza jej początek.", True)
    for group in (["participants", "coverage_items"] if any(f.get("group") == "coverage_items" for f in fields) or not any(f.get("code") == "requested_scope" for f in fields) else ["participants"]):
        if not any(field["group"] == group for field in fields):
            warnings.append({"id": f"{group}:missing_group", "field": None, "code": "missing_group",
                             "message": f"Brak grupy {group}; sprawdź, czy pominięto strukturę dokumentu.", "requires_note": False})
    return warnings


def warning_digest(fields):
    payload = json.dumps(draft_warnings(fields), sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(payload.encode()).hexdigest()
