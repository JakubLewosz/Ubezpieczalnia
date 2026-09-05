# DANE TESTOWE — syntetyczna poczta

Wszystkie .eml powstają lokalnie przez `python3 scripts/generate_mail_fixtures.py`, mają `X-Broker-Demo: DANE TESTOWE` i kontakty wyłącznie `.invalid`. Nie kopiuj tutaj rzeczywistej korespondencji. Surowe maile użytkownika należą wyłącznie do prywatnego MEDIA_ROOT.

- application: numerowany wniosek komunikacyjny jako rzeczywisty skan PDF; trafia do istniejącego OCR.
- no-client: nadawca bez kartoteki; import nie tworzy klienta.
- candidates: dwie kartoteki syntetyczne tworzone jawnie przez seed, nigdy przez importer.
- newsletter: do ręcznego „Nie wymaga działania” z powodem.
- html-only: polskie akapity, nieaktywny skrypt i zdalny adres `.invalid`, który nie jest pobierany.
- malformed: niepoprawna data, powielony Message-ID i nieznany charset.
- blocked: niewykonywalne atrapy EXE/ZIP odrzucane przez wspólną walidację dokumentów.
- oversized: część 2 KiB, jawnie testowana przez seed z limitem 1 KiB. Standardowy limit pozostaje 20 MiB.
- reply: nowa odpowiedź do application, zawsze nowe todo także po zakończeniu wcześniejszej wiadomości.

Polecenia seed, lokalny IMAP/TLS i zakres walidacji: docs/MAILBOX.md oraz docs/LOCAL_IMAP.md. Ponowne wstrzyknięcie tych samych bajtów z nowym UID oznacza nowe zadanie; ponowne pobranie tego samego UID jest idempotentne.

Git zachowuje .eml jako pliki binarne, aby nie normalizował zakończeń CRLF. To konieczne do porównań pełnych bajtów z serwerem IMAP. Czytelny generator powyżej jest źródłem tych syntetycznych przypadków.
