# Stan MVP — 5 września 2026

Zaimplementowano działający zakres demonstracyjny Broker Office. Kluczowy przebieg wykonano w prawdziwej przeglądarce Chromium: sesja Django → kartoteka → upload → osobny worker Celery/Redis → lokalny odczyt → korekta → zatwierdzona rewizja → pobranie XLSX. Nie są to atrapy API. Baza PostgreSQL i prywatny magazyn zapisują dane na dysku.

## Działające obszary

- Indywidualne konta ADMIN/EMPLOYEE, CSRF także logowania, ograniczanie prób według IP i konta, odwołanie sesji, administracja kontami i reset hasła bez poczty. Panel Django korzysta ze wspólnego logowania; flaga `is_staff` nie zastępuje roli biznesowej.
- Osoby i organizacje, edycja, wyszukiwanie także przez numer polisy, normalizacja bez zmiany oryginalnych danych, paginacja/sortowanie i archiwizacja. Ostrzeżenia o potencjalnych duplikatach oraz unikalność podanego PESEL/NIP wymuszona przez PostgreSQL również przy równoczesnym dodawaniu.
- Ręczne polisy, kilka osób w roli ubezpieczonego i ta sama osoba w obu rolach, powiązane dokumenty, Decimal/NULL składki, daty kalendarzowe, wyliczany status oraz domknięte terminy Europe/Warsaw.
- Prywatne oryginały i PNG stron, walidacja formatów/zawartości/rozmiarów, sumy kontrolne, brak publicznego `/media/`. DOCX/XLSX tylko jako załączniki.
- pypdf, PDFium oraz Tesseract `pol+eng`: rzeczywiste tekstowe, obrazowe i mieszane wejścia. Profil komunikacyjnego wniosku brokerskiego, jawne braki i ostrzeżenia, źródła/strony/metoda. Rozdzielone numery, daty ochrony, data dokumentu, składka i suma.
- Wynik silnika, szkic i zatwierdzenia są oddzielne. Korekty nie udają źródła, poprzednie rewizje zostają zachowane, ponowny odczyt wymaga jawnego przejęcia wyniku do szkicu. Konflikty wersji zamiast cichego nadpisania.
- `review_export_v0`: arkusze Informacje/Dane, konkretna zatwierdzona rewizja, powtarzalne grupy, daty/liczby/zera wiodące, tekst bez aktywnych formuł, audyt eksportu.
- Polski, jasny interfejs, źródła przełączające strony, powiększenie, układ mobilny, etykiety/fokus/klawiatura i ochrona niezapisanych zmian. Brak pustych zakładek przyszłych integracji.

## Faktycznie wykonana weryfikacja

| Weryfikacja | Wynik |
|---|---|
| Świeża baza PostgreSQL 17.11, migracje, jawny seed | wykonane; seed nie resetuje danych przy starcie |
| `pytest backend/tests` | **73 passed**, 9,90 s w końcowym pełnym uruchomieniu |
| Prawdziwy Tesseract, tekst/scan/mixed/PNG/JPEG oraz holdout | wykonane, z jawnymi odchyleniami OCR opisanymi w TESTING |
| Dwuwątkowe zapisy do PostgreSQL | jeden sukces i jeden konflikt; tożsamość klienta, szkic i zatwierdzenie |
| Konta i pliki bez sesji, CSRF, reset konta, role | sprawdzone testami backendu |
| XLSX: zawartość, daty, kwoty, identyfikatory, niezmienność, formuły | sprawdzone przez openpyxl i XML wygenerowanego pliku |
| Migracje `--check --dry-run`, Ruff backend + scripts | poprawne; brak zmian migracji |
| Frontend ESLint, TypeScript strict, Prettier | poprawne |
| Vitest/Testing Library | **10 passed** |
| Vite build | poprawny |
| Playwright Chromium, prawdziwe API + worker | **2 passed**, 8,3 s po poprawkach etykiet i obserwowania raportów Vite |
| Dodatkowa obsługa przez przeglądarkę | firma + reload; polisa z trzema relacjami, Decimal/NULL, edycja i archiwizacja |
| Wizualna kontrola i interakcje źródła/powiększenia | 9 zrzutów, widoki 1440 i 390 px, bez poziomego overflow przy 390 px i bez błędów JS |
| Przerwanie procesu OCR | rzeczywisty SIGKILL procesu wykonawczego; naturalne wygaśnięcie lease, druga próba i kontrolowany błąd limitu zakresów po 374 s; brak utknięcia i dodatkowego wyniku |
| Backup/restore do osobnej bazy | zgodne liczniki 20 tabel, SHA-256 7 oryginałów i 41 plików oraz pola 2 rewizji; API odmówiło 3 anonimowych pobrań, uwierzytelnione oryginał/PNG/historyczny XLSX poprawne |
| Restart aplikacji, PostgreSQL i Redis | te same liczniki, pliki i rewizje; w przeglądarce zachowana sesja, widoczny szkic/podgląd i pobranie oryginału HTTP 200 |
| Własność lokalnego Redis i konfiguracja startu | 5 testów zgodności/odmowy obcej instancji; rzeczywisty status/start/stop własnych usług; jawne środowisko produkcyjne poprawnie blokuje `dev.py` mimo developerskiego `.env` |
| `docker compose config --quiet` | poprawna konfiguracja |

