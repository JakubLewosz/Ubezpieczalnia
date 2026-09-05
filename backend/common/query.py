from rest_framework.exceptions import ValidationError


def positive_ids(value, name, *, limit=250):
    """Bound relation selectors before they reach PostgreSQL or pagination."""
    if value is None or value == "":
        return []
    pieces = value.split(",")
    if len(pieces) > limit or any(
        not item.isascii() or not item.isdigit() or len(item) > 19
        or not 0 < int(item) <= 9223372036854775807 for item in pieces
    ):
        raise ValidationError({name: f"Podaj poprawne identyfikatory; maksymalnie {limit} w zapytaniu."})
    return list(dict.fromkeys(int(item) for item in pieces))
