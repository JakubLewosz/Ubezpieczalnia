"""Generate documents from synthetic text, independently of extraction implementation.

Expected assertions live in fixtures/synthetic/expected.json and are deliberately
not imported here or by the application parser. No identifiers represent people.
"""

import argparse
from io import BytesIO
from pathlib import Path

import pypdfium2 as pdfium
from pypdf import PdfReader, PdfWriter
from reportlab.lib.pagesizes import A4
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

ROOT = Path(__file__).resolve().parents[1]

MAIN = [
    "WNIOSEK BROKERSKI KOMUNIKACYJNY",
    "Numer wniosku: TEST-WN-0007",
    "Data dokumentu: 2026-08-20",
    "UBEZPIECZAJĄCY",
    "Imię i nazwisko: Alicja Demonstracyjna DANE TESTOWE",
    "E-mail: alicja@broker-demo.invalid",
    "Telefon: +48 000 000 001",
    "Adres: ul. Testowa 1, 00-000 Miasto Testowe",
    "UBEZPIECZONY",
    "Imię i nazwisko: Bruno Przykładowy DANE TESTOWE",
    "E-mail: bruno@broker-demo.invalid",
    "Adres: ul. Fikcyjna 2, 00-000 Miasto Testowe",
    "POJAZD",
    "Marka: TestMobil",
    "Model: Przykład 2",
    "Numer rejestracyjny: TEST001",
    "VIN: TEST0000000000001",
    "Rok produkcji: 2022",
]
COVERAGE = [
    "WNIOSKOWANA OCHRONA - NIE JEST WYSTAWIONĄ POLISĄ",
    "Początek ochrony: 2026-10-01",
    "Koniec ochrony: 2027-09-30",
    "Zakres: OC, AC, Assistance",
    "Suma ubezpieczenia: 75000,00 PLN",
    "Składka: 1234,50 PLN",
    "Poprzedni ubezpieczyciel: Towarzystwo Testowe DANE TESTOWE",
    "Poprzedni numer polisy: TEST-POL-0091",
    "Sposób płatności: przelew jednorazowy",
]


def font_path():
    return ROOT / "fixtures/fonts/DejaVuSans.ttf"


def text_pdf(pages, page_start=1, total_pages=None):
    output = BytesIO()
    doc = canvas.Canvas(output, pagesize=A4, invariant=1)
    doc.setTitle("DANE TESTOWE - syntetyczny dokument Broker Office")
    doc.setAuthor("Broker Office - generator danych testowych")
    for page_number, lines in enumerate(pages, page_start):
        doc.setFillColorRGB(0.13, 0.28, 0.36)
        doc.setFont("FixtureFont", 16)
        doc.drawString(42, A4[1] - 43, "DANE TESTOWE")
        doc.setFont("FixtureFont", 8)
        doc.drawString(42, A4[1] - 59, "Dokument syntetyczny. Nie potwierdza zawarcia ubezpieczenia.")
        doc.setStrokeColorRGB(0.7, 0.78, 0.82)
        doc.line(42, A4[1] - 68, A4[0] - 42, A4[1] - 68)
        y = A4[1] - 91
        for line in lines:
            doc.setFont("FixtureFont", 9.3)
            doc.setFillColorRGB(0.12, 0.16, 0.2)
            # All fixtures are intentionally controlled, short labelled fields.
            if pdfmetrics.stringWidth(line, "FixtureFont", 9.3) > A4[0] - 84:
                raise ValueError(f"Zbyt długa linia syntetycznego formularza: {line}")
            doc.drawString(42, y, line)
            y -= 20
        if y < 44:
            raise ValueError("Zbyt wiele linii na stronie formularza.")
        doc.setFont("FixtureFont", 8)
        doc.drawString(42, 27, f"DANE TESTOWE | Strona {page_number} / {total_pages or len(pages)}")
        doc.showPage()
    doc.save()
    return output.getvalue()


def render_page(pdf_bytes, index=0):
    document = pdfium.PdfDocument(pdf_bytes)
    page = document[index]
    bitmap = page.render(scale=2.5)
    image = bitmap.to_pil().copy()
    bitmap.close()
    page.close()
    document.close()
    return image


def image_pdf(image):
    output = BytesIO()
    doc = canvas.Canvas(output, pagesize=A4, invariant=1)
    doc.setTitle("DANE TESTOWE - skan syntetyczny")
    doc.drawImage(ImageReader(image), 0, 0, width=A4[0], height=A4[1])
    doc.save()
    return output.getvalue()


