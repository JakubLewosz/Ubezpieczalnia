# Codex: napraw MVP Broker Office i dodaj wspólną skrzynkę pocztową

## 1. Zadanie i punkt odniesienia

Pracujesz w repozytorium JakubLewosz/Ubezpieczalnia. Rozwijasz ISTNIEJĄCĄ aplikację, nie tworzysz kolejnej od zera. Przeanalizuj kod, napraw problemy, dodaj działającą obsługę przychodzącej poczty i wykonaj testy. Nie kończ na planie, makietach, dokumentacji lub obietnicy późniejszej implementacji.

Punkt odniesienia audytu: gałąź codex/broker-office-mvp, commit b9460085db68688c2c38b2c896cb5106ee6cadbd. Sprawdź bieżący HEAD i zmiany od tego commita. Nie cofaj nowszej pracy. Historyczne numery linii i wyniki nie dowodzą, że problem nadal występuje: zweryfikuj go na bieżącym kodzie.

Materiały pomocnicze, jeśli dołączono je do zadania:
- AUDYT_MVP_Ubezpieczalnia_b946008.md — ustalenia A01–A09 i granice ich potwierdzenia;
- PROBY_AUDYTU_MVP_b946008.zip — syntetyczne próby diagnostyczne, nie gotowe poprawki ani pełne testy integracyjne.

Audyt nie uruchamiał całej aplikacji. Część ustaleń pochodzi z izolowanych funkcji, część z analizy kodu; A07/A08 wymagają odtworzenia w UI. Nie kopiuj adapterów udających Django/DRF z prób do właściwych testów. Przenieś przypadki do normalnego zestawu projektu. Brak załączników nie blokuje zadania: konkretne wymagania są także poniżej.

NOWA DECYZJA O ZAKRESIE: wcześniejsze wyłączenie poczty w audycie, AGENTS.md i specyfikacji dotyczyło pierwszej wersji. Teraz zlecam:
A. stabilizację i naprawę podstawy;
B. następnie implementację wspólnej skrzynki przychodzącej.

Zaktualizuj te instrukcje tylko w tym zakresie. Zakazy prawdziwych danych testowych, automatycznej wysyłki, publicznych plików i zewnętrznego AI pozostają w mocy.

Firma według przekazanego kontekstu ma około 10 pracowników, około 500 klientów i jedną wspólną skrzynkę Interia. Najważniejsza reguła: PRZECZYTANIE WIADOMOŚCI NIE OZNACZA JEJ OBSŁUŻENIA.

## 2. Sposób wykonania i nieprzekraczalne granice

Zachowaj modularny monolit Django/DRF/PostgreSQL, React/TypeScript/Vite, Celery/Redis, lokalny odczyt i prywatny magazyn. Nie wprowadzaj mikroserwisów, bazy wektorowej ani nowego frameworka. Nie aktualizuj wszystkich zależności bez potrzeby. Instaluj z lockfile; konieczne zmiany zależności uzasadnij i zweryfikuj ich zgodność oraz licencje.

Zachowaj sesje, CSRF, role, kontrolę wersji, niezmienne wyniki i zatwierdzenia, źródła danych, bezpieczny XLSX i blokady współbieżności. Nie twórz polisy automatycznie z wniosku ani klienta automatycznie z maila.

Nie kasuj istniejącej bazy, migracji, plików ani historii, żeby testy zaczęły przechodzić. Nowe modele i zmiany formatu wymagają migracji i testu aktualizacji istniejącej demonstracji. Historyczne zatwierdzenia muszą nadal dać się odczytać i eksportować. Nie używaj istniejącej bazy demonstracyjnej jako niszczonej bazy testów.

Pracuj na wydzielonej gałęzi i w logicznych commitach. Nie zmieniaj widoczności repozytorium, nie wykonuj force-push, automatycznego merge, wdrożenia produkcyjnego ani operacji na rzeczywistej skrzynce. Sprawdzaj diff i listę plików przed commitem.

W repo wyłącznie syntetyczne dane, kontakty .invalid i oznaczenia DANE TESTOWE. Żadnych prawdziwych maili, polis, identyfikatorów klientów, podpisów, haseł, tokenów, .env, dumpów ani logów z treścią wiadomości. Syntetyczne .eml trzymaj w jasno wskazanym katalogu fixtures; wszystkie rzeczywiste surowe maile i załączniki poza Git. Nie podłączaj zewnętrznego OCR/LLM.

Przed implementacją przeczytaj instrukcje projektu, modele, frontend, worker, CI i dokumentację. Utwórz krótki plan oraz docs/REMEDIATION_STATUS.md: problem, dowód, test odtwarzający, naprawa, wykonana weryfikacja. Następnie implementuj. Zakończ etap A testem całego procesu dokumentowego przed rozwijaniem etapu B; nie zostawiaj poczty wyłącznie w backlogu.

## 3. A01 — odtwarzalna instalacja, CI i Compose

W historycznym CI npm ci --prefix frontend zgłosiło EUSAGE: brakujące wpisy lockfile, m.in. @emnapi/core, @emnapi/runtime, @emnapi/wasi-threads, tslib. Testy były pominięte, nie zaliczone.

