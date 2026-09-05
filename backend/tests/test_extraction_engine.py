import json
import os
import shutil
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

from extraction.acquisition import AcquisitionError, acquire_document
from extraction.engine import BrokerMotorEngine, ExtractionLimitError, PageText, typed_value

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures" / "synthetic"
EXPECTED = json.loads((FIXTURES / "expected.json").read_text())


def values(result):
    return {f"{field['group']}.{field['index']}.{field['code']}": field["value"] for field in result["fields"]}


def synthetic_document(name):
    return SimpleNamespace(file=SimpleNamespace(path=str(FIXTURES / name)), pk=7,
                           mime_type="image/png" if name.endswith(".png") else "image/jpeg" if name.endswith(".jpg") else "application/pdf")


def require_tesseract():
    if not shutil.which("tesseract"):
        if os.environ.get("OCR_REQUIRED") == "1":
            pytest.fail("Brak obowiązkowego OCR: Tesseract i języki pol+eng.")
        pytest.skip("Prawdziwy OCR wymaga lokalnego Tesseract; obowiązkowy w jobie CI OCR.")
    result = subprocess.run(["tesseract", "--list-langs"], capture_output=True, text=True, check=True)
    if not {"pol", "eng"}.issubset(set(result.stdout.split())):
        if os.environ.get("OCR_REQUIRED") == "1":
            pytest.fail("Brak obowiązkowego OCR: Tesseract i języki pol+eng.")
        pytest.skip("Prawdziwy OCR wymaga języków pol+eng; obowiązkowe w jobie CI OCR.")


@pytest.mark.parametrize("name", ["application_text.pdf", "application_holdout.pdf", "application_missing.pdf"])
def test_text_and_unseen_layout_use_content_and_preserve_meanings(name, settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path
    pages = acquire_document(synthetic_document(name))
    result = BrokerMotorEngine().extract(pages)
    assert result["profile"] == "broker_motor_application_v0"
    actual = values(result)
    for key, value in EXPECTED[name]["fields"].items():
        assert actual[key] == value, key
    for key in EXPECTED[name].get("null_fields", []):
        assert actual[key] is None
        field = next(field for field in result["fields"] if f"{field['group']}.{field['index']}.{field['code']}" == key)
        assert field["warnings"]
    assert all(page.method == "text" for page in pages)
    assert (tmp_path / "previews" / "7" / "1.png").is_file()


@pytest.mark.ocr
@pytest.mark.parametrize("name", ["application_scan.pdf", "application_mixed.pdf", "application.png", "application.jpg"])
def test_real_local_ocr_and_mixed_pages(name, settings, tmp_path):
    require_tesseract()
    settings.MEDIA_ROOT = tmp_path
    pages = acquire_document(synthetic_document(name))
    result = BrokerMotorEngine().extract(pages)
    assert result["profile"] == "broker_motor_application_v0"
    assert [page.method for page in pages] == EXPECTED[name]["page_methods"]
    actual = values(result)
    # Reference values remain independent. Known Tesseract character mistakes are
    # recorded separately and must be explicitly warned, never silently corrected.
    for key, value in EXPECTED["application_text.pdf"]["fields"].items():
        if actual[key] != value:
            field = next(field for field in result["fields"] if f"{field['group']}.{field['index']}.{field['code']}" == key)
            assert actual[key] in EXPECTED[name].get("accepted_ocr_readings", {}).get(key, []), key
            assert field["warnings"] and field["method"] == "ocr"
    for field in result["fields"]:
        if field["value"] is not None:
            assert field["source"] and field["page"] and field["method"] in {"text", "ocr"}


def test_missing_tesseract_is_failure(settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path
    settings.TESSERACT_CMD = str(tmp_path / "missing-tesseract")
    with pytest.raises(AcquisitionError, match="Brak lokalnego"):
        acquire_document(synthetic_document("application.png"))


def test_unsupported_profile_never_guesses_motor_fields(settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path
    result = BrokerMotorEngine().extract(acquire_document(synthetic_document("unsupported_property.pdf")))
    assert result["profile"] is None
    assert result["fields"] == []
    assert "Brak profilu automatycznego odczytu" in result["warnings"]
    negative = BrokerMotorEngine().extract([PageText(1, "text", "DANE TESTOWE\nTo nie jest wniosek komunikacyjny.\nWniosek nieruchomościowy.\nNumer wniosku: 0001")])
    assert negative["profile"] is None


def test_duplicate_conflicting_values_and_dates_stay_explicit():
    page = PageText(1, "text", """DANE TESTOWE. Wniosek brokerski komunikacyjny
Numer wniosku: 00017
Poprzedni numer polisy: 00099
Początek ochrony: 03.02.2027
Koniec ochrony: 01.02.2027
Marka: TestMobil
Marka: Inny TestMobil
Suma ubezpieczenia: 20 000,00 PLN
Składka: 500,50 PLN
E-mail: daneQdemo.invalid
""")
    parsed = BrokerMotorEngine().extract([page])
    actual = values(parsed)
    assert actual["application.0.application_number"] == "00017"
    assert actual["previous.0.policy_number"] == "00099"
    assert actual["vehicle.0.make"] is None
    assert actual["coverage.0.insured_sum"] == "20000.00"
    assert actual["coverage.0.premium"] == "500.50"
    assert actual["participants.0.email"] is None
    assert next(field for field in parsed["fields"] if field["code"] == "end_date")["warnings"]


def test_oversized_text_and_repeating_groups_fail_before_unbounded_growth():
    with pytest.raises(ExtractionLimitError, match="1 MiB"):
        BrokerMotorEngine().extract([PageText(1, "text", "a" * (1024 * 1024 + 1))])
    many = "DANE TESTOWE wniosek komunikacyjny\n" + "Ubezpieczony: DANE TESTOWE\n" * 101
    with pytest.raises(ExtractionLimitError, match="100 uczestników"):
        BrokerMotorEngine().extract([PageText(1, "text", many)])
    many_scopes = "DANE TESTOWE wniosek komunikacyjny\nZakres: " + ",".join(["TEST"] * 31)
    with pytest.raises(ExtractionLimitError, match="30 pozycji"):
        BrokerMotorEngine().extract([PageText(1, "text", many_scopes)])


@pytest.mark.parametrize("raw", ["1e999999", "NaN", "0.000000001", "1234567890123.00", "-1.00"])
def test_amount_limits_preserve_numeric_excel_precision(raw):
    with pytest.raises(ValueError):
        typed_value(raw, "decimal")


def test_repeated_scope_labels_preserve_distinct_rows():
    result = BrokerMotorEngine().extract([PageText(1, "text", """DANE TESTOWE
Wniosek komunikacyjny
Zakres: OC
Zakres: AC; Assistance
Ubezpieczony 1: Alicja DANE TESTOWE
Ubezpieczony 2: Bruno DANE TESTOWE
""")])
    actual = values(result)
    assert [actual[f"coverage.{index}.requested_scope"] for index in range(3)] == ["OC", "AC", "Assistance"]
    assert actual["participants.0.name"] == "Alicja DANE TESTOWE"
    assert actual["participants.1.name"] == "Bruno DANE TESTOWE"
