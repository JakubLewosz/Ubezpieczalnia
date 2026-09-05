# Wersje, zgodność i licencje zależności

Zestawienie przygotowano na podstawie faktycznie zainstalowanych metadanych pakietów, lockfile oraz oficjalnych informacji autorów. Nie nadaje ono licencji kodowi Broker Office. W repozytorium celowo nie dodano własnego pliku LICENSE. Przed dystrybucją lub produkcyjnym użyciem należy sprawdzić obowiązki właściwe dla wybranego modelu dystrybucji i dołączyć wymagane informacje o komponentach.

## Faktycznie zainstalowane komponenty

Python lokalnie: 3.12.13; uv: 0.11.8. PostgreSQL: 17.11, Redis: 8.10.1 i Tesseract: 5.5.3 z `pol` oraz `eng` zostały zainstalowane przez Homebrew. Lokalny Node.js: 24.11.0. Obraz Python przypina 3.12.13, Node 22.23.2, PostgreSQL 17.11, Redis 8.2.9. Pełne digesty są w Dockerfile/Compose; ich dostępność została zweryfikowana w oficjalnym rejestrze, a samo uruchomienie obrazów wymaga działającego demona Docker.

| Komponent | Zainstalowana wersja | Licencja z metadanych/autora |
| --- | --- | --- |
| Django | 5.2.17 | BSD-3-Clause |
| Django REST Framework | 3.18.0 | BSD-3-Clause |
| psycopg, psycopg-binary | 3.3.5 | LGPL-3.0-only; uwzględnić binarne zależności koła |
| Celery | 5.6.3 | BSD-3-Clause |
| redis-py | 6.4.0 | MIT |
| pypdf | 6.17.0 | BSD-3-Clause |
| pypdfium2 | 5.13.0 | BSD-3-Clause / Apache-2.0 oraz licencje zależności PDFium |
| Pillow | 12.3.0 | MIT-CMU |
| openpyxl | 3.1.5 | MIT |
| ReportLab | 4.5.1 | BSD |
| Gunicorn | 25.3.0 | MIT |
| python-dotenv | 1.2.3 | BSD-3-Clause |
| pytest / pytest-django | 9.1.1 / 4.14.0 | MIT / BSD |
| Ruff | 0.16.6 | MIT |
| React / React DOM | 19.2.8 | MIT |
| React Router DOM | 7.18.3 | MIT |
| TypeScript | 6.0.3 | Apache-2.0 |
| Vite | 8.2.2 | MIT |
| Tailwind CSS | 4.3.3 | MIT |
| Vitest | 5.0.0 | MIT |
| Playwright Test | 1.63.0 | Apache-2.0 |
| Lucide React | 1.41.0 | ISC |
| ESLint / typescript-eslint | 10.10.0 / 8.69.0 | MIT |
| Prettier | 3.9.6 | MIT |

Pełniejszy odczyt Python z zależnościami przechodnimi: `docs/licenses-python.json`, wygenerowany poleceniem `uv run --project backend pip-licenses --format=json --with-urls`. Bezpośrednie zależności frontendowe z faktycznych `node_modules`: `docs/licenses-frontend.json`. Lockfile zawierają także integralność artefaktów. Inwentarz nie jest sam w sobie audytem podatności ani pełną analizą prawną wszystkich elementów systemowych.

## Ważne warunki

- **Redis 8** pozwala wybrać AGPLv3, RSALv2 albo SSPLv1. Dla dokumentacji demonstracji wskazujemy dostępną ścieżkę AGPLv3; przed dostarczaniem obrazu należy ocenić obowiązki źródeł/licencji dla tego sposobu dystrybucji. Redis 7.4 także nie jest BSD; BSD dotyczy 7.2 i starszych. [Licencje Redis](https://redis.io/legal/licenses/).
- **PostgreSQL** używa PostgreSQL License. [Oficjalna licencja](https://www.postgresql.org/about/licence/). Wsparcie gałęzi 17 trwa według harmonogramu do listopada 2029; [polityka wersjonowania](https://www.postgresql.org/support/versioning/).
- **Tesseract** i standardowe dane językowe projektu używają Apache-2.0. Nie wysyłają dokumentów poza komputer. [Dokumentacja projektu](https://tesseract-ocr.github.io/tessdoc/).
- **pypdfium2** wymaga uwzględnienia PDFium i zależności binarnych: sam opis „BSD wrappera” jest niewystarczający. Koło zawiera informacje licencyjne bibliotek. [Rozdział licencyjny autora](https://pypdfium2.readthedocs.io/en/stable/readme.html#licensing).
- **psycopg-binary** jest wygodną instalacją dla demonstracji. Przy dystrybucji trzeba uwzględnić LGPL oraz wbudowane biblioteki klienckie. [Instalacja i warianty psycopg](https://www.psycopg.org/psycopg3/docs/basic/install.html).
- **DejaVu Sans** w `fixtures/fonts/DejaVuSans.ttf` służy generatorowi syntetycznych PDF i zawiera pełny używany polski alfabet. Font pochodzi z lokalnego runtime Popplera; obowiązujące informacje zachowano w `fixtures/fonts/LICENSE-DejaVu.txt` z oficjalnego repozytorium DejaVu. Font ma licencję Bitstream Vera z modyfikacjami DejaVu w domenie publicznej i warunkami elementów Arev. [Licencja projektu](https://dejavu-fonts.github.io/License.html). Jest to licencja zewnętrznego fontu, nie aplikacji.

## Zgodność potwierdzana dokumentacją i instalacją

Django 5.2 obsługuje Python 3.12, a PostgreSQL 17 mieści się w wymaganiach backendu. [Django FAQ](https://docs.djangoproject.com/en/5.2/faq/install/), [backend PostgreSQL](https://docs.djangoproject.com/en/5.2/ref/databases/#postgresql-notes). Node 22.23.2 jest powyżej wymaganej przez Vite granicy 22.12; [instrukcja Vite](https://vite.dev/guide/). Python 3.12 oraz Redis są obsługiwane przez Celery, ale Windows natywnie nie jest wspierany; [wprowadzenie Celery](https://docs.celeryq.dev/en/stable/getting-started/introduction.html).

Dowodem instalowalności są istniejące zamrożone środowiska i wykonane testy opisane w STATUS. Różnica Redis lokalnie/Compose oraz brak testu uruchomienia kontenerów nie są przemilczane. Aktualizacja któregokolwiek lockfile lub obrazu wymaga ponowienia istotnych testów i odświeżenia tego zestawienia.

TypeScript przypięto do stabilnego 6.0.3, ponieważ aktualny typescript-eslint 8.69.0 deklaruje zgodność `>=4.8.4 <6.1.0`. Początkowo instalowalne 7.0.2 nie pasowało do tego zakresu; wybrano zgodny komplet z działającym lintem, bez obchodzenia zależności peer.

## Zmiany naprawy i poczty

Naprawa lockfile npm dodaje brakujące wpisy transytywne @emnapi/core i @emnapi/runtime 1.11.1 (MIT) bez aktualizacji dotychczasowych wersji. Python nie otrzymał nowych zależności: IMAP/MIME używają stdlib, dziennik istniejącego psycopg. Lokalny test używa Dovecot CE 2.4.5; licencje i wyjątki obrazu opisano wraz z oficjalnymi źródłami w LOCAL_IMAP.md. Dovecot nie jest wymagany do późniejszego odbioru od dostawcy.