Sprawdź frontend/package.json, package-lock.json, Dockerfile i .github/workflows/ci.yml. Odtwórz problem w czystej instalacji zgodnej z wersjami Node/npm używanymi w CI/Compose. Ustal przyczynę i wygeneruj poprawny lockfile. Zachowaj npm ci oraz zamrożoną instalację Pythona. Nie używaj --force, wyłączenia kontroli ani usuwania testów jako naprawy.

Zweryfikuj instalację, lint, TypeScript, testy, build i migracje. Wykonaj rzeczywiste docker compose build i uruchomienie ze świeżymi, odrębnymi wolumenami testowymi. docker compose config nie potwierdza działania kontenerów.

OCR ma mieć wymagane języki, a obowiązkowy job ma zawodzić przy ich braku, nie kończyć się sukcesem po pominięciu OCR. Playwright uruchamiaj z prawdziwym API, PostgreSQL i workerem. Zachowaj diagnostykę przy błędzie, ale tylko ze sztucznymi danymi i bez sekretów.

Sprawdź aktualny zdalny workflow, jeśli masz uprawnienia i możliwość publikacji w ramach tego zadania. Lokalnego sukcesu nie nazywaj zielonym GitHub Actions. Gdy Docker/zdalne CI rzeczywiście są niedostępne, opisz niewykonany test i komendy; nie deklaruj pełnego odbioru etapu.

## 4. A02 — realistyczny profil wniosku komunikacyjnego

Napraw backend/extraction/engine.py i niezbędne elementy procesu. Obecny parser w audycie nie rozpoznawał numerowanego wniosku, a po zmianie nagłówka uzupełniał tylko 1 z 22 pól. To dotyczyło gotowego tekstu, nie tylko jakości OCR.

Obsłuż jeden ograniczony, rzeczywisty rodzaj układu, nie „dowolny PDF”. Minimalny syntetyczny materiał do odtworzenia:

    DANE TESTOWE
    Białystok, 2026-08-27
    Wniosek brokerski nr TEST/2026/001
    (zapytanie ofertowe)
    1. Ubezpieczający/ Ubezpieczony:
    Anna Demonstracyjna, 00-000 Miejscowość Testowa, ul. Testowa 1.
    PESEL: nie podano. Tel. 000 000 000
    2. Przedmiot ubezpieczenia:
    samochód osobowy MarkaTestowa ModelTestowy, nr rej. DEMO001,
    rok prod. 2020, nr VIN: TEST1234567890123, liczba miejsc 5.
    3. Rodzaj, zakres i suma ubezpieczenia:
    a) OC – ustawowe minimalne sumy gwarancyjne
    b) NNW – 10.000 Pln
    c) Assistance – wariant POLSKA podstawowy
    4. Okres ubezpieczenia: 04.09.2026 – 03.09.2027.
    5. Informacje o kliencie i inne:
    a) ostatni Ubezpieczyciel: Ubezpieczyciel Testowy (polisa 000123)
    6. Warunki płatności: jednorazowo przelewem.

To wzór struktury, nie jedyny tekst, do którego wolno dopasować rozwiązanie. Dodaj warianty numeracji, odstępów, łamania wierszy, skrótów, interpunkcji, brakujących wartości i kolejności sekcji. Przygotuj osobne oczekiwane odpowiedzi i warianty niewykorzystywane do dostrajania. Parser nie może czytać tych oczekiwań ani rozpoznawać nazwy/hasza pliku.

Rozróżniaj numer wniosku od poprzedniej polisy, datę dokumentu od okresu ochrony, sumę NNW od składki i zakres wnioskowany od zawartej umowy. Nie wpisuj „10.000 Pln” jako 10 PLN ani jako składki całej polisy. Przypisz sumę do właściwego elementu zakresu; brak ogólnej sumy nie oznacza zera. Źródło ma wskazywać stronę i rzeczywisty fragment.

Wspólna etykieta Ubezpieczający/Ubezpieczony nie może trafiać do nazwiska. Odwzoruj jednego uczestnika pełniącego obie role, nie dwa nowe rekordy klientów. Rozszerzenie reprezentacji ról/grup nie może uszkodzić zapisanych rewizji starego formatu.

Nie zgaduj niejednoznacznej marki/modelu, nazwiska, identyfikatora czy kwoty. Zachowaj kontrolowane braki i ostrzeżenia. Ubezpieczenie domu, wystawiona polisa i zwykły mail nie mogą zostać rozpoznane jako wniosek komunikacyjny wyłącznie przez pojedyncze słowo. Sprawdź negacje i cytowane fragmenty.

Powtórz testy na syntetycznym PDF tekstowym, skanie, JPEG/PNG i PDF mieszanym. Nie uruchamiaj OCR na stronie z wystarczającym tekstem. Nie przedstawiaj wyników syntetycznych jako procentu skuteczności na całej kancelarii.

## 5. A03 — ręczne uzupełnienie pominiętej struktury

Przeanalizuj extraction/services.py, serializery, widoki i frontend/src/documents.tsx. Samo wymaganie niezmiennej liczby pól blokuje dopisanie uczestnika pominiętego przez parser.

Dodaj kontrolowane operacje dodania i usunięcia uczestnika oraz elementu zakresu w wersji roboczej obsługiwanego profilu. Serwer nadaje stabilną tożsamość grupy, określa dozwolone pola, typy, role i limity. Nie pozwalaj klientowi przesłać arbitralnego schematu JSON. Nie wykorzystuj ponownie identyfikatora usuniętej grupy i nie zmieniaj tożsamości pozostałych przez samo przestawienie kolejności.

