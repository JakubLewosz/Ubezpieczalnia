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

Uruchom aplikację przez `scripts/dev.py` albo Compose. W terminalu testów ustaw użytkownika i hasło wcześniej jawnie utworzonego konta. Na POSIX hasło wczytaj bez wpisywania go do historii:

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

Przebieg: logowanie → klient → upload → zakończenie rzeczywistego zadania → korekta → zapis → zatwierdzenie → pobranie XLSX. E2E wymaga worker/Redis, a nie tylko serwera Vite. Konto i wytworzone dane testowe pozostają w lokalnej bazie. Raporty/przechwycone pobrania nie trafiają do Git.

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

Workflow `.github/workflows/ci.yml` przygotowuje PostgreSQL, Redis i Tesseract `pol+eng`, uruchamia testy backendu, kontrolę migracji, lint, TypeScript, testy komponentów i build, a następnie prawdziwy przebieg przeglądarkowy z Celery. Hasło E2E i klucz sesji są losowane podczas joba. Zewnętrzne OCR/AI i produkcyjne sekrety nie są wymagane. Job nie zastępuje weryfikacji Docker Compose na komputerze z działającym demonem.

## Rzeczywiste przerwanie workera

5 września 2026 wysłano SIGKILL do procesu wykonującego OCR syntetycznego PDF z 30 powtórzonymi stronami. Nie skracano zegara ani lease w bazie. Worker/beat odzyskały zadanie po naturalnym wygaśnięciu dzierżawy. Druga próba po 374 sekundach od przerwania zakończyła się czytelnym `failed`: „Dokument przekracza limit 30 pozycji żądanego zakresu.” Powtórzony dokument zawierał 90 wystąpień zakresów, więc błąd był oczekiwaną ochroną limitu. W bazie pozostało jedno zadanie, `attempts=2`, bez wyniku silnika; zadanie nie utknęło ani nie wytworzyło pozornego sukcesu. Początkowa asercja lokalnego skryptu oczekująca `succeeded` była zbyt wąska i nie przeszła; późniejsza jawna kontrola sprawdziła końcowy błąd, ponowienie i brak wyniku. Test ten potwierdza odzyskanie po awarii, a nie udaną ekstrakcję tego sztucznie powielonego dokumentu.

## Zaobserwowane ograniczenia rzeczywistego OCR

Lokalny Tesseract 5.5.3 `pol+eng`, syntetyczny font DejaVu Sans i rendering PDF w skali 3 (około 216 dpi) wykazały błędy znaków mimo poprawnego odczytu kwot, dat, numeru wniosku i poprzedniej polisy. W skanie `TEST001` zostało odczytane jako `TESTO01`, a w PNG/JPEG jako `TESTOO1`. W niektórych polach PNG/JPEG znak `ł` stał się `t` (`Przykład` → `Przyktad`). Niektóre adresy e-mail i VIN zawierały niedozwolone znaki, dlatego pozostają puste z ostrzeżeniem. Tekstowy oraz mieszany wariant w tym lokalnym sprawdzeniu zachowały wartości referencyjne.

Parser nie zamienia samodzielnie `O` na `0` ani `t` na `ł`. Każde pole OCR otrzymuje ostrzeżenie i odnośnik do strony; pracownik musi porównać źródło oraz poprawić dane. Poprawne oczekiwania pozostają w `fixtures/synthetic/expected.json` oddzielnie od jawnych `accepted_ocr_readings`. Testy dopuszczają tylko te opisane różnice i wymagają ostrzeżenia przy odstępstwie; nie deklarują pełnej dokładności odczytu. Inna wersja Tesseract może wymagać osobnej oceny zaobserwowanego wyniku, bez zmieniania prawidłowej wartości referencyjnej ani dodawania zgadywanych poprawek do parsera.

Limity silnika: tekst całego dokumentu do 1 MiB UTF-8, do 100 uczestników i 30 pozycji żądanego zakresu. Ich przekroczenie kończy zadanie czytelnym błędem. Kwoty profilu mają maksymalnie 12 cyfr przed przecinkiem i 2 po nim; są eksportowane jako liczby, bez utraty identyfikatorów tekstowych z zerami wiodącymi.
