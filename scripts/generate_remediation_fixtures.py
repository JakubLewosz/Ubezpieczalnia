"""Syntetyczne numerowane wnioski; nie importuje parsera ani oczekiwanych odpowiedzi."""
from pathlib import Path

from generate_fixtures import font_path, image_pdf, render_page, text_pdf
from pypdf import PdfReader, PdfWriter
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "fixtures/remediation"


def main():
    pdfmetrics.registerFont(TTFont("FixtureFont", str(font_path())))
    for name in ["numbered", "variant", "holdout"]:
        lines = (OUTPUT / f"{name}.txt").read_text().splitlines()
        payload = text_pdf([lines])
        (OUTPUT / f"{name}.pdf").write_bytes(payload)
        if name != "numbered":
            continue
        picture = render_page(payload)
        picture.save(OUTPUT / "numbered.png")
        picture.save(OUTPUT / "numbered.jpg", quality=96)
        (OUTPUT / "numbered_scan.pdf").write_bytes(image_pdf(picture))
        first = text_pdf([lines[:10]], total_pages=2)
        second = text_pdf([lines[10:]], page_start=2, total_pages=2)
        mixed = PdfWriter()
        from io import BytesIO
        mixed.add_page(PdfReader(BytesIO(first)).pages[0])
        mixed.add_page(PdfReader(BytesIO(image_pdf(render_page(second)))).pages[0])
        with (OUTPUT / "numbered_mixed.pdf").open("wb") as stream:
            mixed.write(stream)


if __name__ == "__main__":
    main()
