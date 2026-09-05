# Testowanie i scenariusz odbioru

Wszystkie dane są syntetyczne. Testy backendu wymagają PostgreSQL, nie SQLite. Najpierw wykonaj konfigurację, instalację i start lokalnych usług z README. Testowy użytkownik PostgreSQL musi mieć `CREATEDB`. Tesseract musi udostępniać `pol` i `eng`.

## Polecenia

Z katalogu repozytorium:

```sh
uv run --project backend pytest backend/tests
uv run --project backend python backend/manage.py makemigrations --check --dry-run
uv run --project backend ruff check backend scripts
npm run check --prefix frontend
npm run lint --prefix frontend
npm test --prefix frontend
npm run build --prefix frontend
```

Backend obejmuje m.in. uprawnienia/CSRF, klientów, daty i role polis, walidację uploadów, realny tekst/OCR, wersjonowanie, idempotencję i zawartość XLSX. Dokładny wynik konkretnego uruchomienia znajduje się w STATUS, a lista przypadków w `backend/tests`. Brak programu lub języka Tesseract powinien powodować czytelny błąd zadania; brak OCR nie jest pozornym sukcesem.

Fixtures `application_text`, `application_scan`, `application_mixed`, PNG/JPEG i holdout nie są wynikami przypisanymi do nazw plików. Kod silnika czyta dokument. Oczekiwania `fixtures/synthetic/expected.json` nie są wejściem parsera. Celowe braki oraz niejednoznaczne rozpoznanie kontaktu wymagają ręcznej korekty. Wynik syntetycznego zestawu nie wyznacza procentowej skuteczności na polisach kancelarii.

## Playwright

Pełny zestaw wymaga dwóch kont EMPLOYEE (`E2E_USERNAME/PASSWORD` i `E2E_SECOND_USERNAME/PASSWORD`) oraz konta ADMIN (`E2E_ADMIN_USERNAME/PASSWORD`), wcześniej jawnie utworzonych na danych testowych. Dla poczty wybierz `E2E_MAIL_SOURCE=imap` i lokalny Dovecot opisany niżej; wariant `demo` służy osobnemu sprawdzaniu interfejsu bez sieci IMAP. Brak wyboru źródła kończy test błędem. Uruchom aplikację przez `scripts/local_imap.py run-dev` albo Compose z jawnym nakładanym plikiem `compose.local-imap.yaml`.

Na POSIX każde hasło wczytaj bez wpisywania go do historii; przykład dla pierwszego konta:

```sh
export E2E_BASE_URL=http://127.0.0.1:5173
export E2E_USERNAME=pracownik.demo
read -rs E2E_PASSWORD
export E2E_PASSWORD
cd frontend
npx playwright install chromium
npm run test:e2e
unset E2E_PASSWORD
```

W PowerShell:

```powershell
$env:E2E_BASE_URL = 'http://127.0.0.1:5173'
$env:E2E_USERNAME = 'pracownik.demo'
$credential = Get-Credential -UserName $env:E2E_USERNAME
$env:E2E_PASSWORD = $credential.GetNetworkCredential().Password
Set-Location frontend
npx playwright install chromium
npm run test:e2e
Remove-Item Env:E2E_PASSWORD
```

Przed `npm run test:e2e` uzupełnij analogicznie drugie konto, ADMIN i źródło. Zestaw obejmuje 5 przebiegów dokumentowych oraz 4 pocztowe: import przez worker, indywidualne odczytanie dwóch osób, pracę odpowiedzialnego, konflikt równoczesnego przejęcia, zachowanie notatki przy zmianie właściciela, bezpieczny HTML i załącznik → dokument → OCR → rewizję/XLSX. Test poczty najpierw utrwala granicę startową lokalnego źródła, następnie dopisuje fixture na lokalnym serwerze. Nie resetuje kursora istniejącego źródła. E2E wymaga workerów/Redis. Konta i dane testowe pozostają w lokalnej bazie. Raporty/przechwycone pobrania nie trafiają do Git.

## Lokalny IMAP i rozdzielenie kolejek

