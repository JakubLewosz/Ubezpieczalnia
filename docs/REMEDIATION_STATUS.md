# Naprawy podstawy i wspólna skrzynka — rejestr wykonania

Punkt odniesienia: `b9460085db68688c2c38b2c896cb5106ee6cadbd`; przy rozpoczęciu HEAD był identyczny, drzewo czyste. Gałąź robocza: `codex/broker-office-mailbox`. Nie dołączono osobnego pliku audytu ani ZIP; przypadki pochodzą z nowego zlecenia w REMEDIATION_SPEC.

Ten dokument jest aktualizowany na podstawie rzeczywiście wykonanych prób. Wcześniejsze 73/10/2 testy dotyczą pierwszego MVP i nie potwierdzają jeszcze nowych wymagań.

| Problem | Początkowy dowód na bieżącym kodzie | Regresja i naprawa | Wykonana weryfikacja |
|---|---|---|---|
| A01 | Odtworzone EUSAGE na czystym npm 10.9.8/11.6.1 | Uzupełniony lockfile bez aktualizacji istniejących wersji; OCR preflight; oddzielny Compose | npm ci macOS ARM64/Linux ARM64/AMD64; lint/TS/23 testy/build; rzeczywisty build/start i OCR przez worker w Compose. Zdalne nowe CI jeszcze przed publikacją. |
| A02 | Odtworzone nierozpoznanie numerowanego wniosku i błędna wspólna etykieta starego profilu | Ograniczony profil v1, osobne kwoty zakresu, źródła i brak zgadywania | Warianty + holdout; PDF/scan/PNG/JPEG/mixed z rzeczywistym Tesseract. Tekst NNW 10000 PLN; OCR ma jawne braki/ostrzeżenia (fixtures/remediation/README.md). |
| A03 | Odtworzone blokowanie liczby pól | Grupy UUID nadawane przez serwer, add/remove, ręczny ratunek, audyt i wersja | API i pełny Playwright: druga osoba i zakres w drugiej rewizji oraz XLSX; pierwsza rewizja niezmienna. |
| A04 | Odtworzone niepełne selektory i brak filtrów | Filtrowanie przed paginacją, wyszukiwanie, zachowanie zaznaczeń | PostgreSQL: >25 klientów/polis/dokumentów, archiwum i konkurencyjne przypisanie; Playwright wybiera drugą stronę i zachowuje wybór po wyszukaniu. |
| A05 | Odtworzone zatwierdzanie z nieaktualnymi ostrzeżeniami | Bieżąca walidacja, version + warning_digest + świadome potwierdzenie; notatka dla sprzeczności | API: daty, VIN, e-mail, jednostki, wartości zerowe, utrzymanie sprzeczności źródła, nieaktualne potwierdzenie. |
| A06 | Odtworzone U+0001 → wyjątek XLSX | Walidacja XML i długości także metadanych; kontrolowane 400 starej rewizji | Rzeczywisty API/XLSX: polskie znaki, nowe linie, identyfikatory, tekst formułopodobny, limity i historyczny eksport. |
| A07 | Odtworzone dodatkowe wysłanie formularza po kliknięciu pomocniczym | Domyślne type=button; tylko zapis submit | Test komponentowy i dwie sesje Playwright: reload konfliktu nie wysyła drugiego PATCH. |
| A08 | Odtworzone edytowalne pola podczas opóźnionego PATCH; zachowanie treści przy konflikcie już działało w próbie | Blokada podczas zapisu, ochrona stanu i spóźnionych odpowiedzi | 23 testy komponentowe; realne dwa konta, opóźniony PATCH, 409, anulowanie i świadomy reload. |
| A09 | Potwierdzony brak maskowania w kolejności komend CI (bez ponownej publikacji wartości) | add-mask przed GITHUB_ENV, diagnostyka wyłącznie z listy dozwolonych liczników | Kontrola skryptów i prób wymaganego OCR; brak treści/sekretów w nowych artefaktach. |

## Bramka etapu A — wykonana przed rozpoczęciem B

Native PostgreSQL, Redis, Django, Celery i Tesseract: cały zestaw backendu **123 passed / 18.97 s** przed dodatkowymi 7 regresjami; później agent wykonał **74 passed** w modułach odczytu/eksportu. Frontend lint, strict TypeScript, **23 testy**, build. **5 scenariuszy Playwright** zaliczono w osobnych biegach: wcześniejsze 2, numerowany dokument z rewizjami i XLSX, dwa konta/opóźniony PATCH oraz selektory >25 rekordów. Pełny nowy proces dokumentowy trwał 7.9 s.

Migracja 0002 na istniejącej demonstracji zachowała JSON obu historycznych zatwierdzeń, ich eksport XLSX i SHA-256 wszystkich 41 plików. Przed migracją wykonano prywatną kopię. Pierwszy nowy E2E wykrył błąd PostgreSQL FOR UPDATE na nullable JOIN; poprawiono blokowanie na konkretne tabele, powtórzony proces przeszedł. Nowe oddzielne wolumeny Compose uruchomiono i wykonano rzeczywisty OCR przez API/Celery. Po przebudowie końcowych obrazów A pełne 5 testów Playwright na Compose przeszło w 26,3 s. Nowe zdalne CI będzie raportowane po publikacji.

## Etap B

Rozpoczęto po zaliczeniu powyższej bramki. Zakres obejmuje PostgreSQL/API/UI, MIME, idempotentny import i załączniki, read-only IMAP z lokalnym serwerem TLS, osobiste przeczytanie oddzielne od pracy, współbieżność, oddzielną kolejkę i integracyjny Playwright.

## Plan

1. Odtworzyć i naprawić A01–A09 równolegle w rozłącznych obszarach kodu; zachować bazę i dawne migracje.
2. Wykonać migrację istniejącej demonstracji i pełny dokument → korekta struktury → ostrzeżenia → zatwierdzenie → XLSX, przegląd UI oraz commit etapu A.
3. Zaimplementować model pracy i import MIME, klienta IMAP, lokalne źródło testowe oraz UI skrzynki; dodać testy podczas pracy.
4. Uruchomić rzeczywisty IMAP/Celery/Playwright, konflikty i odporność, backup/restore i restart; uzupełnić instrukcje, wyniki, screenshots oraz logiczne commity.

Ochrona źródłowej demonstracji: testy Django korzystają z odrębnej bazy testowej; Compose używa oddzielnego projektu/wolumenów. Istniejących plików, zatwierdzeń ani bazy nie usuwa się dla przejścia testów.
