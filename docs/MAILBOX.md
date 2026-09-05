# Wspólna skrzynka przychodząca

Jedna odebrana wiadomość jest jedną pozycją do obsługi. Przeczytanie przez pracownika jest osobnym rekordem i nie oznacza załatwienia. Odpowiedzi obsługuje się w dotychczasowym programie pocztowym; Broker Office nie wysyła maili i nie potwierdza wysłania odpowiedzi. Wszystkie opisane demonstracje używają wyłącznie danych syntetycznych.

## Praca zespołu

| Operacja | Kto | Skutek i właściciel |
|---|---|---|
| Import | Worker IMAP / jawna komenda demo | Nowe `todo`, bez właściciela i klienta; także mail wcześniej przeczytany u dostawcy |
| Otwarcie | Aktywny pracownik | Jeden osobisty ReadReceipt; bez zmiany stanu pracy, wersji ani flag IMAP |
| Zajmij się | Aktywny pracownik | Atomowo z nieprzydzielonego `todo` do `in_progress`, właściciel = bieżący pracownik, czas przejęcia |
| Notatka/powiązania | Właściciel lub ADMIN | Wersjonowana zmiana; przypisanie klienta lub dokumentu nie kończy obsługi |
| Oczekujemy | Właściciel lub ADMIN | `waiting`, właściciel pozostaje, wymagana notatka minimum 3 znaki |
| Obsłużona | Właściciel lub ADMIN | `done`, zachowany właściciel, osobno wykonawca i czas zakończenia |
| Nie wymaga działania | Właściciel lub ADMIN | `no_action`, wymagany powód minimum 3 znaki, wykonawca i czas |
| Zwolnij | Właściciel lub ADMIN | Z aktywnego stanu do `todo`, bez właściciela; notatka i historia pozostają |
| Przekaż | ADMIN | Tylko do aktywnego konta; `todo` staje się `in_progress`, `waiting` pozostaje oczekiwaniem |
| Otwórz ponownie | Właściciel lub ADMIN | Tylko zakończona pozycja → `in_progress`; zachowany aktywny właściciel, inaczej bieżący ADMIN. Wcześniejsze zakończenie pozostaje w audycie |

Przed zamknięciem wiadomość musi należeć do aktywnego pracownika. Po odebraniu dostępu właścicielowi jego nazwisko i informacja o nieaktywności pozostają widoczne; administrator może przekazać zadanie. Terminalny stan zmienia tylko jawne ponowne otwarcie. Zwykły zapis notatki nie otwiera zakończonej wiadomości.

Istotne operacje blokują aktualny wiersz w PostgreSQL, sprawdzają wersję i uprawnienia po blokadzie. Równoczesne przejęcie: jeden sukces, drugi HTTP 409. Powtórny zapis starej wersji nie nadpisuje notatki. UI blokuje pola podczas żądania, chroni niezapisane zmiany i nie zastępuje szkicu odpowiedzią pollingu. Lista domyślnie pokazuje najstarsze niezałatwione, po 20 rekordów; liczniki dotyczą całego filtrowanego zbioru.

## Tożsamość i dokumenty

Unikalność importu: `(mailbox, folder, UIDVALIDITY, UID)`. `Message-ID`, temat oraz nagłówki odpowiedzi są wyłącznie kontekstem. Dwa identyczne Message-ID, brak tego nagłówka lub odpowiedź do `done` nadal tworzą nowe `todo`. Oddzielnie zapisujemy INTERNALDATE dostawcy, zadeklarowany Date (NULL przy niepewnej wartości) i czas lokalnego importu. Surowe nagłówki pozostają w niezmiennym `.eml`; ich dekodowany widok nie jest autoryzacją nadawcy.

Adres nadawcy podpowiada najwyżej 20 kartotek i podaje pełny licznik trafień. Nie tworzy ani nie przypisuje klienta. Pełna wyszukiwarka klienta ma kolejne strony. Polisa musi obejmować wybranego klienta i być aktywna.