Dane dodane ręcznie mają jawne pochodzenie, autora i czas; nie podszywają się pod OCR. Można osobno zachować wskazanie strony wybranej przez człowieka, ale nie jako dowód automatycznego odczytu. Audyt operacji dodania/usunięcia grupy i kontrola wersji są obowiązkowe.

Dodaj także ograniczoną ścieżkę ratunkową: po nieudanym rozpoznaniu pracownik może jawnie wybrać „Uzupełnij ręcznie — wniosek komunikacyjny”. Otrzymuje schemat tego profilu i podgląd, nie fałszywy wynik silnika. Oryginalny wynik pozostaje nierozpoznany/nieudany, a pochodzenie ręcznego szkicu jest odrębne. To nowa decyzja tego zadania, nie twierdzenie o starej specyfikacji. Nie dodawaj uniwersalnego konstruktora formularzy.

Test: parser pomija drugą osobę; pracownik dopisuje ją, zapisuje, zatwierdza i eksportuje obie osoby. Historyczna rewizja nie zmienia się. Analogicznie sprawdź brakujący zakres, wspólne role, usunięcie grupy i konflikt dwóch edycji.

## 6. A04 — kompletne selektory relacji

Napraw wybór polisy przy uploadzie i wybór dokumentów przy polisie. Główne listy mają paginację; problem dotyczy selektorów.

Dodaj filtrowanie na serwerze i dostęp do dalszych stron/wyszukiwania. Przy uploadzie proponuj polisy właściwego klienta zgodne z regułą archiwizacji API. Przy polisie proponuj dokumenty jej uczestników, nieprzypisane do innej polisy, oraz zachowuj jej obecne dokumenty.

Nie pobieraj całej bazy do przeglądarki. Zmiana zapytania, strony lub uczestnika nie może po cichu gubić wcześniej zaznaczonych relacji. Zmiana uczestników ma wywoływać wyjaśniony konflikt niezgodnych dokumentów, nie automatyczne przenoszenie plików.

Sprawdź również wybór klienta: wykluczenia aktualnych uczestników nie mogą uczynić pozostałych kartotek niedostępnymi tylko dlatego, że pierwsza strona zawiera wykluczone wyniki.

Testy: ponad 25 polis jednej kartoteki, ponad 25 dokumentów o podobnych nazwach kilku klientów, wybór spoza pierwszej strony, archiwum i równoczesne przypisanie tego samego dokumentu do dwóch polis.

## 7. A05 — walidacja bieżących danych i świadome zatwierdzenie

Ponownie waliduj odczyt po korekcie i przy zatwierdzaniu, również po zmianie grup. Rozdziel:
- błędy struktury, niedozwolonych typów/ról i bezpieczeństwa — odrzucenie operacji;
- niepełne dane lub sprzeczności dokumentu — konkretne ostrzeżenie i uzgodniona jawna decyzja.

Sprawdzaj m.in. daty i ich kolejność, VIN, e-mail, format identyfikatorów, kwoty i znaczenie przypisanej jednostki. Nie uznawaj walidacji formatu za dowód prawdziwości danych. Nie dopowiadaj braków.

Szkic może zachować niepełną/błędną wartość do poprawienia. Zatwierdzenie z pozostającymi ostrzeżeniami wymaga ich aktualnego, świadomego potwierdzenia; dla istotnej sprzeczności także krótkiej notatki. Potwierdzenie wiąż z konkretną wersją szkicu i zestawem ostrzeżeń. Zmiana pola unieważnia nieaktualne potwierdzenie. Wniosek z błędnym źródłem wolno przepisać wiernie po decyzji człowieka, nie „naprawiać” przez zmyślanie.

Zachowaj rozróżnienie: nie odczytano, brak w dokumencie, wartość ręczna, zero. Ostrzeżenia muszą wskazywać problematyczne pole, nie tylko „sprawdź ręcznie”. Reguły zapisz jako założenia robocze do odbioru przez kancelarię.

## 8. A06 — eksport odporny na niedozwolony tekst

Sprawdź korektę, zatwierdzanie, exports/profile.py i exports/views.py. Znak U+0001 przechodził korektę, a generator zgłaszał IllegalCharacterError.

Waliduj tekst do XLSX, w tym metadane i nazwy, a nie tylko komórki odczytu. Nie niszcz oryginalnego źródła i nie zmieniaj go bez śladu. Nowy szkic ma dostać wskazanie niedozwolonego znaku/pola; ewentualna sanitizacja ma być jawna i audytowana. Dla starej niezmiennej rewizji zwróć kontrolowany błąd eksportu i instrukcję utworzenia korekty, zamiast nieobsłużonego HTTP 500.

Sprawdź też limity długości komórek, by nie obcinać po cichu wartości. Zachowaj typ tekstowy identyfikatorów i ciągów zaczynających się od =, +, -, @ i białych znaków. Prawidłowe daty i liczby pozostają datami/liczbami. Eksport zawsze dotyczy konkretnej zatwierdzonej rewizji.

