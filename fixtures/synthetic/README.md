# DANE TESTOWE

Wszystkie dokumenty w tym folderze powstają z `scripts/generate_fixtures.py`.
Nie zawierają prawdziwych polis, identyfikatorów osobowych, podpisów, znaków firmowych ani kodów QR.
Adresy e-mail kończą się domeną `.invalid`, PESEL i NIP nie są generowane.

- `application_text.pdf`: wniosek z tekstem i polskimi znakami.
- `application_scan.pdf`, `application.png`, `application.jpg`: wyłącznie obraz, wymagają rzeczywistego OCR.
- `application_mixed.pdf`: strona tekstowa oraz druga strona obrazowa.
- `application_missing.pdf`: celowo brak VIN, roku, składki i poprzedniego numeru polisy.
- `application_holdout.pdf`: niezależny wariant kolejności etykiet, separatorów i sekcji uczestników.
- `unsupported_property.pdf`: dokument nieruchomościowy poza profilem automatycznego odczytu.
- `encrypted.pdf` i `corrupted.pdf`: świadomie niepoprawne wejścia testów walidacji.

`expected.json` przechowuje oczekiwania oddzielnie. Aplikacja i parser nie mogą go czytać.
Składnia klucza pola: `grupa.indeks.kod`. Pliki nie wyznaczają skuteczności na rzeczywistych dokumentach.

`fields` i `same_fields_as` oznaczają treść wzorcową dokumentu. `accepted_ocr_readings` dokumentuje zaobserwowane błędy konkretnego Tesseract (np. O/0, ł/t) jako alternatywne surowe odczyty, które muszą pozostać oznaczone do weryfikacji. Nie są to poprawne dane biznesowe ani podmiany wykonywane przez parser. Nielegalny VIN i nieprawidłowy e-mail powinny pozostać puste z ostrzeżeniem.

Odtworzenie: `uv run --project backend python scripts/generate_fixtures.py`.

Generator używa dołączonego fontu DejaVu Sans z `fixtures/fonts`, aby zachować polskie znaki i ten sam układ na różnych systemach. Licencja fontu znajduje się obok pliku TTF.