Załącznik istnieje niezależnie od Document. „Zapisz w dokumentach klienta” wymaga jawnego wyboru klienta/polisy, kontroli bieżącej wersji oraz tej samej walidacji co upload. Blokada wiadomości i części MIME oraz unikalna relacja do dokumentu chronią przed podwójnym zapisem. Powtórzenie zwraca istniejący dokument. Zmiana klienta przy wiadomości nie przenosi wcześniejszych dokumentów. Dokument ma link do wiadomości i części MIME; przechodzi zwykły OCR → korekta → zatwierdzona rewizja → kontrolny XLSX. Sam import poczty nie zleca OCR.

## Konfiguracja serwera i zatrzymanie

Brak konfiguracji nie blokuje klientów, dokumentów ani demonstracji offline. Domyślnie `MAIL_SYNC_ENABLED=false`. Dodatkowo zapisane `Mailbox.enabled` wymaga jawnego rozpoczęcia przez ADMIN. Hasło jest odczytywane wyłącznie na serwerze; preferowany `MAIL_PASSWORD_FILE`. Nie ma pól połączenia w formularzu pracownika, hasła w bazie/API, prefiksów VITE_ ani przechowywania sekretu w przeglądarce.

| Ustawienie | Domyślnie / znaczenie |
|---|---|
| `MAIL_SYNC_ENABLED` | `false`; możliwość uruchomienia integracji przez ADMIN |
| `MAIL_HOST`, `MAIL_PORT` | `poczta.interia.pl`, `993`; zweryfikowany SSL/TLS |
| `MAIL_USERNAME` | pełny adres, bez wartości domyślnej |
| `MAIL_PASSWORD_FILE` / `MAIL_PASSWORD` | prywatny plik sekretu ma pierwszeństwo; bez wartości domyślnej |
| `MAIL_FOLDER` | `INBOX`; w tym MVP nazwy ASCII |
| `MAIL_CA_FILE` | opcjonalny dodatkowy zaufany CA; lokalny test ma własny certyfikat. Nigdy `CERT_NONE` |
| `MAIL_POLL_SECONDS` | 60, dozwolone 15–3600 |
| `MAIL_TIMEOUT_SECONDS` | 20, dozwolone 1–60 |
| `MAIL_BATCH_SIZE` / `MAIL_UID_WINDOW` | 25 wiadomości / 5000 UID na przebieg |
| `MAIL_RETRY_LIMIT` | 3, dozwolone 1–5 |

„Test połączenia” otwiera folder tylko do odczytu, nie pobiera treści, nie rozpoczyna importu i nie zmienia kursora. „Odśwież listę” odczytuje API. „Synchronizuj teraz” zleca ograniczone zadanie serwerowe; rezerwacja i 30-sekundowe ograniczenie ręcznych zleceń zapobiegają równoległym przebiegom. „Wstrzymaj” natychmiast unieważnia token dzierżawy. Aby wyłączyć także możliwość wznowienia, ustaw `MAIL_SYNC_ENABLED=false` w konfiguracji serwera i uruchom ponownie procesy aplikacji.

Zmiana hosta/portu/loginu/folderu wybiera nową konfigurację z osobnym kursem i wstrzymuje poprzednią. Zmiana samego hasła nie resetuje tożsamości. Konto demo ma odrębne źródło `offline-demo` i nie wykonuje połączeń sieciowych.

## Granica importu, awarie i UIDVALIDITY

Pierwszy udany EXAMINE daje UIDVALIDITY i UIDNEXT. Jednorazowo zapisujemy `boundary_uid = UIDNEXT - 1`, czyli **wyłączenie wcześniejszej historii**, a nie oznaczenie jej jako obsłużonej. Wiadomość przychodząca po tej odpowiedzi ma wyższy UID i zostanie odkryta w kolejnym przebiegu. Restart ani test połączenia nie wyznaczają nowej granicy.

Klient używa UID SEARCH w skończonym zakresie ustalonym na początku przebiegu, potem UID FETCH rozmiaru/INTERNALDATE i `BODY.PEEK[]`. Nie stosuje UNSEEN ani `n:*`, nie zakłada ciągłości UID, sprawdza UID odpowiedzi. Nie ma STORE, APPEND, MOVE, COPY, DELETE ani EXPUNGE w importerze. Lokalny injector testowy ma APPEND wyłącznie do kontrolowanego loopback Dovecot; nie jest klientem produkcyjnym.