Dodaj test przez rzeczywiste API i generator: U+0001, inne niedozwolone znaki, dopuszczalne nowe linie/tabulatory, polskie znaki, identyfikatory z zerami, formułopodobny tekst, za długi tekst oraz stare rewizje.

## 9. A07/A08 — przyciski, zapis w toku i stan formularza

Wspólny Button ma domyślnie type="button". Tylko właściwe przyciski zapisu mają jawny submit. Sprawdź wszystkie wywołania, także modale i nową pocztę. „Wczytaj ponownie” po konflikcie nie może uruchamiać dodatkowego POST/PATCH formularza.

Usuń ryzyko utraty edycji podczas zapisu. Dopuszczalne: blokada pól podczas żądania albo zachowanie zmian powstałych po jego wysłaniu. Odpowiedź na wcześniejsze żądanie nie może oznaczać późniejszej zmiany jako zapisanej. Zastosuj regułę do odczytu, klienta, polisy i poczty.

Sprawdź polling i spóźnione odpowiedzi po przejściu między rekordami: nie mogą odtwarzać starego szkicu ani przypisywać danych poprzedniego klienta nowemu formularzowi. Zachowaj ochronę niezapisanych zmian. Wygaśnięcie sesji i konflikt muszą mieć czytelny komunikat, bez cichej utraty treści.

Wykonaj testy komponentowe/przeglądarkowe z opóźnionym PATCH, dwoma kontami i konfliktem. Nie oznaczaj dawnych podejrzeń jako potwierdzonych bez próby; jeśli problem został już naprawiony, udokumentuj test potwierdzający.

## 10. A09 — sekrety i logi

Zamaskuj generowane sekrety CI przed użyciem ich w kolejnych komendach/GITHUB_ENV (::add-mask::). Nie drukuj konfiguracji, haseł ani całych zmiennych środowiskowych. Nie publikuj .env, surowych maili, wrażliwych logów ani uwierzytelnionej sesji jako artefaktów.

Historyczny audyt wskazał sekrety jednorazowego CI, nie potwierdzony wyciek haseł kancelarii. Nie publikuj ponownie ich wartości. Sprawdź nowe ścieżki błędów: szczególnie logowanie IMAP, MIME, OCR i eksport.

## 11. Etap B — produktowe zasady wspólnej skrzynki

Dodaj działającą sekcję „Skrzynka”. Nie zastępuj jej komunikatem „wkrótce” ani tablicą danych w React. Ma korzystać z PostgreSQL, rzeczywistych endpointów i procesu synchronizacji.

W tej wersji JEDNA ODEBRANA WIADOMOŚĆ = JEDNA POZYCJA DO OBSŁUGI. Stan obsługi przechowuj per wiadomość. Powiązane odpowiedzi możesz pokazać kontekstowo na podstawie nagłówków, ale nie potrzebujemy osobnego modułu spraw ani automatycznego łączenia po samym temacie.

Robocze statusy:
- todo — Do obsłużenia; domyślny status każdej nowej wiadomości;
- in_progress — W trakcie;
- waiting — Oczekujemy;
- done — Obsłużona;
- no_action — Nie wymaga działania, z krótkim powodem.

Otwarcie maila, pobranie załącznika, przypisanie klienta i flaga przeczytania u dostawcy NIE zamykają obsługi. Stan przeczytania przechowuj osobno dla każdego użytkownika; jego zapis nie zmienia wersji pracy pozostałych osób. Automatyczne pobranie do aplikacji nie oznacza, że człowiek otworzył wiadomość.

Pracownik widzi, kto i kiedy przejął oraz zakończył obsługę. Przy waiting wymagaj krótkiej notatki, na co czekamy. Przy done zapisz wykonawcę i czas; notatka jest dostępna. To decyzja pracownika, nie dowód wysłania odpowiedzi.

NOWY MAIL W DAWNYM ZAKOŃCZONYM TEMACIE ZAWSZE JEST NOWĄ POZYCJĄ todo, nawet gdy ma ten sam temat, Message-ID jest wadliwy albo inna wiadomość z wątku była obsłużona. Nie zmieniaj historii wcześniej zakończonej wiadomości. To rozstrzygnięcie upraszcza MVP i zabezpiecza przed ukryciem nowej pracy.

Nie dodawaj teraz SMTP, odpowiedzi, przekazywania ani kasowania/przenoszenia maili na Interii. Odpowiadanie pozostaje w dotychczasowej poczcie; pracownik ręcznie odnotowuje wynik. Napisz to jasno w UI i dokumentacji. Nie wyświetlaj przycisku sugerującego działające wysyłanie.

## 12. Odpowiedzialność, współbieżność i audyt poczty

W roboczym modelu wszyscy aktywni pracownicy widzą wspólną skrzynkę. Nie znają ani nie otrzymują z API hasła do Interii.

„Zajmij się” atomowo przypisuje nieprzydzieloną wiadomość do bieżącego pracownika i ustawia in_progress. Dwa równoczesne przejęcia: jedno powodzenie, drugi pracownik otrzymuje informację o konflikcie i właścicielu. Nie stosuj cichego nadpisania.

Stan obsługi, notatki robocze i powiązania zmienia właściciel obsługi lub ADMIN. ADMIN może przypisać/przekazać wiadomość aktywnemu pracownikowi z historią zmiany; pracownik może zwolnić swoją wiadomość z powrotem do todo. Dostępne jest jawne ponowne otwarcie zakończonej pozycji. Opisz dozwolone przejścia i zachowanie przypisania po każdym z nich. Nie przypisuj zadań do nieaktywnych kont; pokaż wiadomości po odebraniu dostępu właścicielowi do administracyjnego przekazania.

