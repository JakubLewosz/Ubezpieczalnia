"""Ograniczony profil treści; nie zależy od nazwy, hasha ani generatora dokumentu."""

import re
import unicodedata
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Protocol

PROFILE = "broker_motor_application_v0"
MAX_TEXT_BYTES = 1024 * 1024
MAX_PARTICIPANTS = 100


class ExtractionLimitError(ValueError):
    pass


@dataclass(frozen=True)
class PageText:
    number: int
    method: str
    text: str


class ExtractionEngine(Protocol):
    def extract(self, pages: list[PageText]) -> dict: ...


def normalized(value: str) -> str:
    return "".join(
        char for char in unicodedata.normalize("NFKD", value.lower().replace("ł", "l"))
        if not unicodedata.combining(char)
    )


# code, label, type, unit, aliases. Identifiers remain textual, including leading zeros.
SCHEMA = {
    "application": [
        ("application_number", "Numer wniosku", "text", "", ["numer wniosku", "nr wniosku", "wniosek nr"]),
        ("document_date", "Data dokumentu", "date", "", ["data dokumentu", "data sporzadzenia", "data wniosku"]),
    ],
    "participants": [
        ("role", "Rola", "text", "", []),
        ("name", "Nazwa / imię i nazwisko", "text", "", ["imie i nazwisko", "nazwa organizacji", "nazwa", "pelna nazwa"]),
        ("email", "E-mail", "text", "", ["e-mail", "email", "adres e-mail"]),
        ("phone", "Telefon", "text", "", ["telefon", "tel", "numer telefonu"]),
        ("address", "Adres", "text", "", ["adres", "adres zamieszkania", "adres siedziby"]),
        ("pesel", "PESEL", "text", "", ["pesel"]),
        ("nip", "NIP", "text", "", ["nip"]),
    ],
    "vehicle": [
        ("make", "Marka", "text", "", ["marka", "marka pojazdu"]),
        ("model", "Model", "text", "", ["model", "model pojazdu"]),
        ("registration", "Numer rejestracyjny", "text", "", ["numer rejestracyjny", "nr rejestracyjny", "rejestracja"]),
        ("vin", "VIN", "text", "", ["vin", "numer vin", "nr vin"]),
        ("year", "Rok produkcji", "integer", "rok", ["rok produkcji", "rok pojazdu"]),
    ],
    "coverage": [
        ("start_date", "Początek wnioskowanej ochrony", "date", "", ["poczatek ochrony", "ochrona od", "data poczatku ochrony", "poczatek wnioskowanej ochrony"]),
        ("end_date", "Koniec wnioskowanej ochrony", "date", "", ["koniec ochrony", "ochrona do", "data konca ochrony", "koniec wnioskowanej ochrony"]),
        ("requested_scope", "Żądany zakres (wniosek)", "text", "", ["zakres", "zadany zakres", "wnioskowany zakres", "zakres ubezpieczenia"]),
        ("insured_sum", "Suma ubezpieczenia", "decimal", "PLN", ["suma ubezpieczenia"]),
        ("premium", "Składka podana we wniosku", "decimal", "PLN", ["skladka", "wnioskowana skladka"]),
    ],
    "previous": [
        ("insurer", "Poprzedni ubezpieczyciel", "text", "", ["poprzedni ubezpieczyciel", "dotychczasowy ubezpieczyciel"]),
        ("policy_number", "Poprzedni numer polisy", "text", "", ["poprzedni numer polisy", "numer poprzedniej polisy", "poprzednia polisa", "nr poprzedniej polisy"]),
    ],
    "payment": [
        ("payment_method", "Sposób płatności", "text", "", ["sposob platnosci", "forma platnosci", "platnosc"]),
    ],
}