Przed przesunięciem kursora każdy odkryty UID zostaje zapisany jako trwały `pending`. Zbyt duża, zniknięta, uszkodzona lub niepobrana wiadomość zachowuje widoczną pozycję i techniczny błąd. Nie zamyka pracy i nie blokuje późniejszych maili. Próby mają timeout, backoff i limit; po jego wyczerpaniu rekord wymaga kontroli administratora. `last_success` dotyczy zakończonego przebiegu, obok pozostaje licznik problemów pojedynczych wiadomości.

Mailbox ma dzierżawę 240 s i losowy token. Transakcje obejmują tylko krótkie rezerwacje/zapisy. Stary worker po utracie tokenu nie zapisze pliku, kursora ani wyniku. Po awarii następny cykl odzyskuje wygasłą rezerwację. Zadanie ma ograniczenie czasu krótsze niż dzierżawa. Błąd uwierzytelnienia/TLS wstrzymuje importer do jawnego wznowienia po poprawieniu konfiguracji; powtarzające się inne awarie również wymagają wznowienia.

Zmiana UIDVALIDITY zatrzymuje normalny import i ustawia `resync_required`. ADMIN przegląda stan, następnie wybiera **Odbuduj po zmianie UIDVALIDITY**. Wcześniejsza generacja pozostaje w bazie z całą pracą, odczytami, dokumentami i historią. Nowa generacja jest pobierana partiami do osobnych `todo`, oznaczonych do przeglądu odbudowy. Kandydaci wcześniejszych wiadomości wymagają identycznych surowych bajtów SHA-256/rozmiaru, daty dostawcy, nadawcy i tematu; nagłówek Message-ID nie wystarcza. Nawet pewny kandydat nie dziedziczy `done`. Człowiek porównuje wskazany wcześniejszy rekord i może jawnie wybrać „Nie wymaga działania” z powodem odnoszącym się do niego. Niejednoznaczne trafienia pozostają nową pracą. To celowo ostrożny proces odbudowy, bez automatycznego scalania.

Obserwujemy wyłącznie INBOX od granicy startowej. Wiadomość przeniesiona/usunięta przez inny program przed odczytem może być nieosiągalna; filtr przekierowujący od razu do innego folderu wyłącza ją z obserwacji. Nie gwarantujemy dostarczenia niezależnie od reguł i działań innych klientów.

## Niezaufana treść i limity

Stdlib `email` parsuje MIME. HTML-only zamieniamy na tekst po stronie serwera, pomijając skrypty/style; nie wykonujemy HTML, nie pobieramy obrazów, fontów, trackerów ani linków. Źródło i dopuszczone części są prywatnymi plikami pod losowymi kluczami, nigdy pod nazwą z MIME. Pobieranie tylko po sesji z `attachment`, `no-store`, `nosniff` i CSP sandbox. Zablokowane części mają powód, nie mają aktywnego podglądu/pobrania części.

Domyślne limity (konfigurowalne na serwerze): `MAIL_MAX_RAW_BYTES` 30 MiB (także przed alokacją literału IMAP i po odbiorze), `MAIL_MAX_HEADER_BYTES` 128 KiB, `MAIL_MAX_PARTS` 100, `MAIL_MAX_DEPTH` 10, `MAIL_MAX_ATTACHMENTS` 30, `MAIL_MAX_ATTACHMENT_BYTES` do 20 MiB i nigdy ponad limit uploadu, `MAIL_MAX_DECODED_BYTES` 30 MiB łącznie, `MAIL_MAX_BODY_BYTES` 2 MiB. Przekroczenie jest widoczne; nie obcinamy po cichu. DOCX/XLSX są tylko załącznikami, nie uruchamiamy makr. Archiwa, pliki wykonywalne i zagnieżdżone `.eml` nie są automatycznie otwierane. Nie ma antywirusa; walidacja formatu nie oznacza, że plik jest bezpieczny.