Każda istotna modyfikacja wymaga wersji i transakcji. Sprawdzaj uprawnienia po zablokowaniu aktualnego rekordu, nie tylko przed żądaniem. Zapisz kto/co/kiedy, przejście statusu, zmianę właściciela, powiązanie klienta i utworzenie dokumentu. Ponowiona operacja nie może tworzyć podwójnych skutków. Zmiana statusu nie jest twardym usunięciem maila.

Osobiste „przeczytałem” realizuj dedykowaną operacją po otwarciu szczegółów, nie skutkiem pobierania listy. Polling nie generuje nieograniczonej historii przeczytań. Stany techniczne pobierania/parsing failure są oddzielne od stanu biznesowego done.

## 13. Modele i powiązanie z klientami/dokumentami

Dodaj odrębny moduł, np. correspondence, bez konfliktu z modułami standardowymi Pythona. Wspieraj jedną skonfigurowaną skrzynkę; nie buduj wieloorganizacyjnej platformy.

Zaprojektuj minimalne modele dla konfiguracji bez sekretów, stanu synchronizacji, tożsamości zdalnej wiadomości, jej treści/metadanych, obsługi, osobistych odczytów i załączników. Możesz łączyć modele, jeśli odpowiedzialności pozostają czytelne.

Tożsamość importu obejmuje skrzynkę/konto, folder, UIDVALIDITY i UID z ograniczeniem unikalności w bazie. Message-ID służy pomocniczo, nie jest jedynym kluczem deduplikacji. Zachowaj także bezpiecznie oryginalne nagłówki, datę dostawcy, datę zadeklarowaną przez nadawcę i czas importu; nie utożsamiaj ich.

Wiadomość może nie mieć przypisanego klienta i nadal musi być widoczna do obsługi. Nie twórz fikcyjnego klienta „Nieznany”. Pracownik wyszukuje klienta i świadomie wiąże wiadomość; opcjonalnie istniejącą polisę, zgodnie z jej uczestnikami.

Adres nadawcy może dawać kandydatów, ale nigdy automatyczne przypisanie/autoryzację — nawet przy jednym trafieniu. Przy kilku pokaż wybór. Nadawca, nazwa wyświetlana i temat są niezaufanymi danymi.

Załącznik pocztowy może istnieć bez Document, bo obecny Document wymaga klienta. Akcja „Zapisz w dokumentach klienta” wybiera właściwą kartotekę/polisę, uruchamia dotychczasową walidację i tworzy trwałe powiązanie ze źródłowym mailem oraz częścią MIME. Nie osłabiaj istniejących reguł uploadu.

Powtórzenie tej akcji zwraca istniejący wynik, nie drugi dokument. Tożsamością operacji jest źródłowy załącznik, nie sama nazwa pliku lub globalny checksum. Równoczesne próby muszą być bezpieczne. Zmiana klienta przy mailu nie przenosi automatycznie już utworzonego dokumentu do innej kartoteki.

Dokument z maila wchodzi do istniejącego procesu odczytu → weryfikacja → zatwierdzenie → XLSX. Nie buduj drugiej ekstrakcji specjalnie dla poczty. Automatyczne nadejście maila nie uruchamia od razu OCR wszystkich plików.

## 14. Rzeczywisty odbiór IMAP i bezpieczna konfiguracja

Zaimplementuj prawdziwego klienta IMAP, a nie tylko import .eml. Konfiguracja Interii do ponownego sprawdzenia w oficjalnej dokumentacji: serwer poczta.interia.pl, port 993, SSL/TLS, login jako pełny adres. Nie zakładaj nazwy imap.poczta.interia.pl ani istnienia API/webhooka Interii. Nie wyłączaj weryfikacji certyfikatów.

W instrukcji podłączenia uwzględnij wymagane przez Interię włączenie dostępu programu pocztowego, jeśli jest wyłączony, oraz sprawdzenie aktualnych limitów transferu. Nie zakładaj rodzaju pakietu firmowej skrzynki.

Domyślnie zewnętrzna synchronizacja WYŁĄCZONA. Przykładowe ustawienia: MAIL_SYNC_ENABLED=false, MAIL_HOST, MAIL_PORT, MAIL_USERNAME, MAIL_PASSWORD_FILE lub sekret środowiskowy, MAIL_FOLDER=INBOX, MAIL_POLL_SECONDS=60. Nazwy dostosuj do projektu i udokumentuj. Brak konfiguracji nie psuje pozostałej aplikacji.

Hasło wyłącznie po stronie serwera, poza repo. Preferuj plik sekretu/sekrety środowiska; nie przechowuj go jawnie w bazie, nie zwracaj w API, nie używaj prefiksu VITE_, localStorage ani pól diagnostycznych. W tej wersji konfiguracja połączenia jest operacją administratora wdrożenia, nie dowolnym adresem serwera przesyłanym przez pracownika do API.

