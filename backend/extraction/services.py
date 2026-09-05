import copy
from decimal import InvalidOperation

from django.utils import timezone
from rest_framework.exceptions import APIException, ValidationError

from .engine import typed_value


class VersionConflict(APIException):
    status_code = 409
    default_detail = "Ten odczyt ma już nowszą wersję. Odśwież dane przed zapisem."


def check_version(draft, version):
    if draft.version != version:
        raise VersionConflict()


def validate_fields(stored, submitted, user):
    if len(stored) != len(submitted):
        raise ValidationError({"fields": "Zachowaj wszystkie pola i grupy odczytu."})
    by_identity = {(field["group"], field["index"], field["code"]): field for field in stored}
    result = []
    seen = set()
    changed = False
    for incoming in submitted:
        if (not isinstance(incoming.get("group"), str) or not isinstance(incoming.get("code"), str)
                or type(incoming.get("index")) is not int):
            raise ValidationError({"fields": "Nieprawidłowy identyfikator pola."})
        identity = (incoming.get("group"), incoming.get("index"), incoming.get("code"))
        try:
            previous = by_identity.get(identity)
            duplicate = identity in seen
        except TypeError as exc:
            raise ValidationError({"fields": "Nieprawidłowy identyfikator pola."}) from exc
        if previous is None or duplicate or incoming.get("type") != previous["type"]:
            raise ValidationError({"fields": "Nie można zmienić tożsamości ani typu pola."})
        seen.add(identity)
        field = copy.deepcopy(previous)
        value = incoming.get("value")
        absent = incoming.get("absent", False)
        if not isinstance(absent, bool) or (value is not None and not isinstance(value, str)):
            raise ValidationError({"fields": "Wartość musi być tekstem lub null; brak w dokumencie musi być logiczny."})
        if absent and value is not None:
            raise ValidationError({"fields": "Pole oznaczone jako brak w dokumencie musi mieć wartość null."})
        if value is not None:
            if len(value) > 10_000:
                raise ValidationError({"fields": "Wartość pola jest zbyt długa."})
            if field["type"] != "text":
                try:
                    value = typed_value(value, field["type"])
                except (ValueError, InvalidOperation) as exc:
                    raise ValidationError({"fields": f"Nieprawidłowa wartość pola: {field['label']}."}) from exc
        if value != previous["value"] or absent != previous["absent"]:
            changed = True
            field.setdefault("origin", {
                key: previous[key] for key in ("value", "page", "source", "method")
            })
            field.update(
                value=value, absent=absent, manual=True, source="", page=None, method="manual",
                updated_by=user.username, updated_at=timezone.now().isoformat(),
                warnings=[] if absent else ["Wartość wpisana ręcznie; sprawdź zgodność z dokumentem."],
            )
        result.append(field)
    # Client-side reordering is not an edit and does not alter stable export ordering.
    corrected = {(field["group"], field["index"], field["code"]): field for field in result}
    return [corrected[key] for key in by_identity], changed
