# Broker Office

Lokalne MVP do demonstracji obsługi kancelarii ubezpieczeniowej. **Wyłącznie DANE TESTOWE.** Nie jest wdrożeniem produkcyjnym ani deklaracją zgodności z RODO.

Przebieg: logowanie → klient → prywatny dokument → lokalny odczyt tekstu/OCR → ręczna weryfikacja obok stron dokumentu → zatwierdzona rewizja → kontrolny XLSX. Dodatkowo kartoteki, ręczne polisy z wieloma uczestnikami, terminy, historia i wspólna skrzynka przychodząca. Każdy nowy mail jest osobną pozycją do obsługi; otwarcie wiadomości jej nie zamyka. Zakres wykonanych testów i bieżące ograniczenia opisuje [STATUS](docs/STATUS.md).

Technologia: modularny monolit Django 5.2/DRF/PostgreSQL 17, React/TypeScript strict/Vite/Tailwind, Celery/Redis, pypdf/pypdfium2/Tesseract `pol+eng`, openpyxl. Interfejs i API działają pod jednym originem. Pierwszy profil odczytu dotyczy wyłącznie wniosków brokerskich komunikacyjnych.

## Szybki start: Docker Compose

Wymagania: Git, Python 3 do generatora konfiguracji, działający Docker Engine/Docker Desktop z Compose v2. Polecenia wykonuj z katalogu sklonowanego repozytorium. Obrazy są przypięte do wersji i digestów; pierwsze uruchomienie wymaga Internetu do pobrania zależności.

```sh
python3 scripts/generate_local_config.py
docker compose build
docker compose up -d db redis
docker compose run --rm backend python manage.py migrate
docker compose run --rm backend python manage.py seed_demo --username admin.demo --role ADMIN
docker compose run --rm backend python manage.py seed_demo --username pracownik.demo --role EMPLOYEE
docker compose up -d
```

Hasła podajesz interaktywnie, minimum 12 znaków. Nie ma domyślnego hasła. Seed wymaga `DJANGO_ENV=development`, nie uruchamia się automatycznie i nie zastępuje danych ponownym startem. Jawny reset: to samo polecenie z `--reset-password`. Administrator może tworzyć konta i zmieniać hasła również w administracji kontami.