Dla ADMIN udostępnij stan integracji, bezpieczny test połączenia bez pobierania treści i jawne rozpoczęcie/wstrzymanie importu. Test połączenia sam nie aktywuje synchronizacji ani nie resetuje kursora. Zmiana konta/hosta/folderu nie może podpiąć starego kursora do innej skrzynki.

Nie potrzebujesz hasła kancelarii do implementacji. Nie proś o nie w odpowiedzi ani nie próbuj logować się na jej konto. Rzeczywistą próbę sieciową wykonuj wyłącznie na jawnie udostępnionej skrzynce testowej. Brak takiego konta nie jest przeszkodą dla działającego klienta i lokalnych testów IMAP, ale uniemożliwia twierdzenie „sprawdzono na Interii”.

## 15. Synchronizacja bez zmiany cudzej poczty i bez cichych pominięć

Wszystkie połączenia z rzeczywistym dostawcą są tylko do odczytu: EXAMINE/read-only oraz BODY.PEEK dla treści/nagłówków. Żadnego STORE, APPEND, MOVE, COPY, DELETE, EXPUNGE, oznaczania \Seen, modyfikowania folderów ani flag. Nie używaj POP3. Nie pobieraj wyłącznie UNSEEN: mail otwarty wcześniej w Interii nadal wymaga importu i statusu todo.

Pierwsza aktywacja: domyślnie „nowe wiadomości od uruchomienia”. Atomowo utrwal jednorazową granicę UID i UIDVALIDITY z pierwszego udanego otwarcia folderu. Pokazuj ją jako wyłączenie wcześniejszej historii, nie jako obsłużenie starych maili. Test połączenia i zwykły restart nie wyznaczają nowej granicy. Maile napływające podczas inicjalizacji nie mogą zginąć między zapisem granicy a pierwszym przebiegiem.

Automatyczny import całej historii, folderu Wysłane, spamu i kosza pozostaje poza zakresem. Opisz ograniczenie: obserwujemy INBOX; wiadomość usunięta/przeniesiona przez inny program przed odczytem może nie zostać pobrana. Nie gwarantuj dostarczenia wszystkich maili niezależnie od działań innych klientów. Przed przyszłym pilotażem trzeba sprawdzić reguły folderów i programy usuwające pocztę.

Używaj UID, nie zmiennych numerów sekwencyjnych. Nie zakładaj ciągłości UID. Pracuj partiami w skończonym zakresie ustalonym na początku przebiegu. Pusty zakres ma nie uruchamiać pobrania. Przetestuj pułapkę zakresu UID n:*, który może zwrócić ostatnią starą wiadomość; jawnie sprawdzaj zwrócone UID i granice.

Postęp odkrywania i nieudane pobrania muszą być trwałe. Nie przesuwaj kursora poza nieutrwalone wiadomości bez zapisania ich jako oczekujących na ponowienie. Wiadomość za duża, uszkodzona lub z problematycznym załącznikiem ma widoczny rekord/stan wymagający uwagi, nie znika i nie blokuje kolejnych maili. Przy rozłączeniu podczas pobrania spróbuj ponownie bez duplikatu.

Zadbaj o idempotencję, ograniczone ponowienia, timeouty i backoff. Błąd hasła/certyfikatu nie powinien powodować ciągłych prób logowania. Pokaż błąd i sposób wznowienia. last_success oznacza pomyślny przebieg, nie sam otwarty socket; pokaż też zaległe błędy pojedynczych wiadomości.

Jedna aktywna synchronizacja na skrzynkę: krótka blokada/transakcja do rezerwacji, wygasająca dzierżawa i token próby. Nie trzymaj transakcji podczas całego połączenia sieciowego. Po utracie dzierżawy stary worker nie może przesuwać postępu. Restart/awaria workera nie powoduje trwałego utknięcia.

Przy zmianie UIDVALIDITY zatrzymaj normalny import i pokaż ADMIN „wymagana ponowna synchronizacja”. Nie resetuj jej po cichu ani nie nadpisuj istniejących statusów. Dodaj jawny, udokumentowany proces odbudowy stanu: wcześniejsza historia zostaje zachowana, pewne dopasowania wymagają dodatkowej weryfikacji treści, niejednoznaczne trafiają do przeglądu. Nie łącz po samym Message-ID i nie oznaczaj nieznanej wiadomości jako wcześniej obsłużonej.

Synchronizacja okresowa działa na serwerze przy zamkniętej przeglądarce. Oddziel ją od ciężkiego OCR przez kolejki i odpowiednią konfigurację workerów tego samego backendu. Pojedyncze długie OCR nie ma blokować skrzynki. Zaktualizuj Compose, dev.py, routing i beat tak, aby żadne zadanie nie pozostało w nieobsługiwanej kolejce.

## 16. MIME, treść i załączniki jako niezaufane wejście

Przygotuj ograniczony zasobowo parser MIME: tekst zwykły, multipart/alternative i mixed, HTML-only, kodowane polskie nagłówki i nazwy plików, brak/duplikaty Message-ID, błędne daty i charsety. Używaj sprawdzonych bibliotek, nie własnego parsera MIME opartego na regexach.

Na pierwszy etap wybierz BEZPIECZNY WIDOK TEKSTOWY. text/plain wyświetlaj jako tekst. HTML-only zamień na czytelny tekst po stronie serwera, bez wykonywania HTML/JS/CSS. Nie używaj dangerouslySetInnerHTML dla treści maila. Nie ładuj zdalnych obrazów, fontów, pikseli śledzących ani adresów z HTML. Nie pobieraj linków w tle. Zachowaj akapity i pozwól obejrzeć pełny tekst, nie tylko fragment.

