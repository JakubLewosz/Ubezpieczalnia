from io import BytesIO
from pathlib import Path
import zipfile
import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from PIL import Image
from pypdf import PdfWriter
from documents.models import Document

pytestmark = pytest.mark.django_db
FIXTURES = Path(__file__).resolve().parents[2] / "fixtures/synthetic"


def pdf(encrypted=False, pages=1):
    writer = PdfWriter()
    for _ in range(pages):
        writer.add_blank_page(width=595, height=842)
    if encrypted:
        writer.encrypt("synthetic-only")
    data = BytesIO()
    writer.write(data)
    return data.getvalue()


def upload(api, customer, name, content):
    return api.post(
        "/api/documents/",
        {"client": customer.pk, "category": "DANE TESTOWE", "file": SimpleUploadedFile(name, content)},
        format="multipart",
    )


def test_upload_metadata_private_original_no_public_media(api, customer, user):
    data = pdf()
    response = upload(api, customer, r"..\..\evil<script>.pdf", data)
    assert response.status_code == 201, response.data
    obj = Document.objects.get()
    assert obj.original_name == "evil<script>.pdf"
    assert "<" not in obj.file.name and ".." not in obj.file.name
    assert obj.file.read() == data
    duplicate = upload(api, customer, "duplicate.pdf", data)
    assert duplicate.status_code == 201 and duplicate.json()["duplicate_warnings"]
    response = api.get(f"/api/documents/{obj.pk}/original/")
    assert response.status_code == 200 and response["X-Content-Type-Options"] == "nosniff"
    assert response["Content-Disposition"].startswith("attachment;")
    assert b"".join(response.streaming_content) == data
    assert api.get("/media/" + obj.file.name).status_code == 404
    api.logout()
    assert api.get(f"/api/documents/{obj.pk}/original/").status_code == 403
    assert api.get(f"/api/documents/{obj.pk}/pages/1/").status_code == 403


@pytest.mark.parametrize(
    "name,content",
    [
        ("evil.html", b"<script>"),
        ("fake.pdf", b"<html>"),
        ("broken.pdf", b"%PDF-1.4\ninvalid"),
        ("encrypted.pdf", pdf(True)),
        ("many.pdf", pdf(pages=31)),
        ("fake.png", b"not a png"),
        ("fake.docx", b"not a zip"),
        ("empty.pdf", b""),
    ],
)
def test_reject_invalid_documents(api, customer, name, content):
    response = upload(api, customer, name, content)
    assert response.status_code == 400, response.data
    assert Document.objects.count() == 0


def test_size_and_pixel_limits(api, customer, settings):
    settings.MAX_UPLOAD_BYTES = 20
    assert upload(api, customer, "large.pdf", pdf()).status_code == 400
    settings.MAX_UPLOAD_BYTES = 20 * 1024 * 1024
    settings.MAX_DOCUMENT_PIXELS = 50
    data = BytesIO()
    Image.new("RGB", (10, 10)).save(data, format="PNG")
    assert upload(api, customer, "image.png", data.getvalue()).status_code == 400


def test_office_attachment_stored_but_never_interpreted(api, customer):
    from openpyxl import Workbook

    data = BytesIO()
    Workbook().save(data)
    response = upload(api, customer, "synthetic.xlsx", data.getvalue())
    assert response.status_code == 201, response.data
    assert response.json()["review_status"] == "attachment"
    assert api.post(f"/api/documents/{response.json()['id']}/extract/", {}, format="json").status_code == 400


def test_zip_expansion_and_macro_rejected(api, customer, settings):
    for extra in ["word/vbaProject.bin", "word/large.xml"]:
        data = BytesIO()
        with zipfile.ZipFile(data, "w", zipfile.ZIP_DEFLATED) as out:
            out.writestr("[Content_Types].xml", "<Types/>")
            out.writestr("word/document.xml", "<document/>")
            out.writestr(extra, "x" * 10000)
        settings.MAX_UNPACKED_BYTES = 1000
        assert upload(api, customer, "unsafe.docx", data.getvalue()).status_code == 400


def test_failed_database_insert_removes_private_original(api, customer, settings):
    from unittest.mock import patch

    with patch.object(Document, "_do_insert", side_effect=RuntimeError("synthetic DB failure")):
        with pytest.raises(RuntimeError):
            upload(api, customer, "failed.pdf", pdf())
    assert not any(path.is_file() for path in settings.MEDIA_ROOT.rglob("*"))