Szczegóły instalacji, TLS, ograniczeń i licencji obrazu: [LOCAL_IMAP.md](LOCAL_IMAP.md). Poniższe polecenia dotyczą wyłącznie serwera testowego z `compose.imap-test.yaml`, opublikowanego na `127.0.0.1:19993`:

```sh
python3 scripts/local_imap.py init
python3 scripts/local_imap.py start
uv run --project backend python scripts/check_imap_protocol.py --fixture fixtures/mail/application.eml
RUN_LOCAL_IMAP_TESTS=1 uv run --project backend pytest backend/tests/test_mail_sync_integration.py
uv run --project backend python scripts/local_imap.py run-dev
```

`init` generuje losowe hasło i certyfikat w ignorowanym `.local/imap-test` z prawami `0600`; nie zastępuje istniejącej konfiguracji. Test protokołu sprawdza rzeczywiste TLS, IMAP4rev1, odrzucenie niezaufanego certyfikatu, dwa różne UID o tej samej treści oraz identyczne UID/SHA-256/flagi przed i po pracy produkcyjnego klienta. Test integracyjny zapisuje przez produkcyjny synchronizator do PostgreSQL i porównuje stan odczytania; wymaga jawnego opt-in. Zwykły zestaw backendu pomija wyłącznie ten test sieciowy, a CI uruchamia go obowiązkowo osobnym krokiem po starcie Dovecot.

OCR konsumuje `ocr,celery` (druga kolejka zachowuje zgodność z dawnymi zadaniami), osobny worker konsumuje `mail,maintenance`. Beat cyklicznie zleca import i odzyskiwanie zadań. Co 60 sekund uruchamia również ograniczone sprzątanie dziennika osieroconych plików; nie skanuje całego magazynu. Niepoprawna konfiguracja poczty pokazuje błąd integracji, zachowując działanie pozostałej aplikacji.

Powtarzalny test bez otwartej przeglądarki: `uv run --project backend python scripts/verify_mail_worker.py` przy uruchomionym lokalnym IMAP i native workerach. Wymaga prywatnego pliku danych logowania wskazanego przez `--credentials` (domyślnie `.local/demo-credentials.json`). Dodaje tylko syntetycznego klienta, 30-stronicowy dokument oraz newsletter, a następnie sprawdza, że wiadomość zostaje pobrana przez beat/mail worker podczas rzeczywistego OCR, pozostaje `todo`, bez właściciela i bez osobistego odczytania. 5 września 2026 wiadomość zaimportowała się po **4,08 s**, gdy OCR wciąż działał; OCR zakończył się po **25,01 s** kontrolowanym błędem przekroczenia 30 pozycji zakresu w sztucznie powielonym dokumencie. Ta próba potwierdza niezależne kolejki, bez pozornego sukcesu ekstrakcji.

Czysty, osobny Compose: `python3 scripts/verify_compose.py --port 5175 --local-imap`. Skrypt losuje nazwę projektu, prywatną konfigurację oraz trzy konta i zachowuje niezależne wolumeny. Nie zatrzymuje ani nie usuwa istniejącej demonstracji. Domyślna konfiguracja Compose bez tego przełącznika pozostawia pocztę wyłączoną.

## Ręczny odbiór

