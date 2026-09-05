"""Real local OCR and IMAP workers: receive a fixture while a long scan is still running."""

import argparse
import http.cookiejar
import json
import os
import secrets
import sys
import time
import urllib.request
from io import BytesIO
from pathlib import Path

from local_imap import DIRECTORY, ROOT, environment, inject


def main():
    parser = argparse.ArgumentParser(description="DANE TESTOWE: odbiór poczty równolegle z prawdziwym OCR.")
    parser.add_argument("--credentials", type=Path, default=ROOT / ".local/demo-credentials.json")
    args = parser.parse_args()
    os.environ.update(environment())
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    sys.path.insert(0, str(ROOT / "backend"))
    import django
    django.setup()
    from correspondence.config import load_config
    from correspondence.imap_client import IMAPClient
    from correspondence.models import Message
    from correspondence.sync_models import Mailbox
    from django.conf import settings
    from extraction.models import ExtractionJob
    from pypdf import PdfReader, PdfWriter

    if not settings.DEVELOPMENT:
        raise SystemExit("Próba wymaga lokalnej demonstracji DJANGO_ENV=development.")
    config = load_config()
    mailbox = Mailbox.objects.get(kind="imap", config_fingerprint=config.fingerprint)
    if not mailbox.enabled or mailbox.uidvalidity is None or mailbox.last_success is None:
        raise SystemExit("Najpierw ADMIN musi jawnie uruchomić i zainicjalizować lokalny import.")
    credentials = json.loads(args.credentials.read_text())
    base = "http://127.0.0.1:5173"
    cookies = http.cookiejar.CookieJar()
    client = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cookies))

    def api(path, payload=None, raw=None, content_type=None):
        headers = {"Origin": base, "Referer": base + "/"}
        if payload is not None:
            raw = json.dumps(payload).encode()
            content_type = "application/json"
        if raw is not None:
            headers["X-CSRFToken"] = next(cookie.value for cookie in cookies if cookie.name == "csrftoken")
            headers["Content-Type"] = content_type
        with client.open(urllib.request.Request(base + path, data=raw, headers=headers), timeout=30) as response:
            return json.load(response)

    api("/api/auth/csrf/")
    api("/api/auth/login/", {key: credentials[key] for key in ("username", "password")})
    person = api("/api/clients/", {"kind": "person", "first_name": "DANE TESTOWE",
                                 "last_name": "Próba oddzielnych kolejek " + secrets.token_hex(4)})
    reader = PdfReader(ROOT / "fixtures/synthetic/application_scan.pdf")
    writer = PdfWriter()
    for _ in range(30):
        writer.add_page(reader.pages[0])
    output = BytesIO()
    writer.write(output)
    boundary = "BrokerSynthetic" + secrets.token_hex(16)
    body = (f'--{boundary}\r\nContent-Disposition: form-data; name="client"\r\n\r\n{person["id"]}\r\n'
            f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="DANE-TESTOWE-long-ocr.pdf"\r\n'
            'Content-Type: application/pdf\r\n\r\n').encode()
    body += output.getvalue() + f"\r\n--{boundary}--\r\n".encode()
    document = api("/api/documents/", raw=body, content_type="multipart/form-data; boundary=" + boundary)
    job_data = api(f'/api/documents/{document["id"]}/extract/', {})
    deadline = time.monotonic() + 90
    while time.monotonic() < deadline:
        job = ExtractionJob.objects.get(pk=job_data["id"])
        if job.status == "running":
            break
        if job.status == "failed":
            raise SystemExit("Nie udało się rozpocząć rzeczywistego długiego OCR.")
        time.sleep(0.5)
    else:
        raise SystemExit("Worker nie rozpoczął odczytu w czasie próby.")
    with IMAPClient(config) as source:
        uid = source.open_folder().uidnext
    started = time.monotonic()
    inject(DIRECTORY, ROOT / "fixtures/mail/newsletter.eml")
    # No browser, request_sync call, Celery eager mode, artificial task sleep or mocked client.
    while time.monotonic() - started < 90:
        message = Message.objects.filter(mailbox=mailbox, uidvalidity=mailbox.uidvalidity,
                                         uid=uid, fetch_state="ready").first()
        if message:
            break
        time.sleep(0.5)
    else:
        raise SystemExit("Beat i worker nie pobrali wiadomości w czasie próby.")
    job.refresh_from_db()
    assert job.status == "running", "Poczta dotarła dopiero po zakończeniu OCR; brak dowodu równoległej pracy."
    assert message.status == "todo" and message.owner_id is None and not message.reads.exists()
    result = {"data": "DANE TESTOWE", "document": document["id"], "job": job.pk, "message": message.pk,
              "mail_import_seconds": round(time.monotonic() - started, 2), "ocr_status_at_import": job.status,
              "browser_used": False, "manual_sync_trigger": False, "status": message.status, "personal_reads": 0}
    deadline = time.monotonic() + 300
    while time.monotonic() < deadline:
        job.refresh_from_db()
        if job.status in {"failed", "succeeded"}:
            break
        time.sleep(1)
    else:
        raise SystemExit("OCR nie osiągnął stanu końcowego w limicie.")
    result["ocr_final_status"] = job.status
    result["ocr_controlled_error"] = job.error
    result["ocr_seconds"] = round((job.finished_at - job.started_at).total_seconds(), 2)
    target = ROOT / ".local/mail-worker-result.json"
    target.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
