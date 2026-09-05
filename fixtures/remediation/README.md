# Syntetyczne próby A02–A06

Wyłącznie DANE TESTOWE, kontakty `.invalid`. Pliki nie reprezentują rzeczywistej kancelarii.

`numbered.txt` odwzorowuje numerowany wniosek z zadania. `variant.txt` zmienia kolejność sekcji, łamanie wierszy, oznaczenia, skróty, interpunkcję i zapis kwot. `holdout.txt` jest osobnym wariantem regresji (rzymska numeracja, dane uczestnika przy nagłówku, osobne wartości); jego oczekiwania nie są odczytywane przez parser ani generator. Osobne `expected.json` zapisuje ręcznie oczekiwane odpowiedzi, w tym kontrolowane braki. Nie jest to statystyka skuteczności kancelarii.

`uv run --project backend python scripts/generate_remediation_fixtures.py` odtwarza PDF tekstowe, skan, PNG/JPEG i PDF mieszany. Renderer korzysta wyłącznie z zatwierdzonego fontu syntetycznych fixtures. OCR jest wykonywany lokalnym Tesseract pol+eng; testy nie poprawiają znaków przez zgadywanie. Drobne pomyłki OCR mają jawne ostrzeżenia i są kontrolowane w testach, bez przedstawiania ich jako prawdziwych danych.

Zmierzony lokalny Tesseract 5.5.3 odczytał `DEMO001` jako `DEMOO001` i `Pln` jako `Pin`. Pierwszy błąd zachowuje ostrzeżenie OCR; drugi pozostawia sumę NNW pustą z rzeczywistym fragmentem oraz ostrzeżeniem o niejednoznacznej kwocie/jednostce. Pracownik może przepisać `10000` po sprawdzeniu źródła. `ocr_observations.json` odnotowuje te konkretne odstępstwa; oczekiwane poprawne odpowiedzi pozostają odrębne i nie zostały zmienione na błędny odczyt.