Kontroluj wielkość wiadomości przed pełnym pobraniem oraz rzeczywiście odebrane bajty, liczbę części, poziom zagnieżdżenia MIME i rozmiar dekodowanych załączników. Ustal jawne konfigurowalne limity demonstracyjne, spójne z istniejącym limitem dokumentów. Nie pobieraj wielokrotnie całej skrzynki. Części odrzucone przez limity pozostaw widoczne z powodem.

Surowa wiadomość, gdy ją przechowujesz, oraz załączniki są prywatnymi niezmiennymi plikami. Nazwa z MIME nigdy nie jest ścieżką na dysku. Pliki pobieraj wyłącznie przez uwierzytelnione API z bezpiecznymi nagłówkami, attachment/no-store; nie przez publiczny URL.

Dokumenty dopuszczonych typów przechodzą wspólną walidację. Nie wykonuj makr, skryptów ani plików wykonywalnych. Nie rozpakowuj automatycznie archiwów i zagnieżdżonych .eml. Zablokowane typy pokaż bez udostępniania aktywnego podglądu. Brak antywirusa musi pozostać jawnym ograniczeniem; nie oznaczaj pliku jako „bezpieczny” po samym sprawdzeniu rozszerzenia.

Import pliku i zapis rekordu muszą obsługiwać awarię bez osieroconych plików lub podwójnego dokumentu. Audyt i logi nie powinny powielać treści wszystkich maili.

## 17. Interfejs skrzynki i demonstracja

Dodaj „Skrzynka” do menu i powiązaną korespondencję w kartotece klienta. Lista: nadawca z adresem, temat, czas odebrania, załączniki, stan obsługi, odpowiedzialny pracownik, klient i osobisty znacznik otwarcia.

Filtry: wymagające działania (todo/in_progress/waiting), nieprzydzielone, moje, wszystkie, status, klient i proste wyszukiwanie po temacie/nadawcy. Zapewnij paginację. Dla kolejki pracy domyślnie pokaż najstarsze niezałatwione; umożliwiaj zmianę sortowania. Liczniki mają pochodzić z całego filtrowanego zbioru w API, nie długości bieżącej strony.

Szczegóły: pełny tekst, załączniki, historia, przyciski przejęcia/zmiany stanu, notatka i powiązania. Akcje zależą od uprawnień API i aktualnej wersji. Nowa wiadomość pojawia się po odświeżeniu/pollingu bez przeładowania całego programu, ale polling nie zabiera wpisywanej notatki.

Pokaż stan źródła: „tryb demonstracyjny”, „integracja wyłączona”, „połączono”, „błąd”, „wymaga synchronizacji”. Wyświetl ostatni udany przebieg i zaległe problemy. Nie pokazuj „brak nowych wiadomości”, jeśli synchronizacja nie działa. Przycisk odświeżenia listy odróżnij od zlecenia połączenia z IMAP; zlecenie jest limitowane i nie tworzy równoległych prac.

Na starcie dodaj rzeczywiste liczniki wiadomości do obsługi i linki do odpowiednich filtrów. Zachowaj istniejące terminy polis i dokumenty do sprawdzenia.

Dodaj jawny seed/komendę demonstracyjną z syntetycznymi .eml: nowy wniosek z PDF, brak klienta, kilka pasujących kartotek, newsletter, HTML-only, wadliwy nagłówek, niedozwolony i zbyt duży załącznik oraz odpowiedź do zakończonego tematu. Dodanie kolejnej wiadomości ma być osobną świadomą czynnością, możliwą przy otwartej aplikacji. Dane zapisuj przez ten sam proces parsowania/importu do bazy, nie jako atrapy API w React. Tryb demo nie łączy się z Internetem i nie miesza się z prawdziwą skrzynką.

## 18. Weryfikacja całości

Dodawaj testy w trakcie zmian. Użyj prawdziwego PostgreSQL dla transakcji/konfliktów i prawdziwego Celery/Redis dla integracji asynchronicznych. Mocki zostają w testach jednostkowych, ale nie są jedynym dowodem działania.

Minimalny zakres:

1. A01–A09: nowe regresje, stare testy, migracja istniejącej demonstracji, świeża instalacja i Compose.

2. Dokument: realistyczny syntetyczny wniosek, OCR, korekta grup/ról, ostrzeżenia, zatwierdzenie, pobranie i sprawdzenie rzeczywistej zawartości XLSX.

3. Poczta: parsowanie MIME, prywatne pobrania, role/CSRF, osobiste otwarcie bez zmiany obsługi, nieprzydzielony mail i kandydaci bez automatycznego przypisania.

4. Praca współbieżna: dwa przejęcia, konflikt notatki/statusu, przekazanie przez ADMIN, nieaktywny pracownik, spóźniona odpowiedź API.

5. Import: ponowienie tej samej wiadomości i załącznika, brak/duplikat Message-ID, równe tematy różnych nadawców, nowa odpowiedź po done, restart i rozłączenie w połowie.

