"""Fail the required OCR prerequisite check instead of silently skipping tests."""

import os
import shutil
import subprocess


def main():
    executable = os.environ.get("TESSERACT_CMD", "tesseract")
    if not shutil.which(executable):
        raise SystemExit("Brak Tesseract: obowiązkowa weryfikacja OCR nie może zostać pominięta.")
    try:
        result = subprocess.run(
            [executable, "--list-langs"], capture_output=True, text=True, check=True, timeout=20,
        )
    except (OSError, subprocess.SubprocessError):
        raise SystemExit("Nie udało się sprawdzić języków Tesseract.") from None
    languages = set(result.stdout.splitlines())
    missing = {"pol", "eng"} - languages
    if missing:
        raise SystemExit("Brak wymaganych języków OCR: " + ", ".join(sorted(missing)))
    print("Obowiązkowe języki lokalnego OCR dostępne: pol, eng.")


if __name__ == "__main__":
    main()