Prywatny zapis ma trwały dziennik StorageReservation, zatwierdzony w krótkim osobnym połączeniu PostgreSQL przed zapisaniem bajtów. Pliki powstają pod dokładnym losowym kluczem przez O_EXCL, bez nadpisywania. Dotyczy to surowych maili, części MIME i dokumentów tworzonych z załącznika. Żywy zapis trzyma blokadę advisory; normalny rollback sprząta własne pliki. Po nagłym przerwaniu zadanie maintenance sprawdza wpisy po 15 minutach: usuwa wyłącznie osierocone klucze dziennika, bez aktywnej blokady/dzierżawy i bez referencji z bazy. Powiązane oraz pozostałe pliki magazynu pozostają nietknięte. Faktyczny test SIGKILL po zapisie i przed commitem potwierdził odzyskanie dziennika i selektywne sprzątanie. Spójna kopia nadal wymaga zatrzymania wszystkich procesów zapisujących.

## Demonstracje i test Interii

Offline, przy otwartej aplikacji:

```sh
uv run --project backend python backend/manage.py seed_mail --all
uv run --project backend python backend/manage.py seed_mail --fixture application
# Po ręcznym zakończeniu wcześniejszego wniosku:
uv run --project backend python backend/manage.py seed_mail --fixture reply
```

W Compose odpowiednik to `docker compose run --rm backend python manage.py seed_mail --all`. Każde jawne wywołanie tworzy nowe UID; `--fixture application --uid <znane_UID>` pozwala sprawdzić idempotencję. `oversized` jawnie używa limitu części 1 KiB, aby fixture nie zajmowała dziesiątek MiB w Git. Nie zmienia domyślnego limitu innych wiadomości. Dane demonstracyjne: [fixtures/mail](../fixtures/mail). Generator `python3 scripts/generate_mail_fixtures.py`.

Działający serwer testowy Dovecot/TLS, injector, uruchomienie workera i test flags: [LOCAL_IMAP](LOCAL_IMAP.md). To osobny test protokołu, nie połączenie z Interią.

Przyszłe podłączenie **jawnie udostępnionego konta testowego** Interii:

1. Ponownie sprawdzić [oficjalne parametry](https://pomoc.poczta.interia.pl/programy-pocztowe/news-parametry-do-konfiguracji-programow-pocztowych,nId,2136275): `poczta.interia.pl`, port 993 SSL/TLS, pełny adres. Włączyć dostęp programu pocztowego w ustawieniach konta, jeśli wyłączony. Sprawdzić kompatybilność uwierzytelnienia konta; nie przekazywać hasła do rozmowy ani repo.
2. Sprawdzić pakiet i aktualny [limit transferu](https://pomoc.poczta.interia.pl/moje-konto-i-ustawienia/news-jaka-jest-pojemnosc-konta-pocztowego-w-interia-pl,nId,2136312). Oficjalna strona odczytana 2026-09-05 podaje 1 GB/dzień dla kont bezpłatnych i 15 GB w PocztaPRO; nie zakładamy, jaki pakiet ma kancelaria. Import zużywa wspólny transfer.
3. Skontrolować reguły INBOX i inne programy pocztowe; zapisać liczbę/UID/flags przed próbą. Uzupełnić plik sekretu, zostawić synchronizację wyłączoną i wykonać test połączenia jako ADMIN.
4. Jawnie zezwolić w konfiguracji, rozpocząć jako ADMIN, odczytać widoczną granicę pominiętej historii. Dopiero potem dodać syntetyczny nowy mail do udostępnionego źródła testowego.
5. Zweryfikować import także wiadomości z Seen, dwa konta obsługi, załącznik/OCR/XLSX, reply po done i niezmienność flags/treści/folderów. Przerwać połączenie i sprawdzić wznowienie. Wstrzymać integrację po próbie.

W tej realizacji nie podłączano konta kancelarii ani testowej Interii. Dokumentacja protokołu: [Python 3.12 imaplib](https://docs.python.org/3.12/library/imaplib.html), [IMAP RFC 9051](https://www.rfc-editor.org/rfc/rfc9051.html). Klient celowo używa wspólnego podzbioru IMAP4rev1, bez wymagania rozszerzeń rev2.