def typed_value(value: str, field_type: str) -> str | None:
    value = value.strip()
    if not value or normalized(value) in {"brak", "nie podano", "nie dotyczy", "-", "—"}:
        return None
    if field_type == "date":
        parts = re.fullmatch(r"(\d{4})-(\d{2})-(\d{2})", value)
        if parts:
            return date(*map(int, parts.groups())).isoformat()
        parts = re.fullmatch(r"(\d{1,2})[./-](\d{1,2})[./-](\d{4})", value)
        if not parts:
            raise ValueError("Nie rozpoznano jednoznacznej daty.")
        day, month, year = map(int, parts.groups())
        return date(year, month, day).isoformat()
    if field_type == "integer":
        if not re.fullmatch(r"\d{1,9}", value):
            raise ValueError("Nie rozpoznano liczby całkowitej.")
        return str(int(value))
    if field_type == "decimal":
        value = re.sub(r"\s*(PLN|zł|zl)\s*$", "", value, flags=re.I)
        value = value.replace(" ", "").replace("\u00a0", "")
        if re.fullmatch(r"\d{1,3}(?:\.\d{3})+", value):
            value = value.replace(".", "")
        if "," in value:
            value = value.replace(".", "").replace(",", ".")
        if not re.fullmatch(r"\d{1,12}(?:\.\d{1,2})?", value):
            raise ValueError("Kwota wymaga maksymalnie 12 cyfr oraz 2 miejsc po przecinku.")
        amount = Decimal(value)
        if not amount.is_finite() or abs(amount) >= Decimal("1e14"):
            raise ValueError("Kwota poza obsługiwanym zakresem.")
        return format(amount, "f")
    return value


def empty_field(group, index, definition):
    code, label, field_type, unit, _aliases = definition
    return {
        "code": code, "label": label, "value": None, "type": field_type,
        "unit": unit, "group": group, "index": index, "page": None,
        "source": "", "method": "", "warnings": ["Nie znaleziono wartości w dokumencie."],
        "manual": False, "absent": False,
    }


