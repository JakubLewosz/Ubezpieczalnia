# Bezpieczeństwo demonstracji

To środowisko lokalne do wyłącznie syntetycznych danych DANE TESTOWE. Nie jest przeznaczone do publicznego Internetu ani prawdziwych dokumentów kancelarii.

## Obecne zabezpieczenia i granice

- Sesje Django, CSRF także przy logowaniu, unieważnianie sesji przez logout, ograniczanie kolejnych nieudanych logowań. ADMIN zarządza kontami, EMPLOYEE nie ma takiego uprawnienia. Brak publicznej rejestracji.
- HTTP jest jawnym wyjątkiem `DJANGO_ENV=development`. Bez niego konfiguracja wymusza przekierowanie HTTPS, bezpieczne ciasteczka i HSTS. Nie stanowi to gotowej konfiguracji produkcyjnego reverse proxy.
- Oryginały i PNG stron są pobierane wyłącznie przez uwierzytelnione API, bez publicznej trasy `/media/`. Nazwa pliku w magazynie jest losowym kluczem, a oryginalna nazwa nie służy do budowania ścieżki. Odpowiedzi używają bezpiecznego typu, `nosniff` i prywatnego cache.
- PDF/JPEG/PNG podlegają odczytowi. DOCX/XLSX są jedynie załącznikami; skrypty i makra nie są wykonywane. Walidacja porównuje rozszerzenie i zawartość, limit rozmiaru (domyślnie 20 MB), stron (30), pikseli i rozpakowanego Office. Zaszyfrowane/uszkodzone PDF są odrzucane.
- pypdfium2 i Tesseract pracują lokalnie. Treść dokumentu nie jest poleceniem i nie jest wysyłana do zewnętrznego AI/OCR. Subprocess otrzymuje tablicę argumentów bez interpretacji przez powłokę; logi zadania nie zawierają surowego tekstu.
- Domyślnie jedno zadanie OCR, limit czasu strony i zadania, lease odzyskiwany przez Celery beat. Compose ogranicza RAM, CPU i liczbę procesów workera. Brak skanera antywirusowego i dedykowanej piaskownicy parsera pozostaje ograniczeniem.
- Wyniki silnika, zatwierdzenia i audyt nie mają zwykłego API edycji. Szkic, klient i polisa wymagają wersji edycji. Transakcje i blokady wierszy zapobiegają cichemu nadpisaniu równoczesnej zmiany.
- Eksport pochodzi z niezmiennej zatwierdzonej rewizji, a tekst jest jawnie tekstem XLSX także przy prefiksach `=`, `+`, `-`, `@` i białych znakach. Nie wykonuje formuł z dokumentu.
- `.env` jest generowany z losowymi sekretami i uprawnieniami 0600 na systemach POSIX. Generator nie nadpisuje pliku. Windows wymaga dodatkowo właściwych uprawnień profilu użytkownika/ACL. Nie ma hasła zaszytego w obrazie ani automatycznego seeda.

Pracownicy widzą wszystkie kartoteki jako robocze założenie MVP. Nie ma MFA, antywirusa, szyfrowania aplikacyjnego plików, automatycznych aktualizacji, alertów operacyjnych ani potwierdzonego poziomu odporności na ataki. PostgreSQL i Redis w Compose nie mają publikowanych portów. W trybie natywnym używają wyłącznie `127.0.0.1`; jest to zaufane stanowisko developerskie, nie serwer wieloużytkownikowy.

## Spójna kopia bazy i magazynu

Repozytorium **nie jest kopią danych**. Odtworzenie wymaga PostgreSQL oraz odpowiadających mu oryginałów i podglądów z tego samego momentu. Kopie zawierają też konta/sesje, dlatego są materiałem prywatnym nawet w demonstracji. W prawdziwym pilotażu trzeba uzgodnić szyfrowanie, nośnik, retencję, odpowiedzialność i RPO/RTO.

Procedura dla lokalnych danych testowych:

1. Zakończ procesy Django, frontend, worker i beat przez Ctrl+C w `scripts/dev.py`. W Compose wykonaj `docker compose stop frontend backend worker mail-worker beat`. PostgreSQL pozostaje uruchomiony. Nie wykonuj kopii przy aktywnych zapisach plików/OCR.
2. Utwórz nowy katalog `.local/backups/<czas>` z prawami 0700. Nigdy nie dodawaj go do Git.
3. Wykonaj `pg_dump --format=custom --no-owner --no-privileges` właściwej bazy, podając konfigurację przez lokalne zmienne środowiskowe. Nie wpisuj hasła do polecenia ani historii powłoki. W Compose uruchom ten sam program przez `docker compose exec -T db`; wartości `POSTGRES_USER`/`POSTGRES_DB` pochodzą z kontenera.
4. Skopiuj cały `MEDIA_ROOT` do tej samej kopii (oryginały, `previews`, prywatne źródła maili i załączniki). W Compose spakuj wolumen `private_media` przy pomocy `docker compose run --rm --no-deps --entrypoint tar backend -czf - -C /app/.local/media .`.
5. Zapisz metadane: czas UTC, wersję PostgreSQL, commit aplikacji, listę plików oraz SHA-256 dumpa i archiwum. Sekret aplikacji przechowuj oddzielnie; nie dopisuj go do manifestu.
6. Wznowienie: `uv run --project backend python scripts/dev.py` albo `docker compose start backend worker mail-worker beat frontend`.

