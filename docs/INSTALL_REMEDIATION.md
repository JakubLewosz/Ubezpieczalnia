# A01 i A09 — instalacja, Compose i diagnostyka CI

Weryfikacja rozpoczęta 2026-09-05 na macOS arm64. Wcześniejsza demonstracja natywna (PostgreSQL, Redis i pliki) pozostała bez zmian. Nowa próba Compose korzysta z losowej nazwy projektu, oddzielnego pliku konfiguracji, trzech nowych wolumenów i portu 5174.

## Dowód A01 i naprawa lockfile

Zdalny [workflow dla b946008](https://github.com/JakubLewosz/Ubezpieczalnia/actions/runs/33962492054) ma wynik **failure**. Krok instalacji zakończył się `EUSAGE`, a kroki backendu, frontendu i Playwright miały wynik **skipped**. Stan i konkretne linie błędu odczytano przez API GitHub; nie pobrano ani nie zapisano pełnych dawnych logów z jednorazowymi sekretami.

Błąd odtworzono na aktualnym bazowym lockfile w pustych katalogach, bez `node_modules`, w dwóch środowiskach:

- macOS arm64: oficjalny Node **22.23.2**, npm **10.9.8**; suma SHA-256 archiwum Node sprawdzona względem pliku producenta;
- Linux arm64: przypięty obraz `node:22.23.2-bookworm-slim`, identyczny z Dockerfile, Node **22.23.2**, npm **10.9.8**.

Obie próby `npm ci` wskazały brak `@emnapi/core`, `@emnapi/runtime`, `@emnapi/wasi-threads` i `tslib`. Lockfile nie opisywał kompletnie zależności dołączonych do opcjonalnego pakietu `@tailwindcss/oxide-wasm32-wasi`. Dodatkowa czysta próba starego lockfile z lokalnym Node 24.11.0/npm 11.6.1 także zawiodła (`wasi-threads` i `tslib`); problem nie ograniczał się do jednej wersji npm. Działający wcześniej katalog `node_modules` nie stanowił dowodu kompletności lockfile. Nie przypisujemy konkretnej historycznej komendzie powstania braku bez jej zapisu.

W odrębnym, pustym katalogu z `package.json` i dotychczasowym lockfile wykonano npm **10.9.8** `npm install --package-lock-only`. Nie użyto `--force`, `--legacy-peer-deps`, pomijania instalacji opcjonalnych ani aktualizacji zależności głównych. Wszystkie istniejące wpisy zachowały swoje wersje. npm dopisał dwa brakujące wpisy pakietów dołączonych do dystrybucji (`@emnapi/core` i `@emnapi/runtime` **1.11.1**, MIT), których zależności wskazują już zapisane dołączone `wasi-threads` i `tslib`. Uporządkował również znaczniki `peer`. To poprawa opisu istniejącego drzewa, nie migracja frameworków.

Po naprawie czyste `npm ci` zakończyło się sukcesem w obu środowiskach oraz w dodatkowym kontenerze **Linux amd64** (architektura runnera GitHub), Node 22.23.2/npm 10.9.8. W kopii frontendu uruchomionej Node 22.23.2 przeszły TypeScript, ESLint, **13 testów komponentowych** i build. Był to stan kodu w trakcie etapu A; końcowe wyniki całego etapu prowadzi `REMEDIATION_STATUS.md`. Świeże środowisko Pythona zostało utworzone przez `UV_PROJECT_ENVIRONMENT=<odrębny katalog> uv sync --project backend --frozen`: Python **3.12.13**, 41 pakietów, bez zmiany `uv.lock`.

`packageManager` wskazuje npm 10.9.8, CI sprawdza tę wersję, a Node w CI i Dockerfile pozostaje przypięty. Naprawy lockfile należy generować w pustym katalogu, a następnie sprawdzać `npm ci` na środowisku CI; samo udane `npm install` nie jest odbiorem.

## Powtarzalna próba Compose

Docker Desktop został uruchomiony przez `docker desktop start`; Docker Engine **29.4.1**, Compose **5.1.3**. Zastane wolumeny innych projektów nie były usuwane.

Z katalogu projektu:

```sh
python3 scripts/verify_compose.py --port 5174
```

Skrypt generuje prywatną konfigurację, wykonuje rzeczywiste `docker compose build`, uruchamia PostgreSQL/Redis, stosuje migracje, sprawdza ich kompletność i wymagane języki OCR, tworzy jawne konto syntetyczne oraz uruchamia API, worker, beat i frontend. Sprawdza dostęp do CSRF przez frontend i odpowiedź rzeczywistego workera na ping. **Ping workera nie dowodzi odczytu dokumentu** — dalszy przebieg z dokumentem/Playwright jest osobnym testem.

Każdy przebieg ma metadane w `.local/compose-checks/broker-check-<losowy-identyfikator>/result.json`. `completed: true` oznacza wyłącznie przejście wymienionych kontroli uruchomienia. Hasło znajduje się w sąsiednim `credentials.json` (0600), nigdy w logu lub Git. Plik `.env` też ma 0600. Skrypt nie nadpisuje istniejącej demonstracji, nie usuwa wolumenów i przy konflikcie portu odmawia działania.

Do ręcznych kolejnych poleceń używaj wartości z `result.json`:

```sh
export BROKER_ENV_FILE="<pełna ścieżka do pliku environment_file>"
export BROKER_HTTP_PORT=5174
docker compose --project-name "<project>" --env-file "$BROKER_ENV_FILE" ps
docker compose --project-name "<project>" --env-file "$BROKER_ENV_FILE" down
```

`down` zatrzymuje wyłącznie wskazany projekt i zachowuje jego dane. Nie dodawaj `-v`, jeśli chcesz zachować dowód próby. `BROKER_ENV_FILE` i `BROKER_HTTP_PORT` umożliwiają odrębne konfiguracje; zwykły start bez tych zmiennych nadal używa `.env` i portu 5173.

Rzeczywisty build/start zakończył się sukcesem 2026-09-05 na projekcie `broker-check-841895b14b`: wszystkie sześć kontenerów uruchomione, trzy odrębne wolumeny, migracje zastosowane, `makemigrations --check --dry-run` bez zmian, `pol+eng` dostępne, API dostępne przez port 5174 i rzeczywisty worker odpowiada na ping. W backendzie kontenera: Python **3.12.13**, Django **5.2.17**, Tesseract **5.3.0**. Baza **PostgreSQL 17.11**, Redis **8.2.9** zgodnie z przypiętymi obrazami. Nie jest to dowód uruchomienia Windows ani GitHub Actions.

Po uruchomieniu przez prawdziwe HTTP API zalogowano konto syntetyczne z sesją/CSRF, wgrano `fixtures/synthetic/application_scan.pdf` do kartoteki i zlecono odczyt. Rzeczywisty worker kontenera pobrał zadanie z Redis i zakończył je sukcesem po około **2,09 s**: jedna strona metodą `ocr`, 31 pól rozpoznanego profilu. To ograniczona próba uruchomienia OCR w obrazie; zatwierdzenie, grupy i zawartość XLSX sprawdza pełny odbiór dokumentowy etapu A.

Po zamknięciu implementacji A obrazy przebudowano i uruchomiono ponownie z zachowaniem danych. **Pełne 5 testów Playwright na Compose przeszło w 26,3 s**: wcześniejszy proces dokumentowy, ochrona niezapisanej kartoteki, numerowany wniosek z dopisaniem uczestnika i zakresu/ról oraz sprawdzeniem rzeczywistego XLSX, dwa konta/opóźniony PATCH/konflikt, selektory z dalszych stron i archiwum. Pierwsze uruchomienie przeglądarki nastąpiło przed zakończeniem odtwarzania kontenerów i zwróciło `ERR_CONNECTION_REFUSED`; po zakończeniu `up --wait` wykonano pełny przebieg ponownie. CI uzupełniono o jawne drugie konto z osobnym, zamaskowanym hasłem.

Pierwsza próba `broker-check-fa087d6c67` zbudowała obrazy i zastosowała bazowe migracje, ale prawidłowo zawiodła w `makemigrations --check`: obraz uchwycił prace nad nowymi modelami ekstrakcji przed zapisaniem ich migracji. Po ukończeniu migracji wykonano powyższą nową próbę od początku. Kontenery pierwszej próby zatrzymano, pozostawiając jej wolumeny; nie pomijano kontroli, nie kasowano żadnej bazy w celu uzyskania sukcesu.

## Obowiązkowy OCR i A09

`scripts/check_ocr.py` zawodzi przy braku Tesseract albo języka `pol`/`eng`. Jest wywoływany przy budowaniu obrazu i w obowiązkowym CI. Sprawdzono trzy ścieżki: dostępne oba języki — sukces; brak programu — exit 1; program zgłaszający tylko `eng` — exit 1. CI ustawia również `OCR_REQUIRED=1`, aby test OCR nie mógł udawać sukcesu po pominięciu.

Wartości generowanych sekretów CI są rejestrowane przez `::add-mask::` **przed** wpisaniem do `GITHUB_ENV` i przed użyciem w kolejnych krokach, zgodnie z [dokumentacją GitHub](https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-commands#masking-a-value-in-a-log). Generator konfiguracji i skrypt Compose również rejestrują swoje jednorazowe sekrety, gdy `GITHUB_ACTIONS=true`, przed zapisaniem prywatnych plików. Sprawdzono kolejność i uprawnienia 0600 generatora. Dotyczy to jednorazowych wartości runnera; nie jest stwierdzeniem wycieku haseł kancelarii.

Przy niepowodzeniu CI publikuje tylko `test-summary.json` z licznikami i identyfikatorami nieudanych testów. `collect_ci_diagnostics.py` korzysta z zamkniętej listy pól: nie kopiuje komunikatów wyjątków, logów, zawartości żądań, załączników, `.env`, sesji ani archiwów Playwright trace. Sprawdzono próbą z kontrolnym sekretem w błędzie i ścieżką sesji, że nie trafiają do wynikowego JSON. Pełne ślady przeglądarki mogą zawierać ciasteczka i pozostają wyłącznie lokalną diagnostyką poza Git, bez uploadu jako artefakt.

Zmodyfikowany workflow wymaga jeszcze wykonania na GitHub po publikacji nowego commita. Lokalny sukces nie jest zielonym GitHub Actions.