6. IMAP: inicjalizacja granicy, mail przychodzący podczas niej, już przeczytane wiadomości, brak nowych UID, luki UID, puste INBOX, zniknięcie wiadomości, zmiana UIDVALIDITY i odzyskanie po awarii.

7. Zasoby/bezpieczeństwo: limity, uszkodzone MIME, HTML/XSS, próba ścieżki w nazwie, blokowane typy, brak zewnętrznych żądań z treści, brak sekretów w API/logach.

8. Harmonogram: długie OCR nie blokuje synchronizacji; podwójne zlecenie nie dubluje pracy; wyłączona/błędna konfiguracja nie psuje innych modułów.

Wykonaj co najmniej jeden rzeczywisty test klienta po protokole IMAP z lokalnym serwerem testowym (np. osobny profil Compose dobranej, wspieranej implementacji). Nie wystarczy podmiana wszystkich metod klienta zwracająca gotowe JSON-y. Dostarcz instrukcję i fixture umieszczane w tej lokalnej skrzynce. Testy lokalnego serwera nie mogą wysyłać niczego do Interii. Sprawdź flags przed i po imporcie/otwarciu; \Seen i zawartość folderów muszą pozostać bez zmian. Testuj też odmowę błędnego certyfikatu; nie dodawaj globalnego obejścia TLS na potrzeby CI.

Pełny Playwright dla poczty:

nowy mail testowy trafia do źródła → worker go importuje → pojawia się Do obsłużenia → otwarcie nie zmienia stanu → pracownik przejmuje → drugi widzi właściciela → powiązanie klienta → zapis załącznika → istniejący odczyt/weryfikacja/XLSX → świadome Obsłużona → nowa odpowiedź nadal Do obsłużenia.

Sprawdź także newsletter jako Nie wymaga działania, mail bez klienta, wybór spoza pierwszych 20 wyników i konflikt bez utraty tekstu.

Uruchom dotychczasowy test backup/restore, rozszerzając go o maile, załączniki, stan obsługi, osobiste odczyty i kursor. Odtwarzaj tylko do osobnej bazy. Restart nie zmienia zatwierdzeń ani statusów. Po odtworzeniu zewnętrzną synchronizację pozostaw wstrzymaną do świadomej kontroli stanu przez administratora, aby przypadkiem nie uruchomić drugiego importera.

Sprawdź ekrany desktop i wąskie, klawiaturę, focus i stany błędów. Wszystkie zrzuty wyłącznie z syntetycznych danych. Nie utożsamiaj zebranej liczby testów z gwarancją bezpieczeństwa albo gotowością produkcyjną.

## 19. Dokumentacja i końcowy odbiór

Zaktualizuj README, AGENTS.md, specyfikację, API, DECISIONS, TESTING, SECURITY, STATUS oraz rejestr A01–A09. Dodaj docs/MAILBOX.md z modelem stanów, uprawnieniami, deduplikacją, inicjalizacją i odzyskiwaniem synchronizacji, ograniczeniami INBOX, konfiguracją i instrukcją wyłączenia.

Dokumentacja ma pozwolić przejść od czystego klona do dwóch działających demonstracji bez zgadywania. Dodaj instrukcję lokalnego IMAP oraz oddzielną checklistę przyszłego podłączenia testowego konta Interia. Nie podłączaj rzeczywistej kancelarii i nie ogłaszaj zgodności z RODO/produkcyjnej gotowości.

Pozostają poza zakresem: SMTP/odpowiedzi, pełna historyczna poczta, odnowienia i generowanie nowych dokumentów, automatyczna migracja 500 klientów, chatbot, dowolne szablony Excel i uniwersalny parser ubezpieczeń. Kontrolny eksport nadal nie jest docelowym zestawieniem kancelarii.

W końcowej odpowiedzi podaj:
- dla A01–A09: odtworzone/już naprawione/niepotwierdzone, zmianę i wykonany test;
- działający zakres poczty i świadome ograniczenia;
- dokładne komendy uruchomienia i demonstracji;
- rzeczywiście uruchomione testy, wyniki, środowisko i niewykonane kroki;
- czy sprawdzono tylko lokalny IMAP, czy także jawnie udostępnioną testową Interię;
- branch/commity i pozostałe blokady odbioru.

Nie wpisuj, że „wszystko działa”, jeśli sprawdzono tylko import modułów, makiety lub mocki. Brak dostępu do zewnętrznego konta ma być konkretnym ograniczeniem weryfikacji dostawcy, nie wymówką dla brakującego modułu.

Zacznij od inspekcji i krótkiego planu. Wykonuj etapy kolejno, zachowując działający stan po każdym. Jeżeli limit środowiska przerwie pracę, zapisz dokładny punkt kontynuacji i testy pozostałe do wykonania; nie ukrywaj niewykonanego zakresu.

### Oficjalne materiały techniczne do ponownego sprawdzenia

Interia, parametry i dostęp programów pocztowych:
https://pomoc.poczta.interia.pl/programy-pocztowe/news-parametry-do-konfiguracji-programow-pocztowych,nId,2136275

IMAP:
https://www.rfc-editor.org/rfc/rfc9051.html

Sprawdź także dokumentację klienta używanego w projekcie i zgodność z IMAP4rev1. Nie wymagaj od Interii rozszerzeń rev2 bez weryfikacji.

GitHub, maskowanie wartości:
https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-commands#masking-a-value-in-a-log