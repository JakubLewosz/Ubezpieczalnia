"""Wspólne granice XML/XLSX, bez ukrytego usuwania lub obcinania znaków."""

MAX_CELL_CHARACTERS = 32767


class ExportValidationError(ValueError):
    pass


def validate_xlsx_text(value, location="tekst"):
    if value is None:
        return
    value = str(value)
    if len(value) > MAX_CELL_CHARACTERS:
        raise ExportValidationError(f"{location}: tekst przekracza limit {MAX_CELL_CHARACTERS} znaków komórki XLSX.")
    for char in value:
        code = ord(char)
        if not (code in {9, 10, 13} or 0x20 <= code <= 0xD7FF or 0xE000 <= code <= 0xFFFD or 0x10000 <= code <= 0x10FFFF):
            raise ExportValidationError(f"{location}: niedozwolony znak U+{code:04X}. Popraw tekst jawnie; źródło pozostaje niezmienne.")


def validate_tree(value, location="dane"):
    """Sprawdza także historyczne etykiety, źródła, nazwy i inne metadane."""
    if isinstance(value, str):
        validate_xlsx_text(value, location)
    elif isinstance(value, dict):
        for key, child in value.items():
            validate_xlsx_text(key, f"{location}.klucz")
            validate_tree(child, f"{location}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            validate_tree(child, f"{location}[{index}]")