Do przekierowania dumpa i archiwum w PowerShell używaj plików binarnych przez Python `subprocess.run(..., stdout=otwarty_plik_wb)` lub PowerShell 7.4+. Starszy PowerShell może zmieniać binarne dane przy `>`; nie używaj tak powstałej kopii bez weryfikacji.

Przykładowa kopia Compose po zatrzymaniu aplikacji (Python 3, polecenia uruchamiane z repo; folder musi być nowy):

```python
from pathlib import Path
import hashlib
import json
import subprocess
from datetime import datetime, timezone

target = Path('.local/backups') / datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
target.mkdir(parents=True, mode=0o700, exist_ok=False)
commands = {
    'database.dump': ['docker', 'compose', 'exec', '-T', 'db', 'sh', '-c',
        'exec pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc --no-owner --no-privileges'],
    'media.tar.gz': ['docker', 'compose', 'run', '--rm', '--no-deps', '--entrypoint', 'tar',
        'backend', '-czf', '-', '-C', '/app/.local/media', '.'],
}
checksums = {}
for name, command in commands.items():
    with (target / name).open('wb') as output:
        subprocess.run(command, stdout=output, check=True)
    checksums[name] = hashlib.sha256((target / name).read_bytes()).hexdigest()
(target / 'manifest.json').write_text(json.dumps(checksums, indent=2), encoding='utf-8')
```

## Próba odtworzenia na danych testowych

Dla natywnych usług z README dostępny jest wykonywalny test: po zakończeniu demonstracji z zatwierdzoną rewizją zatrzymaj `dev.py` (Django, Vite, worker i beat), pozostaw PostgreSQL uruchomiony i wykonaj:

```sh
uv run --project backend python scripts/verify_backup_restore.py
```

Polecenie wymaga `DJANGO_ENV=development` i nieaktywnych portów aplikacji 8000/5173. Kopiuje bazę oraz cały magazyn do nowego `.local/backups/<czas>-<losowy_id>`, odtwarza je do własnej nowej bazy testowej, porównuje liczniki wszystkich tabel, SHA-256 oryginałów i podglądów oraz snapshoty zatwierdzonych pól. W odtworzonej bazie sprawdza odmowę anonimowego dostępu oraz uwierzytelnione pobranie oryginału, PNG i historycznego XLSX z porównaniem jego pól. Usuwa wyłącznie utworzoną przez siebie bazę odtworzeniową; kopia i manifest pozostają w ignorowanym folderze. Źródłowa baza i magazyn są tylko odczytywane. To test demonstracji, nie narzędzie produkcyjnego backupu. Zatrzymanie workera i beat pozostaje obowiązkiem uruchamiającego; blokada portów nie dowodzi zatrzymania tych procesów.

1. Użyj oddzielnego klona, nowej konfiguracji i pustej bazy/wolumenu; nie nadpisuj jedynej działającej kopii demonstracji. Zweryfikuj SHA-256 obu plików zgodnie z manifestem.
2. Uruchom tylko PostgreSQL i Redis. Odtwórz dump przez `pg_restore --no-owner --no-privileges --exit-on-error -d <pusta_baza> database.dump`. Użyj tej samej wersji PostgreSQL 17 albo zgodnej nowszej wersji narzędzi do zaplanowanej migracji.
3. Rozpakuj własne zweryfikowane archiwum do pustego `MEDIA_ROOT`; zachowaj uprawnienia 0600/0700 i właściciela procesu aplikacji (UID/GID 10001 w obrazie). Nie rozpakowuj niezaufanych archiwów do magazynu.
4. Uruchom migracje aplikacji zgodnej z kopią. Przed uruchomieniem workerów i beat jawnie wstrzymaj zewnętrzną pocztę w odtworzonej bazie i ustaw MAIL_SYNC_ENABLED=false. Zachowaj cursor/UIDVALIDITY oraz pracę i odczyty; usuń wyłącznie dzierżawę i zlecenie integracji. Wygasłe lease OCR pozwolą odzyskać przerwane zadania. Kolejka Redis nie jest źródłem zatwierdzonych danych i może zostać odtworzona przez mechanizm odzyskiwania zadań.
5. Unieważnij odzyskane sesje przed udostępnieniem odtworzonej demonstracji (jawna operacja Django: `Session.objects.all().delete()` na odtworzonej bazie). Utwórz lub jawnie zresetuj hasło konta developerskiego.
6. Porównaj liczbę klientów, polis, dokumentów i rewizji z kopią; pobierz oryginał i sprawdź SHA-256, otwórz PNG oraz eksport historycznej rewizji. Sprawdź też restart usług i brak anonimowego dostępu.

