"""Lokalne pozyskanie tekstu i prywatnych PNG, bez wykonywania treści dokumentu."""

import math
import os
import subprocess
import tempfile
from pathlib import Path

import pypdfium2 as pdfium
from django.conf import settings
from PIL import Image, ImageOps
from pypdf import PdfReader
from pypdf import filters as pdf_filters

from .engine import MAX_TEXT_BYTES, PageText


class AcquisitionError(Exception):
    pass


def _setting(name, default):
    return getattr(settings, name, default)


def _check_pixels(width, height):
    if width < 1 or height < 1 or width * height > _setting("MAX_DOCUMENT_PIXELS", 40_000_000):
        raise AcquisitionError("Strona przekracza limit rozmiaru renderowania.")


def _write_preview(image, document_id, number):
    directory = Path(settings.MEDIA_ROOT) / "previews" / str(document_id)
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    target = directory / f"{number}.png"
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=directory, suffix=".png", delete=False) as stream:
            temporary = Path(stream.name)
            image.save(stream, format="PNG")
        os.replace(temporary, target)
    finally:
        if temporary:
            temporary.unlink(missing_ok=True)
    return target


def _ocr(path):
    command = _setting("TESSERACT_CMD", "tesseract")
    languages = _setting("OCR_LANGUAGE", "pol+eng")
    try:
        result = subprocess.run(
            [command, str(path), "stdout", "-l", languages, "--psm", "3"],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=_setting("OCR_TIMEOUT_SECONDS", 60), check=False,
            env={**os.environ, "OMP_THREAD_LIMIT": "1"},
        )
    except FileNotFoundError as exc:
        raise AcquisitionError("Brak lokalnego programu Tesseract. Zainstaluj Tesseract oraz języki pol i eng.") from exc
    except subprocess.TimeoutExpired as exc:
        raise AcquisitionError("Przekroczono limit czasu OCR strony.") from exc
    if result.returncode:
        # Do not expose raw stderr: document text and local paths are untrusted/private.
        raise AcquisitionError("Tesseract nie wykonał OCR. Sprawdź instalację i języki pol oraz eng.")
    # Some Tesseract builds return success when only one of two requested languages exists.
    if "Failed loading language" in result.stderr or "Error opening data file" in result.stderr:
        raise AcquisitionError("Brak wymaganego języka Tesseract. Wymagane są pol i eng.")
    if len(result.stdout) > 200_000:
        raise AcquisitionError("Tekst strony przekracza limit przetwarzania.")
    return result.stdout


def useful_text(text):
    # Avoid treating page numbers or a small watermark as a usable text layer.
    return sum(char.isalpha() for char in text) >= 70 and len(text.split()) >= 12


def acquire_document(document):
    path = Path(document.file.path)
    pages = []
    text_bytes = 0
    if document.mime_type == "application/pdf":
        try:
            # Limit individual decoded streams before pypdf extraction. These limits
            # are process-wide and never loosened by a document or its contents.
            for setting_name in ["ZLIB_MAX_OUTPUT_LENGTH", "LZW_MAX_OUTPUT_LENGTH", "RUN_LENGTH_MAX_OUTPUT_LENGTH", "MAX_ARRAY_BASED_STREAM_OUTPUT_LENGTH", "MAX_DECLARED_STREAM_LENGTH", "JBIG2_MAX_OUTPUT_LENGTH"]:
                if hasattr(pdf_filters, setting_name):
                    setattr(pdf_filters, setting_name, min(getattr(pdf_filters, setting_name), 10 * 1024 * 1024))
            reader = PdfReader(path, strict=True)
            if reader.is_encrypted:
                raise AcquisitionError("Zaszyfrowany PDF nie może być odczytany.")
            page_limit = _setting("MAX_DOCUMENT_PAGES", 30)
            if not 1 <= len(reader.pages) <= page_limit:
                raise AcquisitionError("Liczba stron PDF przekracza limit.")
            with pdfium.PdfDocument(str(path)) as rendered:
                decoded_total = 0
                for index, source_page in enumerate(reader.pages):
                    contents = source_page.get_contents()
                    if contents is not None:
                        decoded_total += len(contents.get_data())
                    if decoded_total > _setting("MAX_UNPACKED_BYTES", 100 * 1024 * 1024):
                        raise AcquisitionError("Rozpakowana treść PDF przekracza limit.")
                    page = rendered[index]
                    try:
                        width, height = page.get_size()
                        scale = _setting("EXTRACTION_RENDER_SCALE", 3)
                        _check_pixels(math.ceil(width * scale), math.ceil(height * scale))
                        bitmap = page.render(scale=scale)
                        try:
                            picture = bitmap.to_pil()
                            preview_path = _write_preview(picture, document.pk, index + 1)
                        finally:
                            bitmap.close()
                    finally:
                        page.close()
                    text = source_page.extract_text() or ""
                    if len(text) > 200_000:
                        raise AcquisitionError("Tekst strony przekracza limit przetwarzania.")
                    method = "text" if useful_text(text) else "ocr"
                    if method == "ocr":
                        text = _ocr(preview_path)
                    text_bytes += len(text.encode("utf-8"))
                    if text_bytes > MAX_TEXT_BYTES:
                        raise AcquisitionError("Łączna treść dokumentu przekracza limit odczytu 1 MiB.")
                    pages.append(PageText(index + 1, method, text))
        except AcquisitionError:
            raise
        except Exception as exc:
            raise AcquisitionError("Nie można odczytać PDF. Plik może być uszkodzony lub przekraczać limity.") from exc
    elif document.mime_type in {"image/jpeg", "image/png"}:
        try:
            with Image.open(path) as original:
                _check_pixels(*original.size)
                picture = ImageOps.exif_transpose(original).convert("RGB")
                preview_path = _write_preview(picture, document.pk, 1)
            pages.append(PageText(1, "ocr", _ocr(preview_path)))
        except AcquisitionError:
            raise
        except Exception as exc:
            raise AcquisitionError("Nie można odczytać obrazu. Sprawdź format i rozmiar pliku.") from exc
    else:
        raise AcquisitionError("Ten format jest załącznikiem i nie ma automatycznego odczytu.")
    return pages