def generate(output):
    pdfmetrics.registerFont(TTFont("FixtureFont", str(font_path())))
    output.mkdir(parents=True, exist_ok=True)
    primary = text_pdf([MAIN + COVERAGE])
    (output / "application_text.pdf").write_bytes(primary)
    raster = render_page(primary)
    raster.save(output / "application.png")
    raster.convert("RGB").save(output / "application.jpg", quality=93)
    (output / "application_scan.pdf").write_bytes(image_pdf(raster))
    first = text_pdf([MAIN], total_pages=2)
    second = text_pdf([COVERAGE], page_start=2, total_pages=2)
    mixed = PdfWriter()
    mixed.append(PdfReader(BytesIO(first)))
    mixed.append(PdfReader(BytesIO(image_pdf(render_page(second)))))
    mixed.add_metadata({"/Title": "DANE TESTOWE - tekst i obraz w jednym PDF"})
    with (output / "application_mixed.pdf").open("wb") as stream:
        mixed.write(stream)
    missing = [line for line in MAIN if not line.startswith(("VIN:", "Rok produkcji:", "Telefon:"))]
    missing += [line for line in COVERAGE if not line.startswith(("Składka:", "Poprzedni numer polisy:"))]
    (output / "application_missing.pdf").write_bytes(text_pdf([missing]))
    # Holdout layout: reordered content, two separator forms and labelled role sections.
    holdout = [
        "FORMULARZ - WNIOSEK BROKERSKI KOMUNIKACYJNY",
        "Numer wniosku = TEST-WN-HOLDOUT-31",
        "Sposób płatności | dwie raty przelewem",
        "POJAZD",
        "Rok produkcji = 2024",
        "VIN = TEST0000000000031",
        "Numer rejestracyjny | TEST031",
        "Model = Wariant Holdout",
        "Marka = AutoPróba",
        "WNIOSKOWANY OKRES I ZAKRES",
        "Koniec ochrony = 2028-02-29",
        "Początek ochrony = 2027-03-01",
        "Zakres | OC; Assistance",
        "Suma ubezpieczenia = 91000,00 PLN",
        "Składka = 2001,25 PLN",
        "Poprzedni numer polisy = TEST-OLD-0031",
        "Poprzedni ubezpieczyciel = Ubezpieczenia Demo DANE TESTOWE",
        "UCZESTNIK 1 - UBEZPIECZAJĄCY",
        "Imię i nazwisko = Celina Wzorcowa DANE TESTOWE",
        "Adres = Aleja Przykładu 31, 00-000 Miasto Testowe",
        "E-mail = celina@holdout.invalid",
        "UCZESTNIK 2 - UBEZPIECZONY",
        "Imię i nazwisko = Damian Wariantowy DANE TESTOWE",
        "E-mail = damian@holdout.invalid",
        "Data dokumentu = 2027-02-18",
    ]
    (output / "application_holdout.pdf").write_bytes(text_pdf([holdout]))
    (output / "unsupported_property.pdf").write_bytes(text_pdf([[
        "WNIOSEK UBEZPIECZENIA NIERUCHOMOŚCI - DANE TESTOWE",
        "Adres budynku: ul. Nieistniejąca 8, 00-000 Miasto Testowe",
        "Rok budowy: 2001",
        "Suma ubezpieczenia: 900000,00 PLN",
        "Numer wniosku: TEST-DOM-0008",
        "E-mail: budynek@broker-demo.invalid",
        "Ten rodzaj dokumentu nie należy do profilu komunikacyjnego.",
    ]]))
    encrypted = PdfWriter()
    encrypted.append(PdfReader(BytesIO(primary)))
    # Public test input, not an application/account secret.
    encrypted.encrypt("DANE TESTOWE - zaszyfrowany plik")
    with (output / "encrypted.pdf").open("wb") as stream:
        encrypted.write(stream)
    (output / "corrupted.pdf").write_bytes(b"%PDF-1.7\nDANE TESTOWE - deliberately invalid PDF\n")
    print(f"Wygenerowano dokumenty DANE TESTOWE w {output}.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generator wyłącznie syntetycznych dokumentów.")
    parser.add_argument("--output", type=Path, default=ROOT / "fixtures/synthetic")
    generate(parser.parse_args().output)
