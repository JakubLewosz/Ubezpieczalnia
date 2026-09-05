import hashlib
import warnings
import zipfile
from pathlib import Path
from django.conf import settings
from PIL import Image
from pypdf import PdfReader
from rest_framework.exceptions import ValidationError
from exports.text import ExportValidationError, validate_xlsx_text

MIMES = {
    ".pdf": "application/pdf",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
}


def inspect_upload(upload):
    original = upload.name.replace("\\", "/").split("/")[-1]
    try:
        validate_xlsx_text(original, "Nazwa pliku")
    except ExportValidationError as error:
        raise ValidationError({"file": str(error)}) from None
    if len(original) > 255:
        raise ValidationError({"file": "Nazwa pliku przekracza 255 znaków. Skróć ją jawnie przed uploadem."})
    extension = Path(original).suffix.lower()
    if extension not in MIMES:
        raise ValidationError({"file": "Dozwolone są PDF, JPEG, PNG oraz załączniki DOCX i XLSX."})
    if not upload.size or upload.size > settings.MAX_UPLOAD_BYTES:
        raise ValidationError(
            {"file": f"Plik pusty lub większy niż limit {settings.MAX_UPLOAD_BYTES // (1024 * 1024)} MB."}
        )
    digest = hashlib.sha256()
    for chunk in upload.chunks():
        digest.update(chunk)
    upload.seek(0)
    page_count = 0
    try:
        signature = upload.read(8)
        upload.seek(0)
        if extension == ".pdf":
            if not signature.startswith(b"%PDF-"):
                raise ValueError("Nieprawidłowa zawartość PDF.")
            reader = PdfReader(upload, strict=True)
            if reader.is_encrypted:
                raise ValueError("Zaszyfrowany PDF nie jest obsługiwany. Wgraj odszyfrowaną kopię testową.")
            page_count = len(reader.pages)
            if not 1 <= page_count <= settings.MAX_DOCUMENT_PAGES:
                raise ValueError(f"Dozwolone jest 1–{settings.MAX_DOCUMENT_PAGES} stron.")
            for page in reader.pages:
                width, height = float(page.mediabox.width), float(page.mediabox.height)
                if (
                    width <= 0
                    or height <= 0
                    or width * height * getattr(settings, "EXTRACTION_RENDER_SCALE", 3) ** 2
                    > settings.MAX_DOCUMENT_PIXELS
                ):
                    raise ValueError("Strona PDF przekracza limit wymiarów podglądu.")
        elif extension in [".jpg", ".jpeg", ".png"]:
            with warnings.catch_warnings():
                warnings.simplefilter("error", Image.DecompressionBombWarning)
                with Image.open(upload) as img:
                    if img.format != ("PNG" if extension == ".png" else "JPEG"):
                        raise ValueError("Zawartość obrazu nie odpowiada rozszerzeniu.")
                    if (
                        img.width * img.height > settings.MAX_DOCUMENT_PIXELS
                        or getattr(img, "n_frames", 1) != 1
                    ):
                        raise ValueError("Obraz przekracza limit pikseli lub zawiera wiele klatek.")
                    img.verify()
            page_count = 1
        else:
            if not zipfile.is_zipfile(upload):
                raise ValueError("Nieprawidłowa zawartość dokumentu Office.")
            upload.seek(0)
            with zipfile.ZipFile(upload) as archive:
                entries = archive.infolist()
                if (
                    len(entries) > 2000
                    or sum(info.file_size for info in entries) > settings.MAX_UNPACKED_BYTES
                ):
                    raise ValueError("Załącznik przekracza limit rozpakowanych danych.")
                names = [info.filename for info in entries]
                if len(set(names)) != len(names):
                    raise ValueError("Powielone wpisy w archiwum Office.")
                expected = "word/document.xml" if extension == ".docx" else "xl/workbook.xml"
                if expected not in names or "[Content_Types].xml" not in names:
                    raise ValueError("Zawartość Office nie odpowiada rozszerzeniu.")
                if any(
                    "vba" in name.casefold() or name.startswith("/") or ".." in Path(name).parts
                    for name in names
                ):
                    raise ValueError("Makra lub niebezpieczne ścieżki w załączniku są niedozwolone.")
                if archive.testzip():
                    raise ValueError("Uszkodzone archiwum Office.")
    except (ValidationError,):
        raise
    except Exception as exc:
        safe = (
            str(exc)
            if isinstance(exc, ValueError)
            else "Plik jest uszkodzony lub ma nieobsługiwaną strukturę."
        )
        raise ValidationError({"file": safe}) from None
    finally:
        upload.seek(0)
    return {
        "original_name": original,
        "mime_type": MIMES[extension],
        "size": upload.size,
        "checksum": digest.hexdigest(),
        "page_count": page_count,
    }