Pierwsze uruchomienia Playwright zatrzymały się na zbyt dokładnym dopasowaniu etykiety Hasło z gwiazdką. Poprawiono dostępność etykiety, selektor i wykluczono raporty Playwright z obserwacji Vite; końcowy pełny przebieg przeszedł. Nie zaliczano tych przerwanych uruchomień jako sukcesów.

## Środowisko i czego nie sprawdzono

Uruchomiono natywnie na macOS: Python 3.12.13, Django 5.2.17, DRF 3.18.0, PostgreSQL 17.11, Redis 8.10.1, Tesseract 5.5.3 z pol/eng, Node 24.11.0. Pełne wersje zależności są w lockfile i LICENSES.

Demon Docker nie działał (brak gniazda `~/.docker/run/docker.sock`). **Nie wykonano budowania ani uruchomienia kontenerów Compose**, testów na Windows/WSL ani zdalnego joba GitHub Actions. Compose przypina Redis 8.2.9 i Node 22.23.2, inne niż wersje natywne; te obrazy wymagają oddzielnego przebiegu. Dokładne komendy znajdują się w README i TESTING. Nie wykonywano testu obciążeniowego 10 pracowników/500 klientów, testów penetracyjnych ani testów na danych rzeczywistych.

`DJANGO_ENV=production ... check --deploy` pozostawia jedynie W021: HSTS preload nie jest włączony bez uzgodnionej domeny. Lokalny tryb HTTP celowo zgłasza ostrzeżenia wdrożeniowe; nie jest konfiguracją produkcyjną. Natywne kontrolki daty w formularzach mogą używać formatu języka przeglądarki/systemu; prezentacja zapisanych dat i kwot aplikacji jest polska, a API używa ISO/Decimal.

## Znane ograniczenia i następny etap

OCR może mylić O/0, znaki diakrytyczne i znak `@`. Nie zastępujemy ich domysłami. Nielegalny VIN i niejednoznaczny e-mail pozostają puste z ostrzeżeniem; inne wartości OCR wymagają kontroli źródła. Syntetyczny zestaw nie określa skuteczności na dokumentach kancelarii.

To lokalna demonstracja: brak antywirusa, MFA, produkcyjnej izolacji/monitoringu i uzgodnionych zasad retencji/dostępu. Brak poczty, migracji i docelowego Excela jest świadomą granicą zakresu. Nie deklarujemy gotowości produkcyjnej ani zgodności z RODO.

Następny krok: warsztat odbiorczy na syntetycznych dokumentach, ustalenie ról i procesu odnowień, uzgodnienie docelowego mapowania Excel oraz checklisty bezpieczeństwa/infrastruktury przed jakimikolwiek rzeczywistymi danymi. Szczegóły: DECISIONS, SECURITY i BACKLOG.