class BrokerMotorEngine:
    def extract(self, pages: list[PageText]) -> dict:
        if sum(len(page.text.encode("utf-8")) for page in pages) > MAX_TEXT_BYTES:
            raise ExtractionLimitError("Łączna treść dokumentu przekracza limit odczytu 1 MiB.")
        from .numbered import extract_numbered
        numbered = extract_numbered(pages)
        if numbered is not None:
            return numbered
        all_text = normalized("\n".join(page.text for page in pages))
        page_info = [{"number": page.number, "method": page.method} for page in pages]
        # Positive application wording must occur together on one line. An unrelated
        # footer saying "nie należy do profilu komunikacyjnego" is not recognition.
        is_profile = bool(re.search(
            r"^[ \t]*(?:dane testowe[. \t:-]*)?(?:formularz[ \t]*[-:—]?[ \t]*)?"
            r"wniosek[ \t]+(?:brokerski[ \t]+)?(?:ubezpieczenia[ \t]+)?komunikacyjn\w*\b",
            all_text, flags=re.M,
        ))
        if re.search(r"^(?:od|from|temat|subject|do|to):", all_text, flags=re.M):
            is_profile = False
        if not is_profile:
            return {"profile": None, "fields": [], "warnings": ["Brak profilu automatycznego odczytu"], "pages": page_info}

        fields = {}
        for group, definitions in SCHEMA.items():
            if group != "participants":
                for definition in definitions:
                    fields[(group, 0, definition[0])] = empty_field(group, 0, definition)

        aliases = []
        for group, definitions in SCHEMA.items():
            for definition in definitions:
                for alias in definition[4]:
                    aliases.append((alias, group, definition))
        aliases.sort(key=lambda item: -len(item[0]))
        current_participant = -1
        next_scope_index = 0
        role_expression = re.compile(
            r"^(?:(?:uczestnik|osoba)\s*\d*\s*[-—–:|]?\s*)?"
            r"((?:ubezpieczajacy|ubezpieczony|ubezpieczeni|wlasciciel)(?:\s*/\s*(?:ubezpieczajacy|ubezpieczony|ubezpieczeni|wlasciciel))*)\s*(?:\d+)?\s*(?::|=|\||[-—–])?\s*(.*)$"
        )

        def participant(index):
            for definition in SCHEMA["participants"]:
                fields.setdefault(("participants", index, definition[0]), empty_field("participants", index, definition))

        def set_value(key, raw, page, line):
            field = fields[key]
            try:
                value = typed_value(raw, field["type"])
                if field["value"] is not None and field["value"] != value:
                    field.update(value=None, warnings=["Sprzeczne wartości; sprawdź dokument ręcznie."], source="", page=None)
                    field["ambiguous"] = True
                    field["source_conflict"] = True
                    return
                if field.get("ambiguous"):
                    return
                field.update(value=value, page=page.number, source=line.strip()[:240], method=page.method,
                             warnings=[] if value is not None else ["Wartość niewskazana w źródle."])
            except (ValueError, InvalidOperation):
                field.update(value=None, page=page.number, source=line.strip()[:240], method=page.method,
                             warnings=["Nie rozpoznano jednoznacznej wartości; uzupełnij ręcznie."])

        for page in pages:
            for original_line in page.text.splitlines():
                # Columns and semicolon-delimited labels are accepted without depending on layout.
                lines = re.split(r"\s+\|\s+(?=[^|:;]{1,35}[:=])|;\s*(?=[A-Za-zĄĆĘŁŃÓŚŹŻąćęłńóśźż][^;:]{1,35}:)", original_line)
                for line in lines:
                    clean = normalized(line.strip()).strip("[] ")
                    role_match = role_expression.match(clean)
                    if role_match:
                        current_participant += 1
                        if current_participant >= MAX_PARTICIPANTS:
                            raise ExtractionLimitError("Dokument przekracza limit 100 uczestników profilu pilotażowego.")
                        participant(current_participant)
                        role_map = {"ubezpieczajacy": "policyholder", "ubezpieczony": "insured", "ubezpieczeni": "insured", "wlasciciel": "owner"}
                        roles = {role_map[part.strip()] for part in role_match.group(1).split("/")}
                        role_name = ",".join(role for role in ["policyholder", "insured", "owner"] if role in roles)
                        set_value(("participants", current_participant, "role"), role_name, page, line)
                        # Positions in NFKD-normalized Polish are stable after combining marks removed.
                        raw_name = line.strip()[role_match.start(2):].strip()
                        if raw_name:
                            set_value(("participants", current_participant, "name"), raw_name, page, line)
                        continue
                    for alias, group, definition in aliases:
                        match = re.match(r"^" + re.escape(alias) + r"\s*(?::|=|\||[—–])\s*(.*)$", clean)
                        if not match:
                            continue
                        index = current_participant if group == "participants" else 0
                        if group == "participants" and index < 0:
                            current_participant = index = 0
                            participant(index)
                        raw = line.strip()[match.start(1):].strip()
                        if definition[0] == "requested_scope":
                            scopes = [value.strip() for value in re.split(r"[,;/]", raw) if value.strip()]
                            if next_scope_index + len(scopes) > 30:
                                raise ExtractionLimitError("Dokument przekracza limit 30 pozycji żądanego zakresu.")
                            for scope_index, value in enumerate(scopes, start=next_scope_index):
                                key = (group, scope_index, definition[0])
                                fields.setdefault(key, empty_field(group, scope_index, definition))
                                set_value(key, value, page, line)
                            next_scope_index += len(scopes)
                        else:
                            set_value((group, index, definition[0]), raw, page, line)
                        break
        if current_participant < 0:
            participant(0)
        import uuid
        group_ids = {}
        result_fields = list(fields.values())
        for field in result_fields:
            field["group_id"] = group_ids.setdefault((field["group"], field["index"]), str(uuid.uuid4()))
        for field in result_fields:
            field.pop("ambiguous", None)
            if field["value"] and field["method"] == "ocr":
                field["warnings"].append("Tekst z OCR; sprawdź litery, cyfry i znaki w źródle.")
            if field["code"] == "email" and field["value"] and not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", field["value"]):
                field["value"] = None
                field["warnings"] = ["Adres e-mail jest niejednoznaczny; przepisz go ręcznie ze źródła."]
            if field["code"] == "vin" and field["value"] and not re.fullmatch(r"[A-HJ-NPR-Z0-9]{17}", field["value"].upper()):
                field["value"] = None
                field["warnings"] = ["VIN wymaga 17 znaków bez liter I, O i Q; sprawdź go ręcznie w źródle."]
        warnings = ["Profil pilotażowy: wniosek komunikacyjny. Wymaga sprawdzenia przez pracownika."]
        start = fields[("coverage", 0, "start_date")]
        end = fields[("coverage", 0, "end_date")]
        if start["value"] and end["value"] and end["value"] < start["value"]:
            end["warnings"].append("Koniec ochrony jest wcześniejszy niż początek.")
        return {"profile": PROFILE, "fields": result_fields, "warnings": warnings, "pages": page_info}
