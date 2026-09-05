# Lokalny IMAP — rzeczywisty serwer testowy

Ta procedura używa wyłącznie syntetycznej skrzynki `shared@example.invalid` na lokalnym Dovecot. Nie łączy się z Interią, nie wymaga hasła kancelarii i nie wysyła poczty. Dostarczanie fixture do tej skrzynki jest osobną, jawną operacją testową.

## Wymagania i wybór serwera

Wymagany działający Docker Engine/Desktop, Compose, Python i OpenSSL z obsługą `req -addext` (OpenSSL 1.1.1+/3; na Windows można wykonać polecenia w WSL). Używamy opublikowanego obrazu **Dovecot CE 2.4.5**, przypiętego do digestu `sha256:c807be4fb5a97d9c3a90770569d3a6c4cbdcb36742ad41f90409cbd929166553`. Jest to rzeczywista implementacja IMAP, a nie podstawione odpowiedzi metod klienta. Konfiguracja wyłącza eksperymentalny IMAP4rev2; test wymaga IMAP4rev1. Obraz i sposób konfiguracji opisuje [oficjalna dokumentacja Dovecot](https://doc.dovecot.org/2.4.5/installation/docker.html).

Kod Dovecot ma głównie LGPLv2.1, wybrane biblioteki MIT i wskazane wyjątki — [COPYING](https://github.com/dovecot/core/blob/main/COPYING). Źródła oficjalnych receptur obrazów mają CC BY-NC-SA 4.0, z osobnym dopuszczeniem komercyjnego użycia publikowanych obrazów — [repozytorium autorów](https://github.com/dovecot/docker). Nie kopiujemy ich Dockerfile do projektu. Obraz służy tu wyłącznie lokalnej weryfikacji i nie jest dodawany jako zależność wdrożenia kancelarii.

## Pierwsze uruchomienie

Z katalogu sklonowanego projektu:

```sh
python3 scripts/local_imap.py init
python3 scripts/local_imap.py start
uv run --project backend python scripts/check_imap_protocol.py --fixture fixtures/mail/application.eml
```

`init` tworzy `.local/imap-test` (0700), losowe hasło, jego hash dla Dovecot oraz lokalny certyfikat TLS ważny 30 dni. Pliki mają 0600; hasło i klucz nie są wypisywane. W GitHub Actions hasło jest maskowane przed zapisaniem. Ponowne `init` odmawia nadpisania danych. Inny wolny port wybiera się przy tworzeniu, np. `init --port 19994`. Skrypt nie przyjmuje adresu zdalnego serwera.

`start` tworzy osobny projekt `broker-imap-test`, prywatne wolumeny konfiguracji i Maildir oraz publikuje wyłącznie `127.0.0.1:19993`. Certyfikat i plik uwierzytelnienia w wolumenie Dovecot należą do UID 1000, a osobny wolumen sekretu aplikacji do UID 10001. Proces inicjujący wolumeny nie ma sieci i odmawia zastąpienia istniejącej konfiguracji inną. Serwer działa jako użytkownik niebędący rootem, z plikami obrazu tylko do odczytu, bez POP3, SMTP, submission i zdalnego HTTP API. Capability `SYS_CHROOT` pozostaje potrzebna do uruchomienia binarnego pliku login z oficjalnego obrazu; pozostałe capabilities są odebrane.

Certyfikat ma SAN dla lokalnego adresu, `localhost`, `imap-test` i `host.docker.internal`. Klient aplikacji ufa mu **tylko** przez jawny `MAIL_CA_FILE`; nie wyłączamy weryfikacji certyfikatu/hosta ani nie zmieniamy systemowego magazynu zaufania.

Test protokołu dodaje dwie kopie syntetycznego wniosku z różnymi UID, jedną z flagą `Seen`. Następnie produkcyjny `IMAPClient` pobiera obie wiadomości przez TLS i sprawdza granice UID. Porównuje wszystkie UID, SHA-256 treści i trwałe flagi przed/po odczycie, odrzucenie niezaufanego certyfikatu oraz blokadę poleceń zmieniających flagi. Tymczasowa sesyjna flaga `Recent` nie jest stanem przeczytania użytkownika i nie jest częścią porównania trwałych flag. Test ma limit 100 wiadomości lokalnej skrzynki i nie usuwa istniejących wiadomości.

## Demonstracja z aplikacją natywną

Najpierw wykonaj zwykłą instalację, migracje i utworzenie kont opisane w README. Zatrzymaj dotychczasowy `scripts/dev.py`, pozostawiając PostgreSQL i Redis. Następnie:

```sh
uv run --project backend python scripts/local_imap.py run-dev
```

Polecenie uruchamia tę samą aplikację i magazyn z dodatkowymi zmiennymi procesu: lokalny host/port, `MAIL_SYNC_ENABLED=true`, ścieżki prywatnego hasła i CA, INBOX oraz interwał 15 s. Nie zmienia głównego `.env`. Zachowuje obsługę Ctrl+C/SIGTERM i nie zostawia procesu pośredniego.

W aplikacji ADMIN świadomie uruchamia import. Pierwsze udane otwarcie folderu ustala trwałą granicę; wiadomości istniejące wcześniej, również z testu protokołu, nie należą do nowej kolejki pracy. Zaczekaj na stan poprawnej inicjalizacji. W osobnym terminalu:

```sh
uv run --project backend python scripts/local_imap.py inject --fixture fixtures/mail/application.eml
```

Worker pobierze wiadomość bez otwartej przeglądarki. Pojawi się nowa pozycja do obsługi. Przejdź do niej, przejmij pracę, wskaż klienta i zapisz PDF w dokumentach; dalszy odczyt/weryfikacja/XLSX korzysta z istniejącego modułu dokumentów.

Osobną, ograniczoną próbę oddzielenia kolejek wykonasz przy działającej aplikacji i zainicjalizowanym lokalnym źródle:

```sh
uv run --project backend python scripts/verify_mail_worker.py --credentials .local/demo-credentials.json
```

Wskazany prywatny JSON ma klucze `username` i `password` jawnego konta demonstracyjnego. Skrypt tworzy syntetyczną kartotekę i 30-stronicowy dokument, uruchamia prawdziwy OCR, dodaje newsletter do Dovecot i obserwuje import przez beat/worker bez przeglądarki i bez ręcznego zlecenia synchronizacji. Dokument oraz historię próby pozostawia do przeglądu; niczego nie usuwa. Powtarzanie strony może poprawnie zakończyć odczyt błędem limitu liczby pozycji zakresu — to celowy długi materiał techniczny, nie wzorzec parsera.

Po oznaczeniu pozycji jako obsłużonej dodaj następną wiadomość:

```sh
uv run --project backend python scripts/local_imap.py inject --fixture fixtures/mail/reply.eml
uv run --project backend python scripts/local_imap.py inject --fixture fixtures/mail/newsletter.eml --seen
```

Nowa odpowiedź jest nową pozycją `todo`; wcześniejsze `done` pozostaje bez zmian. Flaga `Seen` fixture newslettera nie oznacza osobistego otwarcia ani zakończonej obsługi. Injector używa APPEND **wyłącznie na lokalnym adresie pętli zwrotnej**, dla `.eml` z `fixtures/mail` z oznaczeniem `DANE TESTOWE`. Klient odbierający pocztę w aplikacji nie ma takiej operacji. Nazwy plików i katalog pozostają kontrolowane; injector nie przyjmuje plików spoza tych fixtures.

## Demonstracja aplikacji w Compose

Uruchom lokalny serwer poleceniami `init`/`start` powyżej, a następnie po zwykłym przygotowaniu aplikacji:

```sh
docker compose -f compose.yaml -f compose.local-imap.yaml build
docker compose -f compose.yaml -f compose.local-imap.yaml up -d db redis
docker compose -f compose.yaml -f compose.local-imap.yaml run --rm backend python manage.py migrate
docker compose -f compose.yaml -f compose.local-imap.yaml up -d --wait
```

Jawny plik `compose.local-imap.yaml` przyłącza backend i procesy robocze do prywatnej sieci serwera testowego oraz montuje oddzielny wolumen sekretu aplikacji tylko do odczytu. Konto aplikacji utwórz tak jak w README, dodając oba `-f` do polecenia seed. Późniejsze włączenie importu i wstrzykiwanie fixtures jest identyczne jak w demonstracji natywnej. Zwykły `compose.yaml` nie włącza tej integracji.

## Kolejki, restart i wyłączenie

Ciężki odczyt działa na kolejce `ocr` w osobnym procesie. Ten sam worker obsługuje dawną `celery`, aby stare zadania odczytu nie zostały bez odbiorcy i nie zajmowały procesu poczty. Worker poczty obsługuje `mail` i krótkie zadania `maintenance`. Nowe odczyty są kierowane do `ocr`. Beat zleca odzyskiwanie zadań odczytu, okresowe pobieranie poczty i ograniczone porządkowanie rezerwacji plików po przerwanych zapisach; przeglądarka nie steruje harmonogramem.

ADMIN może wstrzymać import bez zatrzymywania aplikacji. Pełne wyłączenie lokalnego źródła: zatrzymaj `run-dev` i uruchom zwykły `scripts/dev.py` z konfiguracją `MAIL_SYNC_ENABLED=false` (domyślnie). W Compose uruchom ponownie bazowy plik bez `compose.local-imap.yaml`. Sam serwer zatrzymasz:

```sh
python3 scripts/local_imap.py stop
```

To zachowuje wolumeny, UID, zawartość i konfigurację. Ponowny `start` nie zeruje historii; zwykły restart aplikacji nie wyznacza nowej granicy. Nie kasuj `.local/imap-test` ani wolumenów, aby zamaskować błędy testów. Certyfikat po 30 dniach wymaga jawnego przygotowania nowego środowiska testowego albo kontrolowanej wymiany, bez wyłączania walidacji TLS.

## Wykonana weryfikacja i granice

2026-09-05 na macOS arm64/Docker Desktop 29.4.1 wykonano prawdziwy test produkcyjnego klienta z Dovecot 2.4.5: poprawny TLS, IMAP4rev1, dwa fetch, brak zmian flag i treści, zakresy bez nowych UID, zakaz STORE oraz odmowę niezaufanego certyfikatu. JSON dowodu zapisuje się wyłącznie w `.local/imap-test/protocol-result.json`. CI ma obowiązkowy krok tego testu; wykonanie zdalne jest raportowane oddzielnie od lokalnego.

Próba oddzielnych kolejek także przeszła: rzeczywisty OCR 30 stron trwał **25,01 s**, a newsletter został pobrany po **4,08 s**, kiedy OCR pozostawał `running`. Wiadomość miała `todo`, brak właściciela i zero osobistych odczytów. OCR następnie zakończył się kontrolowanym błędem limitu 30 powtórzonych elementów zakresu. Dowód pozostaje w `.local/mail-worker-result.json`; jest to wynik konkretnej próby, nie gwarantowany czas odbioru kancelarii.

Nie wykonano próby na Interii ani na prawdziwej skrzynce kancelarii. Test Dovecot nie dowodzi zgodności wszystkich zachowań konkretnego dostawcy. Instrukcja przyszłego podłączenia świadomie udostępnionego konta testowego i ograniczenia INBOX są w `MAILBOX.md`. Brak skanera antywirusowego pozostaje ograniczeniem demonstracji.
