# Stan Broker Office — naprawa i wspólna skrzynka, 2026-09-05

Rozwinięto istniejące MVP od commita `b9460085db68688c2c38b2c896cb5106ee6cadbd` na `codex/broker-office-mailbox`. Naprawa dokumentów jest osobnym commitem `2c1ec08`, poczta `9ec7d60`, zachowanie bajtów .eml przy klonowaniu `4d495f1`. Gałąź została wypchnięta do GitHub. Historyczne wyniki pierwszego MVP zachowano w [HISTORICAL_STATUS_b946008](HISTORICAL_STATUS_b946008.md); nie są wynikami obecnego odbioru.

## Etap A

A01–A09 odtworzono i poprawiono, z rozróżnieniem części A08, w której zachowanie notatki po konflikcie było już prawidłowe. Szczegółowe dowody i regresje: [REMEDIATION_STATUS](REMEDIATION_STATUS.md). Lockfile przeszedł czyste npm ci na macOS ARM64 i Linux ARM64/AMD64. Instalacja Python pozostaje zamrożona. Obowiązkowy OCR zawodzi przy braku programu/języków.

Numerowany profil wniosku komunikacyjnego ma źródła, jeden uczestnik może pełnić obie role, a NNW 10000 PLN jest kwotą własnego zakresu, nie składką. Ręczne grupy i ratunek, aktualne ostrzeżenia i potwierdzenia, bezpieczny eksport oraz pełne selektory przeszły API i przeglądarkę. Historyczna migracja zachowała dwie wcześniejsze rewizje/XLSX i wszystkie 41 plików początkowej demonstracji.

Przed rozpoczęciem poczty wykonano prawdziwy proces dokumentowy. Native: 5 scenariuszy Playwright w osobnych biegach; po przebudowie Compose komplet **5 passed / 26,3 s**. Frontend A: lint, TypeScript, 23 testy i build. Backend przed ostatnimi dodatkowymi regresjami: 123 passed /18,97 s; osobny końcowy zestaw ekstrakcji/eksportu 74 passed.

## Poczta

Działa PostgreSQL/API/UI i rzeczywisty klient IMAP. Kolejka pracy, własność, wersje, przekazanie ADMIN, jawne zakończenie/ponowne otwarcie i osobiste odczyty są oddzielone. Źródła demo i IMAP pozostają osobnymi rekordami; sam adres nadawcy nie przypisuje klienta. Każdy nowy UID, także odpowiedź po done, tworzy todo. Załącznik jest idempotentnie zapisywany w dokumentach wybranego klienta i używa istniejącego OCR/XLSX.

MIME ma tekstowy widok, limity, prywatne pliki i powody blokady części. IMAP używa EXAMINE, UID i BODY.PEEK ze sprawdzonym TLS; ma trwałe pending, granicę startową, dzierżawę, limitowane ponowienia i jawne odbudowanie po UIDVALIDITY. Workery poczty i OCR są osobne. Konfiguracja serwerowa i synchronizacja zewnętrzna domyślnie wyłączona.

## Wykonane próby etapu B

- Rzeczywisty Dovecot 2.4.5/TLS/IMAP4rev1: flags, UID i pełne SHA-256 wiadomości przed/po pozostają identyczne, także Seen; niewłaściwy certyfikat odrzucony. Protokół nie jest mockiem.
- 23 regresje synchronizacji na PostgreSQL: granica i mail podczas inicjalizacji, sparse/empty UID, przerwanie/retry, auth/TLS, fencing, recovery UIDVALIDITY, test bez treści i konfiguracja. Osobny rzeczywisty Dovecot → sync → PostgreSQL → API/read → powtórny sync: 1 passed /1,29 s.
- Pełny Playwright poczty na Dovecot + Redis/Celery: **2 passed /48,1 s**. Inject → worker → todo → osobiste otwarcie → przejęcie → drugi pracownik → klient 26 z dalszej strony → PDF/OCR/weryfikacja/rzeczywiste komórki XLSX → done → kolejna odpowiedź nowe todo. Newsletter no_action wymaga powodu.
- Przy zamkniętej przeglądarce 30-stronicowy OCR trwał 25,01 s, a beat/mailworker pobrał nowy mail po 4,08 s podczas statusu running OCR. Mail pozostał todo bez właściciela i odczytów. Sam wielokrotnie powielony dokument OCR zakończył się oczekiwanym błędem limitu pozycji zakresu; nie oznaczamy go jako udanej ekstrakcji.