1. Świeży start, migracje, jawne utworzenie kont ADMIN i EMPLOYEE. Ponowne uruchomienie nie resetuje haseł i danych.
2. Sprawdź anonimowy dostęp do API, oryginału, PNG i eksportu; wszystkie muszą wymagać sesji. EMPLOYEE nie administruje kontami. Logout kończy sesję.
3. Dodaj osobę i organizację bez PESEL/NIP. Przetestuj wyszukiwanie po nazwie, kontakcie i numerze polisy, ostrzeżenia o duplikacie oraz archiwizację.
4. Dodaj polisę, w której klient jest ubezpieczającym i ubezpieczonym, oraz drugiego ubezpieczonego. Sprawdź puste i dziesiętne składki oraz datę końca wcześniejszą od początku.
5. Wgraj tekst, skan, mixed i holdout; porównaj metodę/stronę/źródło. Wgraj niepoprawny i zaszyfrowany PDF oraz dokument nieruchomościowy.
6. Otwórz szkic w dwóch oknach. Zapisz w jednym, a następnie w drugim; oczekuj konfliktu i odzyskania świeżej wersji, bez utraty pierwszej zmiany.
7. Zatwierdź, pobierz XLSX, uruchom ponowny odczyt, wprowadź korektę i utwórz kolejną rewizję. Wcześniejszy snapshot/eksport zachowuje dane. Zatwierdzenie nie dodaje automatycznie polisy.
8. Zatrzymaj worker w trakcie zadania, uruchom ponownie worker/beat i poczekaj na wygaśnięcie lease oraz cykl recovery. Zadanie kończy się albo przechodzi w czytelny błąd po ograniczonej liczbie prób.
9. Obejrzyj widok dokumentu na szerokim i wąskim ekranie, nawigację klawiaturą, fokus, powiększenie i źródła pól. Sprawdź ostrzeżenie przed utratą niezapisanych zmian.
10. Zatrzymaj i wznów aplikację oraz bazę. Porównaj identyfikatory/liczby rekordów i pobierz oryginał, następnie wykonaj odtworzenie według SECURITY na oddzielnych danych testowych.

## Kopia i odtworzenie

Powtarzalna natywna próba kopii/odtworzenia, po zatrzymaniu aplikacji i worker/beat, przy działającym PostgreSQL: `uv run --project backend python scripts/verify_backup_restore.py`. Wymaga wcześniejszego przejścia demonstracji i zatwierdzonej rewizji. Szczegóły oraz zakres porównań: SECURITY. Manifest pozostaje w `.local/backups`; polecenie usuwa tylko własną tymczasową bazę.

5 września 2026 wykonano tę próbę na PostgreSQL 17.11: zgadzały się liczniki 20 tabel, sumy 7 oryginałów i wszystkich 41 plików magazynu oraz dane 2 zatwierdzonych rewizji. Odtworzona kopia odmówiła anonimowego pobierania oryginału, PNG i XLSX; po uwierzytelnieniu pobrania oraz porównanie pól eksportu przeszły. Następnie zatrzymano i wznowiono PostgreSQL, Redis oraz aplikację; ten sam manifest potwierdził zachowanie danych. Chromium odtworzył wcześniejszą sesję, formularz szkicu, podgląd i pobrał oryginał.

## CI

Workflow `.github/workflows/ci.yml` przygotowuje PostgreSQL, Redis, Tesseract `pol+eng` i lokalny Dovecot z TLS, uruchamia testy backendu, kontrolę migracji, lint, TypeScript, komponenty/build oraz 9 scenariuszy Playwright z prawdziwymi workerami. Oddzielny job buduje i uruchamia czyste Compose. Tesseract `pol+eng` jest wymagany i jego brak przerywa CI. Losowe hasła kont E2E, lokalnego IMAP, bazy Compose i klucz sesji otrzymują `add-mask` przed zapisem do pliku lub `GITHUB_ENV`. Artefakt błędu zawiera wyłącznie liczniki i identyfikatory testów z allowlisty; brak w nim logów, sesji, treści żądań i trace. Zewnętrzne OCR/AI i produkcyjne sekrety nie są wymagane.

## Rzeczywiste przerwanie workera

5 września 2026 wysłano SIGKILL do procesu wykonującego OCR syntetycznego PDF z 30 powtórzonymi stronami. Nie skracano zegara ani lease w bazie. Worker/beat odzyskały zadanie po naturalnym wygaśnięciu dzierżawy. Druga próba po 374 sekundach od przerwania zakończyła się czytelnym `failed`: „Dokument przekracza limit 30 pozycji żądanego zakresu.” Powtórzony dokument zawierał 90 wystąpień zakresów, więc błąd był oczekiwaną ochroną limitu. W bazie pozostało jedno zadanie, `attempts=2`, bez wyniku silnika; zadanie nie utknęło ani nie wytworzyło pozornego sukcesu. Początkowa asercja lokalnego skryptu oczekująca `succeeded` była zbyt wąska i nie przeszła; późniejsza jawna kontrola sprawdziła końcowy błąd, ponowienie i brak wyniku. Test ten potwierdza odzyskanie po awarii, a nie udaną ekstrakcję tego sztucznie powielonego dokumentu.

