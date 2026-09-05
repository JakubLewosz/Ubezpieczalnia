import copy
import uuid
from decimal import InvalidOperation

from django.utils import timezone
from rest_framework.exceptions import APIException, ValidationError

from exports.text import ExportValidationError, validate_xlsx_text

from .engine import typed_value
from .numbered import ALLOWED_ROLES, blank_group
from .validation import draft_warnings, field_identity


class VersionConflict(APIException):
    status_code = 409
    default_detail = "Ten odczyt ma już nowszą wersję. Odśwież dane przed zapisem."


def check_version(draft, version):
    if draft.version != version:
        raise VersionConflict()


def ensure_group_ids(fields):
    """Dodaje tożsamość tylko do mutable szkicu, nigdy do historycznej rewizji."""
    groups = {}
    for field in fields:
        field.setdefault("group_id", groups.setdefault((field["group"], field["index"]), str(uuid.uuid4())))
    return fields


def validate_fields(stored, submitted, user):
    if len(stored) != len(submitted):
        raise ValidationError({"fields": "Zachowaj pola szkicu. Dodaj lub usuń grupę dedykowaną operacją."})
    by_identity = {(field["group"], field["index"], field["code"]): field for field in stored}
    result = []
    seen = set()
    changed = False
    for incoming in submitted:
        if (not isinstance(incoming.get("group"), str) or not isinstance(incoming.get("code"), str)
                or type(incoming.get("index")) is not int):
            raise ValidationError({"fields": "Nieprawidłowy identyfikator pola."})
        identity = (incoming["group"], incoming["index"], incoming["code"])
        previous = by_identity.get(identity)
        if (previous is None or identity in seen or incoming.get("type") != previous["type"]
                or incoming.get("group_id") != previous.get("group_id")):
            raise ValidationError({"fields": "Nie można zmienić tożsamości ani typu pola."})
        for key in ["label", "unit"]:
            if key in incoming and incoming[key] != previous[key]:
                raise ValidationError({"fields": f"Nie można zmienić definicji pola: {key}."})
        seen.add(identity)
        field = copy.deepcopy(previous)
        if previous.get("method") != "manual" and any("sprzeczne" in str(w).lower() for w in previous.get("warnings", [])):
            field["source_conflict"] = True
        value = incoming.get("value")
        absent = incoming.get("absent", False)
        if not isinstance(absent, bool) or (value is not None and not isinstance(value, str)):
            raise ValidationError({"fields": "Wartość musi być tekstem lub null; brak w dokumencie musi być logiczny."})
        if absent and value is not None:
            raise ValidationError({"fields": "Pole oznaczone jako brak w dokumencie musi mieć wartość null."})
        if value is not None:
            try:
                validate_xlsx_text(value, field_identity(field))
            except ExportValidationError as exc:
                raise ValidationError({"fields": str(exc)}) from exc
            if field["code"] == "role":
                roles = value.split(",")
                if not roles or any(role not in ALLOWED_ROLES for role in roles) or len(roles) != len(set(roles)):
                    raise ValidationError({"fields": "Rola musi należeć do policyholder, insured lub owner (lista bez powtórzeń)."})
                value = ",".join(role for role in ["policyholder", "insured", "owner"] if role in roles)
            if field["type"] != "text":
                try:
                    value = typed_value(value, field["type"])
                except (ValueError, InvalidOperation):
                    pass  # Nieprawidłowa wartość pozostaje w szkicu z aktualnym ostrzeżeniem.
        if value != previous["value"] or absent != previous["absent"]:
            changed = True
            field.setdefault("origin", {key: previous[key] for key in ("value", "page", "source", "method")})
            field.pop("source_conflict", None)
            field.pop("unit_conflict", None)
            field.update(value=value, absent=absent, manual=True, source="", page=None, method="manual",
                         updated_by=user.username, updated_at=timezone.now().isoformat(), warnings=[])
        result.append(field)
    corrected = {(field["group"], field["index"], field["code"]): field for field in result}
    ordered = [corrected[key] for key in by_identity]
    # Replace field warning displays, while the immutable EngineResult still records original diagnostics.
    warnings = draft_warnings(ordered)
    for field in ordered:
        field["warnings"] = [w["message"] for w in warnings if w["field"] == field_identity(field)]
    return ordered, changed


def add_group(draft, group, user):
    existing = {field["group_id"] for field in draft.fields if field["group"] == group}
    maximum = 100 if group == "participants" else 30
    if len(existing) >= maximum:
        raise ValidationError({"group": f"Limit grup: {maximum}."})
    counters = dict(draft.group_counters)
    index = max(counters.get(group, 0), max((f["index"] + 1 for f in draft.fields if f["group"] == group), default=0))
    fields = blank_group(group, index, manual=True, user=user)
    draft.fields = [*draft.fields, *fields]
    counters[group] = index + 1
    draft.group_counters = counters
    return fields[0]["group_id"]


def reset_from_result(draft, latest):
    counters = dict(draft.group_counters)
    for field in draft.fields:
        counters[field["group"]] = max(counters.get(field["group"], 0), field["index"] + 1)
    identities = {}
    fields = copy.deepcopy(latest.fields)
    for field in fields:
        key = (field["group"], field["index"])
        if key not in identities:
            index = counters.get(field["group"], 0)
            identities[key] = (str(uuid.uuid4()), index)
            counters[field["group"]] = index + 1
        field["group_id"], field["index"] = identities[key]
    draft.fields = fields
    draft.group_counters = counters