Wynik próby, czas i ewentualne luki zapisz w STATUS. Sama obecność tej procedury nie oznacza wykonanego testu odtworzenia.

## Uzgodnienia przed rzeczywistymi danymi

- Podstawy i zakres przetwarzania, obowiązki informacyjne, retencja i usuwanie, dokumentacja administratora danych i umowy powierzenia.
- Faktyczne role, minimalny dostęp, indywidualne konta, MFA i bezpieczny proces resetu/odebrania dostępu.
- HTTPS, zarządzanie sekretami, aktualizacje, szyfrowanie dysków/kopii i ograniczenie dostępu operatora do bazy/magazynu.
- Audyt bezpieczeństwa, skanowanie uploadów, izolacja parserów, test przeciążenia i przegląd licencji.
- Właściciel procedury backup/restore, monitoring, alerty, odtwarzanie po awarii i okresowe ćwiczenia.
- Uzgodniony profil eksportu i ręczna odpowiedzialność za zatwierdzane wartości. OCR nie zastępuje weryfikacji dokumentu.

## Poczta i naprawa audytu

Integracja domyślnie wyłączona. Sekret jest wyłącznie po stronie serwera, poza bazą, API i VITE_. Interfejs administratora nie przyjmuje dowolnego hosta. TLS sprawdza certyfikat i nazwę serwera, lokalne testy używają własnego jawnego CA bez globalnego obejścia. Klient protokołu wyłącza pierścień diagnostyczny imaplib, który mógłby zachować LOGIN/treść. Błędy synchronizacji mają stałe komunikaty, nie serializują wyjątków zawierających niezaufane dane.

EXAMINE i BODY.PEEK nie zmieniają flag; APPEND istnieje wyłącznie w jawnym lokalnym injectorze syntetycznych fixture. Nie ma SMTP. MIME jest ograniczone rozmiarem przed odczytem literału, rzeczywistymi bajtami, liczbą/głębokością części i limitami danych zdekodowanych. HTML ma wyłącznie tekstowy widok. Pliki mają losowe klucze, auth/attachment/no-store; blokowane typy nie mają aktywnego podglądu. Nie ma antywirusa, a poprawny format nie jest oceną bezpieczeństwa.

Hasła i klucz sesji CI są maskowane PRZED zapisem do GITHUB_ENV. Artefakt błędu ma wyłącznie dozwolone nazwy testów/liczniki i statusy; nie publikuje śladów uwierzytelnionej sesji, prywatnych plików, tracebacków z treścią ani logów. Historyczne ustalenie dotyczyło jednorazowych wartości CI, nie potwierdzonego wycieku hasła kancelarii.

Eksport waliduje XML1.0 i limit 32767 znaków także w nazwach/metadanych. Historycznej rewizji nie czyścimy ani nie obcinamy w miejscu: niepoprawna wartość powoduje kontrolowane 400 z instrukcją nowej korekty. Formatowanie komórek nie wykonuje tekstu formułopodobnego.

Rozszerzony test backup/restore porównuje pełne snapshoty tabel correspondence (w manifeście tylko hash), sumy plików, osobiste odczyty, statusy i cursor. Wstrzymuje importer WYŁĄCZNIE w odtworzonej bazie przed uruchomieniem aplikacji; źródła nie modyfikuje. Po odtworzeniu ADMIN kontroluje tożsamość folderu i dopiero świadomie wznawia integrację, aby nie uruchomić drugiego importera. Szczegóły: MAILBOX i LOCAL_IMAP.

Zapis poczty i promocja załącznika rezerwują klucz w trwałym dzienniku plików przed zapisem bajtów (osobne krótkie połączenie do tej samej bieżącej bazy). Żywy writer trzyma blokadę advisory. Po awarii maintenance sprząta tylko niepowiązane własne klucze z wygasłym 15-minutowym okresem ochronnym; nie skanuje ani nie usuwa arbitralnie pozostałego magazynu. Test rzeczywistego SIGKILL przed commitem i testy aktywnej blokady/referencji są w test_mail_storage.py.