Otwórz [Broker Office lokalnie](http://127.0.0.1:5173). Korzystaj stale z tego samego hosta, nie przełączaj `localhost` i `127.0.0.1` w trakcie sesji. Compose publikuje tylko port aplikacji na adresie pętli zwrotnej. PostgreSQL, Redis i magazyn plików są dostępne wewnątrz sieci Compose.

Zatrzymanie: `docker compose down`. Ponowne uruchomienie: `docker compose up -d`. Dane pozostają na wolumenach `database`, `private_media`, `queue`. **`docker compose down -v` usuwa te dane.** Diagnostyka: `docker compose ps`, `docker compose logs --tail=80 backend worker mail-worker beat`.

## Windows / PowerShell

Użyj Docker Desktop w trybie kontenerów Linux. Zainstaluj Python 3; pozostałe zależności aplikacji są w kontenerach. W PowerShell wykonaj powyższą sekwencję, zastępując pierwszą komendę:

```powershell
py -3 scripts/generate_local_config.py
```

Pozostałe komendy `docker compose ...` są identyczne i wymagają interaktywnego terminala dla hasła. Nie kopiuj `.env.example` jako gotowej konfiguracji: nie zawiera sekretów. Generator odmawia nadpisania istniejącego `.env`.

Bez Dockera użyj WSL2 (Ubuntu) i instrukcji Linux poniżej. Natywny proces Celery na Windows nie jest wspierany przez autorów projektu; [oficjalna dokumentacja Celery](https://docs.celeryq.dev/en/stable/getting-started/introduction.html) wskazuje to ograniczenie. Nie traktujemy trybu `solo` na Windows jako zweryfikowanego środowiska demonstracji.

## Bez demona Docker: macOS / Linux / Codex

Wymagania: Python 3.12 zarządzany przez `uv`, Node.js 22.23.2 / npm 10.9.8 (wersje odtworzone w CI i obrazach), PostgreSQL 17, Redis 8 i Tesseract z polskim/angielskim. Repozytorium zawiera lockfile Python i npm; do instalacji używaj trybu zamrożonego.

macOS z Homebrew:

```sh
brew install uv node@22 postgresql@17 redis tesseract tesseract-lang
export PATH="$(brew --prefix node@22)/bin:$PATH"
uv python install 3.12
```

Ubuntu/WSL: zainstaluj PostgreSQL 17 z [oficjalnego repozytorium PostgreSQL](https://www.postgresql.org/download/linux/ubuntu/), Redis z [instrukcji Redis](https://redis.io/docs/latest/operate/oss_and_stack/install/archive/install-redis/install-redis-on-linux/) oraz Node 22 i uv zgodnie z instrukcjami ich autorów. OCR i font generatora:

```sh
sudo apt-get update
sudo apt-get install tesseract-ocr tesseract-ocr-pol tesseract-ocr-eng fonts-dejavu-core
```

Następnie na obu systemach:

```sh
uv sync --project backend --frozen
npm ci --prefix frontend
python3 scripts/generate_local_config.py
uv run --project backend python scripts/local_services.py start
uv run --project backend python backend/manage.py migrate
uv run --project backend python backend/manage.py seed_demo --username admin.demo --role ADMIN
tesseract --list-langs
uv run --project backend python scripts/dev.py
```

`local_services.py` nie rejestruje usług systemowych. Tworzy oddzielny klaster w `.local/postgres` oraz Redis w `.local/redis`; oba słuchają na `127.0.0.1` (porty 54329 i 56379). Katalog gniazda lokalnego PostgreSQL ma uprawnienia 0700; połączenia TCP używają SCRAM. Użytkownik developerski ma `CREATEDB` dla testów Django. Nie używaj go do wdrożenia produkcyjnego. Jeśli binaria PostgreSQL nie są w standardowym miejscu, ustaw `BROKER_PG_BIN` na katalog wersji 17.

Skrypt sprawdza PID, katalog danych i pidfile Redis przed użyciem lub zatrzymaniem instancji. Przy konflikcie z innym klonem zgłasza błąd; nie zatrzymuje obcej usługi. Zmienne jawnie ustawione w terminalu mają pierwszeństwo przed `.env` we wszystkich skryptach uruchomieniowych.

`dev.py` uruchamia Django, osobny worker OCR, worker mail/maintenance, Celery beat i Vite. Ciężki OCR ma odrębną kolejkę. Ctrl+C zatrzymuje aplikację; następnie `uv run --project backend python scripts/local_services.py stop` zatrzymuje bazę i kolejkę. Wznowienie tych samych poleceń zachowuje dane. Limity pamięci Compose nie obowiązują automatycznie przy natywnym uruchomieniu; wykonuj odczyt wyłącznie na syntetycznych dokumentach.

## Demonstracja

1. Zaloguj się utworzonym kontem; dodaj klienta lub otwórz Alicję z oznaczeniem DANE TESTOWE.
2. Wgraj `fixtures/remediation/numbered.pdf` przy kliencie. Dokument zapisze się na dysku i w PostgreSQL.
3. Uruchom odczyt i poczekaj na zakończenie zadania. Otwórz weryfikację, przejdź do źródła wybranego pola, zmień wartość i zapisz szkic.
4. W razie braków dodaj uczestnika lub zakres; zapisz, przejrzyj bieżące ostrzeżenia i jawnie je potwierdź. Istotna sprzeczność wymaga notatki. Zatwierdź rewizję; pobierz „Eksport kontrolny — układ demonstracyjny, do uzgodnienia”. Sprawdź arkusze Informacje i Dane.
5. Powtórz z `application_scan.pdf` oraz `application_mixed.pdf`. Odczyt OCR może pozostawić niejednoznaczne kontakty puste; popraw je na podstawie widocznego dokumentu.
6. Wgraj `unsupported_property.pdf`: oczekiwany komunikat „Brak profilu automatycznego odczytu”. Dokument nadal można pobrać.
7. Otwórz polisę testową z kilkoma uczestnikami i listę kończących się polis. Filtry 7/30/60 dni są ustawieniami demonstracyjnymi.

Generator dokumentów: `uv run --project backend python scripts/generate_fixtures.py`. Wzorce oczekiwane są osobno w `fixtures/synthetic/expected.json`; silnik ich nie czyta.


## Demonstracja skrzynki

Po powyższej instalacji/migracji, przy działającej aplikacji:

```sh
uv run --project backend python backend/manage.py seed_mail --all
# Kolejny mail jest świadomą czynnością, także gdy aplikacja pozostaje otwarta:
uv run --project backend python backend/manage.py seed_mail --fixture application
```

W Compose: `docker compose run --rm backend python manage.py seed_mail --all`. Otwórz „Skrzynka”, przejmij wiadomość z wnioskiem, wybierz klienta, zapisz załącznik w jego dokumentach i przejdź istniejący odczyt/weryfikację/XLSX. Następnie świadomie zakończ obsługę. `seed_mail --fixture reply` dodaje nową pozycję todo mimo zakończenia poprzedniego tematu. Drugi pracownik ma własny znacznik przeczytania i widzi właściciela pracy.

To działający import offline przez wspólny parser, bez Internetu. Osobno wykonano rzeczywisty odbiór IMAP/TLS na lokalnym Dovecot przez worker. Dokładny start serwera, injector oraz uruchomienie aplikacji z tym źródłem: [LOCAL_IMAP](docs/LOCAL_IMAP.md). Pełne reguły stanów, limity, konfiguracja, odbudowa UIDVALIDITY i przyszły test Interii: [MAILBOX](docs/MAILBOX.md). Zewnętrzna synchronizacja jest domyślnie wyłączona; nie wpisuj hasła kancelarii do rozmowy ani repo.

## Weryfikacja i dokumentacja

```sh
uv run --project backend pytest backend/tests
uv run --project backend python backend/manage.py makemigrations --check --dry-run
uv run --project backend ruff check backend scripts
npm run check --prefix frontend
npm run lint --prefix frontend
npm test --prefix frontend
npm run build --prefix frontend
```

Playwright wymaga działającej aplikacji i jawnie podanych danych konta testowego: [TESTING](docs/TESTING.md). Procedura kopii bazy i plików: [SECURITY](docs/SECURITY.md). Założenia techniczne i biznesowe: [DECISIONS](docs/DECISIONS.md). [API](docs/API.md), [pełna specyfikacja](docs/MVP_SPEC.md), [backlog](docs/BACKLOG.md), [wersje i licencje](docs/LICENSES.md), [zrzuty działającej aplikacji](docs/SCREENSHOTS.md).

Skrzynka odbiera pocztę tylko do odczytu. Nie ma SMTP/odpowiadania, zewnętrznego AI, automatycznego wystawiania polis ani docelowego arkusza kancelarii. Nie dodawaj `.env`, uploadów, eksportów ani kopii danych do Git.
