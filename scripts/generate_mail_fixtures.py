"""Synthetic fixtures only; no network, mail delivery, or private input."""
from email.message import EmailMessage
from email.policy import SMTP
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / "fixtures/mail"


def message(key, subject, sender="anna@example.invalid", body="DANE TESTOWE\nProszę o sprawdzenie wiadomości."):
    m = EmailMessage(policy=SMTP)
    m["X-Broker-Demo"] = "DANE TESTOWE"
    m["From"] = f"Anna Demonstracyjna <{sender}>"
    m["To"] = "kancelaria@example.invalid"
    m["Subject"] = "DANE TESTOWE — " + subject
    m["Date"] = "Sat, 05 Sep 2026 12:00:00 +0200"
    m["Message-ID"] = f"<{key}@broker.example.invalid>"
    m.set_content(body)
    return m


def main():
    DEST.mkdir(parents=True, exist_ok=True)
    m = message("application", "Zapytanie ofertowe — wniosek komunikacyjny")
    m.add_attachment((ROOT / "fixtures/remediation/numbered_scan.pdf").read_bytes(), maintype="application", subtype="pdf", filename="DANE TESTOWE wniosek.pdf")
    samples = {"application": m,
        "no-client": message("no-client", "Prośba od nowego nadawcy", "nowy@example.invalid"),
        "candidates": message("candidates", "Dwie kartoteki z tym samym kontaktem", "wspolny@example.invalid"),
        "newsletter": message("newsletter", "Newsletter — informacje testowe", "newsletter@example.invalid"),
    }
    html = message("html-only", "Treść HTML z polskimi znakami")
    html.set_content('<html><head><style>body{display:none}</style></head><body><p>DANE TESTOWE</p><p>Zażółć gęślą jaźń.</p><script>alert("x")</script><img src="https://tracker.example.invalid/pixel"><p>Drugi akapit.</p></body></html>', subtype="html")
    samples["html-only"] = html
    bad = message("malformed", "Nieprawidłowy nagłówek")
    del bad["Date"]
    bad["Date"] = "nieprawidłowa data"
    samples["malformed"] = bad
    blocked = message("blocked", "Niedozwolone typy załączników")
    blocked.add_attachment(b"DANE TESTOWE - inert executable placeholder, never run", maintype="application", subtype="octet-stream", filename="DANE TESTOWE.exe")
    blocked.add_attachment(b"DANE TESTOWE - not an archive", maintype="application", subtype="zip", filename="DANE TESTOWE.zip")
    samples["blocked"] = blocked
    oversized = message("oversized", "Limit demonstracyjny załącznika 1 KiB", body="DANE TESTOWE\nTen scenariusz jawnie używa limitu części 1024 bajty; standardowy limit dokumentu to 20 MiB.")
    oversized.add_attachment(b"%PDF-1.4\n% DANE TESTOWE\n" + b"0" * 2048, maintype="application", subtype="pdf", filename="DANE TESTOWE duzy.pdf")
    samples["oversized"] = oversized
    reply = message("reply", "Re: Zapytanie ofertowe — wniosek komunikacyjny")
    reply["In-Reply-To"] = "<application@broker.example.invalid>"
    reply["References"] = "<application@broker.example.invalid>"
    samples["reply"] = reply
    for key, sample in samples.items():
        raw = sample.as_bytes()
        if key == "malformed":
            raw = raw.replace(b"\r\nMIME-Version:", b"\r\nMessage-ID: <second@broker.example.invalid>\r\nMIME-Version:", 1)
            raw = raw.replace(b'charset="utf-8"', b'charset="invalid-test-charset"')
        (DEST / f"{key}.eml").write_bytes(raw)
    print(f"Generated {len(samples)} synthetic fixtures in fixtures/mail.")


if __name__ == "__main__":
    main()