Końcowy zbiorczy backend na macOS: **188 passed, 1 skipped /25,22 s**. Pominięty jest wyłącznie test jawnie wymagający serwera IMAP, wykonany oddzielnie na najnowszym kodzie: **1 passed /1,50 s** z prawdziwym Dovecot/TLS i dziennikiem plików. OCR był obowiązkowy (`OCR_REQUIRED=1`). Ruff i kontrola migracji przechodzą. Frontend: **32/32 komponenty**, strict TypeScript, ESLint, Prettier i build PASS.

Świeży Compose B `broker-check-57090f14bf` na 5175: build, migrate, brak oczekujących migracji i 7 działających usług. **9/9 Playwright /1,8 min** na końcowym backendzie (w tym konflikty, HTML bez zewnętrznych żądań i klawiatura przy 390 px). Pierwsza próba testu focus trafiła na chwilowo disabled przycisk podczas pobierania właściciela; test czeka teraz na aktywny przycisk i sprawdza focus. Wszystkie scenariusze ponowiono. Cztery nowe zrzuty syntetyczne w SCREENSHOTS; 390 px bez poziomego przewijania.

Rozszerzony backup/restore i restart źródła **PASS**: 25 tabel, 67 oryginałów, 7 zatwierdzonych rewizji, 170 plików, 29 maili, 8 załączników, 7 osobistych odczytów i 3 źródła. Hash pełnych tabel poczty porównano przed wstrzymaniem importera WYŁĄCZNIE w odtworzonej bazie. Anonimowe pobrania zwróciły 403, uwierzytelnione raw mail/załącznik/original/PNG/historyczny XLSX były zgodne. Po wznowieniu źródła zachowane są statusy, odczyty, źródłowe pliki, cursor/enabled/version i rewizje. Odtwarzano do nowej własnej bazy, nie nadpisywano źródła.

GitHub Actions na 4d495f1: Compose job SUCCESS; integration ujawnił jeden odmienny odczyt OCR na Ubuntu/Tesseract (`DEMOOO1` zamiast macOS `DEMOO001`). Poprawny wzorzec pozostaje `DEMO001`; uzupełniono wyłącznie jawnie zaobserwowany wariant, z niezmienionymi wymaganiami źródła i ostrzeżeń.

**Końcowy zdalny [workflow 33974462417](https://github.com/JakubLewosz/Ubezpieczalnia/actions/runs/33974462417) dla `fffa3c7784bc861489611bdab538a13a7a4d2e32`: SUCCESS, oba joby `integration` i `compose`.** Wynik odczytano przez API GitHub po zakończeniu. Ubuntu 24.04 AMD64: backend **188 passed, 1 skipped /47,65 s**, następnie obowiązkowy rzeczywisty IMAP **1 passed /1,57 s**, frontend **32 testy** i pełny Playwright **9 passed /2,1 min**. Przeszły zamrożone instalacje, wymagany OCR, kontrola migracji, Ruff, TypeScript, ESLint i build. Osobny job wykonał świeży build/start Compose z własnymi wolumenami. Pominięty w głównym pytest test IMAP został wykonany osobnym krokiem; upload diagnostyki przeznaczony wyłącznie dla błędu pozostał prawidłowo pominięty. Ten wynik dotyczy wskazanego commita kodu; późniejsze uzupełnienie raportu nie zmienia implementacji.

## Ograniczenia

Weryfikowano lokalny serwer IMAP, **nie Interię ani konto kancelarii**. Nie wykonano próby obciążenia 10 osób/500 klientów, Windows/WSL, testu penetracyjnego ani audytu produkcyjnego. Brak SMTP, pełnej historii/spamu/kosza, zewnętrznego AI, antywirusa, docelowego Excela kancelarii, automatycznych klientów/polis i masowej migracji. OCR może mylić O/0, diakrytykę i walutę; wymaga kontroli źródeł. Syntetyczne dane nie określają skuteczności w kancelarii.

Instrukcje od czystego klona: [README](../README.md), [LOCAL_IMAP](LOCAL_IMAP.md), [MAILBOX](MAILBOX.md). Szczegóły lockfile/Compose: [INSTALL_REMEDIATION](INSTALL_REMEDIATION.md). Nie zmieniano widoczności repo, nie scalano gałęzi i nie wdrażano produkcyjnie.
