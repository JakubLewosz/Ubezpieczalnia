# Syntetyczne próby A02–A06

Wyłącznie DANE TESTOWE, kontakty `.invalid`. Pliki nie reprezentują rzeczywistej kancelarii.

`numbered.txt` odwzorowuje numerowany wniosek z zadania. `variant.txt` zmienia kolejność sekcji, łamanie wierszy, oznaczenia, skróty, interpunkcję i zapis kwot. `holdout.txt` jest osobnym wariantem regresji (rzymska numeracja, dane uczestnika przy nagłówku, osobne wartości); jego oczekiwania nie są odczytywane przez parser ani generator. Osobne `expected.json` zapisuje ręcznie oczekiwane odpowiedzi, w tym kontrolowane braki. Nie jest to statystyka skuteczności kancelarii.

`uv run --project backend python scripts/generate_remediation_fixtures.py` odtwarza PDF tekstowe, skan, PNG/JPEG i PDF mieszany. Renderer korzysta wyłącznie z zatwierdzonego fontu syntetycznych fixtures. OCR jest wykonywany lokalnym Tesseract pol+eng; testy nie poprawiają znaków przez zgadywanie. Drobne pomyłki OCR mają jawne ostrzeżenia i są kontrolowane w testach, bez przedstawiania ich jako prawdziwych danych.

Zmierzony lokalny Tesseract 5.5.3 odczytał `DEMO001` jako `DEMOO001` i `Pln` jako `Pin`. Pierwszy błąd zachowuje ostrzeżenie OCR; drugi pozostawia sumę NNW pustą z rzeczywistym fragmentem oraz ostrzeżeniem o niejednoznacznej kwocie/jednostce. Pracownik może przepisać `10000` po sprawdzeniu źródła. `ocr_observations.json` odnotowuje te konkretne odstępstwa; oczekiwane poprawne odpowiedzi pozostają odrębne i nie zostały zmienione na błędny odczyt.

W rzeczywistych uruchomieniach GitHub Actions [33973869722](https://github.com/JakubLewosz/Ubezpieczalnia/actions/runs/33973869722) i [33973926507](https://github.com/JakubLewosz/Ubezpieczalnia/actions/runs/33973926507), Ubuntu 24.04 amd64 z Tesseract `5.3.4-1build5` i pakietami pol/eng `1:4.1.0-2` odczytał rejestrację jako `DEMOOO1`. Ten dodatkowy pomiar jest dopuszczony **wyłącznie dla `numbered_scan.pdf`**. Każde odstępstwo nadal wymaga metody OCR, ostrzeżenia i fragmentu obecnego w rzeczywiście odczytanej stronie. Parser nie poprawia znaków przez zgadywanie; prawidłowe oczekiwanie `DEMO001` w `expected.json` pozostaje bez zmian. Wynik z CI nie jest procentem skuteczności kancelarii.