## Zaobserwowane ograniczenia rzeczywistego OCR

Lokalny Tesseract 5.5.3 `pol+eng`, syntetyczny font DejaVu Sans i rendering PDF w skali 3 (około 216 dpi) wykazały błędy znaków mimo poprawnego odczytu kwot, dat, numeru wniosku i poprzedniej polisy. W skanie `TEST001` zostało odczytane jako `TESTO01`, a w PNG/JPEG jako `TESTOO1`. W niektórych polach PNG/JPEG znak `ł` stał się `t` (`Przykład` → `Przyktad`). Niektóre adresy e-mail i VIN zawierały niedozwolone znaki, dlatego pozostają puste z ostrzeżeniem. Tekstowy oraz mieszany wariant w tym lokalnym sprawdzeniu zachowały wartości referencyjne.

Parser nie zamienia samodzielnie `O` na `0` ani `t` na `ł`. Każde pole OCR otrzymuje ostrzeżenie i odnośnik do strony; pracownik musi porównać źródło oraz poprawić dane. Poprawne oczekiwania pozostają w `fixtures/synthetic/expected.json` oddzielnie od jawnych `accepted_ocr_readings`. Testy dopuszczają tylko te opisane różnice i wymagają ostrzeżenia przy odstępstwie; nie deklarują pełnej dokładności odczytu. Inna wersja Tesseract może wymagać osobnej oceny zaobserwowanego wyniku, bez zmieniania prawidłowej wartości referencyjnej ani dodawania zgadywanych poprawek do parsera.

Limity silnika: tekst całego dokumentu do 1 MiB UTF-8, do 100 uczestników i 30 pozycji żądanego zakresu. Ich przekroczenie kończy zadanie czytelnym błędem. Kwoty profilu mają maksymalnie 12 cyfr przed przecinkiem i 2 po nim; są eksportowane jako liczby, bez utraty identyfikatorów tekstowych z zerami wiodącymi.

## Odbiór naprawy i poczty — 2026-09-05

- Końcowy backend natywny: `OCR_REQUIRED=1 uv run --project backend pytest backend/tests` — 188 passed, 1 skipped /25,22 s; jeden opt-in IMAP wykonany oddzielnie z Dovecot: 1 passed /1,50 s. To nie pominięcie obowiązkowego OCR.
- 32 komponenty, TS, lint, Prettier i build PASS. Końcowy Compose B, 9 scenariuszy Playwright z prawdziwym API/PostgreSQL/Redis/workerami/Dovecot: 9 passed /1,8 min.
- Trwały journal: rzeczywisty SIGKILL po zapisie bajtów przed commitem, selektywne usunięcie własnego osieroconego pliku; referencje i aktywne blokady/dzierżawy chronione.
- Rozdzielenie kolejek przy zamkniętej przeglądarce: OCR 25,01 s, nowy mail ready/todo po 4,08 s podczas running OCR; brak osobistego odczytu.
- Backup/restore: 25 tabel, 67 oryginałów, 7 rewizji, 170 plików oraz pełne snapshoty 29 wiadomości, 8 załączników, 7 odczytów i 3 źródeł. Import kopii wyłączony przed API, źródło bez zmian. Następny restart aplikacji zachował dane pracy, odczyty, cursor i rewizje.
- Zrzuty i sprawdzenie 1440/390 px, focus/Enter/Space/Escape, brak zewnętrznych żądań z HTML: SCREENSHOTS. Wyniki zdalne i środowiskowe odchylenia OCR: STATUS.

Nie uruchamiaj kilku testów wstrzykujących wiadomości do tego samego Dovecot równocześnie: test niezmienności globalnego zbioru UID wymaga kontrolowanego, niezmienianego przez inny test źródła. Dane z wcześniejszych biegów nie są usuwane.
