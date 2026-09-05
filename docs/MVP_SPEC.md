# Zadanie: zbuduj od zera pierwsze działające MVP systemu kancelarii ubezpieczeniowej

Pracujesz jako doświadczony inżynier full-stack. Masz zaprojektować, zaimplementować i przetestować aplikację, a nie tylko opisać rozwiązanie lub przygotować makiety. Nazwa robocza: Broker Office. Odpowiadaj po polsku; identyfikatory w kodzie zapisuj po angielsku.

Budujemy od zera. Nie wykorzystujemy wcześniejszego kodu. Ewentualne screeny starej aplikacji pokazują jedynie kontekst: nie są specyfikacją, wzorcem UX ani dowodem działających integracji.

## 1. Kontekst i granice wiedzy

Według informacji właściciela projektu kancelaria ma około 10 pracowników i około 500 klientów. Pracownicy korzystają z rozproszonych folderów i dokumentów. Potrzebują centralnej kartoteki, powiązania dokumentów i polis, ograniczenia przepisywania danych do Excela, pilnowania kończących się polis oraz usprawnienia obsługi wspólnej poczty Interia. Program docelowo ma służyć pracy w biurze.

Nie ustalono jeszcze docelowego Excela, pełnego modelu wszystkich ubezpieczeń, dokładnego procesu odnowień, zasad poczty, migracji ani infrastruktury produkcyjnej. Nie zamieniaj tych niewiadomych w rzekomo zatwierdzone wymagania.

Decyzje opisane poniżej są założeniami pierwszego MVP demonstracyjnego. Zapisz je osobno od potrzeb biznesowych. W szczególności: dostęp pracowników do wszystkich klientów, dwa poziomy uprawnień, lokalny odczyt dokumentów, pierwszy profil ekstrakcji i kontrolny eksport są decyzjami roboczymi.

Wszystkie dane do rozwoju, testów i demonstracji mają być syntetyczne. Nie potrzebujesz dostępu do prawdziwych dokumentów, kont pocztowych ani bazy klientów.

## 2. Wynik pierwszego MVP

Zaimplementuj działający przebieg:

logowanie → znalezienie lub dodanie klienta → wgranie dokumentu przy kliencie → rzeczywisty lokalny odczyt → sprawdzenie i korekta pól obok podglądu → zatwierdzenie wersji → pobranie kontrolnego XLSX.

Dodatkowo przygotuj podstawową ręczną ewidencję polis i prostą listę ich terminów. Całość ma korzystać z prawdziwego backendu i PostgreSQL. Dane mają przetrwać odświeżenie strony oraz restart usług.

Pierwszy automatyczny profil odczytu ogranicz do wniosku brokerskiego dotyczącego ubezpieczenia komunikacyjnego, w kilku syntetycznych wariantach układu. To pilotaż, nie uniwersalny parser wszystkich dokumentów kancelarii.

Nie implementuj teraz: integracji rzeczywistej poczty, wysyłania wiadomości, chatbotu, porównywarki ofert, rozbudowanych „Spraw”, globalnej kolejki sugestii AI, generowania dokumentów odnowieniowych, edytora Word/PDF, automatycznej migracji folderów, płatności, wielu organizacji ani pełnotekstowego przeszukiwania wszystkich dokumentów. Nie pokazuj pustych zakładek udających te funkcje. Opisz je w backlogu.

## 3. Technologia i struktura

Przyjmij następującą bazę techniczną:

- Backend: Python 3.12, Django 5.2 LTS z aktualnymi poprawkami oraz Django REST Framework.
- Baza: wspierana stabilna wersja PostgreSQL; migracje Django od początku.
- Frontend: React, TypeScript w trybie strict, Vite, Tailwind; spójne dostępne komponenty, np. shadcn/ui.
- Uwierzytelnianie: sesje Django i CSRF, bez własnego systemu JWT.
- Zadania odczytu: Celery i Redis, osobny proces wykonawczy, nie osobny system biznesowy.
- Dokumenty: prywatny lokalny magazyn plików na trwałym wolumenie; metadane w bazie.
- Odczyt: pypdf dla tekstu, pypdfium2 do renderowania, Tesseract z językami polskim i angielskim jako lokalny OCR.
- XLSX: openpyxl.
- Testy: pytest/pytest-django, testy komponentów oraz Playwright dla przebiegów przeglądarkowych.
- Środowisko: Docker Compose, z instrukcją uruchomienia i testowania również w środowisku Codex bez dostępnego demona Docker.

Zweryfikuj zgodność wybranych wersji na podstawie oficjalnej dokumentacji i instalacji. Utrwal rzeczywiście zainstalowane wersje w lockfile. Nie używaj nieprzypiętych obrazów latest, przypadkowych wersji beta ani nieinstalowalnych zależności. Sprawdź i zapisz licencje istotnych zależności. Nie zmieniaj całego stosu wyłącznie z przyzwyczajenia; rzeczywistą przeszkodę opisz w decyzjach architektonicznych.

Zbuduj modularny monolit. Rozdziel moduły kont, klientów, dokumentów, ekstrakcji, eksportu i polis, ale nie twórz mikroserwisów, Kubernetes, bazy wektorowej, silnika workflow ani ogólnego frameworka CRUD. Frontend i API powinny pracować pod jednym originem; w development użyj proxy. Nie rozwiązuj problemów integracji przez wyłączenie CSRF lub szerokie CORS.

## 4. Konta i uprawnienia

Przygotuj indywidualne logowanie, wylogowanie, pobranie bieżącego użytkownika i dwa robocze poziomy: ADMIN oraz EMPLOYEE. Nie myl biznesowej roli pracownika z uprawnieniem Django do panelu administracyjnego.

W MVP pracownik może obsługiwać wszystkie kartoteki, dokumenty, odczyty i polisy. Administrator dodatkowo zarządza użytkownikami. Do administracji kontami możesz wykorzystać zabezpieczony panel Django; nie potrzebujemy drugiego rozbudowanego panelu.

Nie udostępniaj publicznej rejestracji. Tworzenie i administracyjny reset kont przygotuj bez integracji mailowej. Backend ma wymuszać uprawnienia na każdym chronionym endpointcie, w tym przy podglądzie i pobieraniu plików. Ukrycie przycisku w UI nie jest zabezpieczeniem.

Dodaj ograniczanie prób logowania i przetestuj CSRF także dla logowania. Sesja ma być odwoływana przy wylogowaniu. W konfiguracji docelowej wymagaj bezpiecznych ciasteczek i HTTPS; odstępstwo dla lokalnego HTTP ogranicz do wyraźnego trybu developerskiego.

Nie zapisuj haseł w repozytorium. Dane dostępowe demonstracyjne mają być tworzone jawnie przez polecenie developerskie, nie domyślnie przy każdym starcie. Nie uruchamiaj seeda w konfiguracji produkcyjnej.

## 5. Kartoteki klientów

Zaimplementuj listę, wyszukiwanie, dodawanie, edycję, kartotekę szczegółową i archiwizację zamiast twardego usuwania.

Klient jest osobą fizyczną albo organizacją. Nie twórz osobnych baz „klientów komunikacyjnych” i „klientów nieruchomościowych”. Jeden podmiot może uczestniczyć w różnych ubezpieczeniach.

Minimalne dane: imię i nazwisko albo nazwa organizacji, opcjonalne PESEL/NIP, dane kontaktowe, adres, notatka i status archiwizacji. Zależnie od typu wymagaj właściwej nazwy, ale nie wymuszaj identyfikatorów i kontaktów, których pracownik jeszcze nie zna. Identyfikatory przechowuj jako tekst, nie liczby. Nie wyliczaj automatycznie niepodanych danych osobowych.

Wyszukiwanie ma obejmować nazwę, imię/nazwisko, podane identyfikatory i kontakty oraz powiązany numer polisy. Zapewnij paginację, sortowanie i normalizację wyszukiwania bez niszczenia oryginalnej wartości. Wyszukiwanie po VIN i rejestracji jest późniejszym rozszerzeniem, dopóki nie ma uzgodnionej ewidencji pojazdów.

Pokaż ostrzeżenie o możliwym duplikacie, ale nigdy automatycznie nie łącz kartotek. Wspólny e-mail lub telefon nie dowodzi tożsamości. Regułę postępowania z identycznym PESEL/NIP opisz jako założenie MVP; uwzględnij równoczesne dodawanie rekordów. Nie blokuj różnych klientów tylko z powodu podobnego nazwiska.

W kartotece pokaż dane, przypisane dokumenty, ręcznie zapisane polisy i historię istotnych operacji. Nie ukrywaj informacji w wielu niepowiązanych ekranach.

## 6. Podstawowa ewidencja polis

Przygotuj ręczne dodanie, edycję i archiwizację polisy. Minimum: ubezpieczyciel, numer, rodzaj ubezpieczenia, data początku i końca ochrony, opcjonalna składka i waluta, opis przedmiotu oraz powiązane dokumenty.

Uczestników polisy zapisuj przez relację do kartotek z rolą, przynajmniej ubezpieczający i ubezpieczony. Jedna osoba może mieć obie role, a ubezpieczonych może być kilku. Nie twórz nowej osoby dla każdego wystąpienia roli. Zabezpiecz przed powieleniem tej samej relacji roli.

Nie twórz jeszcze rozbudowanych osobnych modułów pojazdów i nieruchomości. Dane wydobyte z wniosku mogą pozostać w wersjonowanym odczycie; model podstawowej polisy nie musi zawierać każdego pola dokumentu.

Daty ochrony to daty kalendarzowe, nie timestampy. Waliduj koniec względem początku. Kwoty zapisuj jako Decimal, nigdy float. Brak składki nie oznacza zera. Numer polisy nie jest globalnym identyfikatorem wszystkich ubezpieczycieli; regułę wykrywania duplikatów zaprojektuj i udokumentuj ostrożnie.

Dodaj filtr kończących się polis z wyborem zakresu dni. Zakresy np. 7/30/60 dni oznacz jako ustawienia demonstracyjne, nie uzgodnione reguły kancelarii. W obliczeniach użyj daty Europe/Warsaw i jawnie ustal, czy końce przedziału są wliczane. Nie wysyłaj powiadomień. Status okresu ochrony wyliczaj z dat, nie utrwalaj jako stale dezaktualizującego się pola.

## 7. Dokumenty i bezpieczny magazyn

Dokument w MVP ma jedną główną kartotekę klienta i opcjonalną powiązaną polisę. Jest to uproszczenie do późniejszej weryfikacji. Nie kopiuj pliku tylko dlatego, że w dokumencie występuje kilka osób.

Przechowuj oryginalną nazwę, bezpieczny wewnętrzny klucz, wykryty typ, rozmiar, sumę kontrolną, kategorię, datę dodania, autora i relacje. Oryginału nie modyfikuj podczas OCR ani poprawek odczytu. Suma kontrolna ma umożliwiać ostrzeżenie przed ponownym wgraniem, nie automatyczne przypisanie dokumentu do innej osoby.

Automatycznie przetwarzaj wyłącznie PDF/JPEG/PNG. DOCX/XLSX mogą być przechowywane i pobierane jako załączniki, bez odczytu i edycji. Pozostałe formaty w tej wersji odrzucaj z wyjaśnieniem; nie udawaj pełnej obsługi wszystkich formatów kancelarii.

Waliduj rozszerzenie i zawartość, rozmiar, liczbę stron i rozmiary rozpakowywanych/renderowanych danych. Ustal konfigurowalne limity developerskie, np. 20 MB oraz 30 stron na dokument. Zadbaj o błędne, zaszyfrowane i uszkodzone pliki oraz obrazy o nadmiernej liczbie pikseli. Nie wykonuj makr, skryptów ani poleceń pochodzących z pliku lub jego nazwy.

Nie udostępniaj magazynu przez publiczny /media/. Każde pobranie oryginału i każda strona podglądu wymagają sesji i uprawnienia. Dobierz bezpieczne nagłówki odpowiedzi; nie renderuj dowolnej zawartości użytkownika jako HTML. Podgląd dokumentów może korzystać z przygotowanych w tle obrazów stron.

Nie dodawaj komunikatu „przeskanowano antywirusowo”, jeżeli skanera nie ma. Brak skanowania opisz jako ograniczenie demonstracji i element do rozstrzygnięcia przed pilotażem produkcyjnym.

## 8. Lokalny odczyt dokumentów

Zaimplementuj rzeczywisty odczyt treści, nie gotowe odpowiedzi przypisane do nazwy pliku, jego hasha lub seeda. Dla stron z użyteczną warstwą tekstową korzystaj z tekstu. Dla stron obrazowych lub pozbawionych wystarczającej warstwy tekstowej użyj lokalnego OCR. Obsłuż mieszany PDF. Zapisuj metodę odczytu i numer strony.

Nie podłączaj zewnętrznych usług AI/OCR, nie wymagaj kluczy API, nie pobieraj wielkich modeli i nie zakładaj GPU. To nie jest decyzja o docelowym silniku: na tym etapie ma działać lokalny, ograniczony i testowalny pilot.

Rozdziel pozyskanie tekstu od interpretacji pól. Przygotuj niewielki interfejs silnika ekstrakcji, który później pozwoli zastąpić reguły innym rozwiązaniem. Nie buduj platformy pluginów na zapas.

Pierwszy profil: wniosek brokerski komunikacyjny. Rozpoznawaj na podstawie treści i etykiet przynajmniej: numer wniosku, uczestników ubezpieczenia i ich role, dane kontaktowe/adresowe, podstawowe dane pojazdu (marka/model, rejestracja, VIN, rok), początek i koniec wnioskowanej ochrony, żądany zakres, poprzedniego ubezpieczyciela, poprzedni numer polisy oraz sposób płatności.

Pola trudniejsze lub niejednoznaczne pozostaw puste z ostrzeżeniem i możliwością ręcznego wpisania. Nie oznaczaj tego jako uniwersalnej skutecznej ekstrakcji. Osobno rozróżniaj sumę ubezpieczenia i składkę, poprzedni numer polisy i numer wniosku, datę dokumentu i okres ochrony. Oczekiwany zakres we wniosku nie jest potwierdzonym zakresem wystawionej polisy.

Dla innego rodzaju dokumentu pokaż „Brak profilu automatycznego odczytu”. Oryginał nadal ma być dostępny. Nie interpretuj dokumentu nieruchomościowego jako komunikacyjnego i nie zwracaj pozornego sukcesu z przypadkowymi liczbami.

Każde odczytane pole przechowuje kod, wartość, typ/jednostkę, lokalizację w grupie powtarzalnej, numer strony i krótki fragment źródła. Jeśli nie da się wskazać źródła, zaznacz to. Nie twórz wymyślonych procentów pewności; wystarczą jawne ostrzeżenia i metoda pozyskania.

Zadania działają w tle, mają stan queued/running/succeeded/failed, ograniczenia czasu i zasobów oraz możliwość kontrolowanego ponowienia. Stan zadania technicznego jest oddzielny od zatwierdzenia biznesowego. Ponowne dostarczenie zadania nie tworzy dodatkowego wyniku. Obsłuż przerwanie procesu wykonawczego tak, aby zadanie nie zostało bezterminowo „w trakcie”. Domyślnie ogranicz współbieżność OCR do jednego zadania; ustawienie ma być konfigurowalne. Surowej treści i danych osobowych nie zapisuj w logach procesu.

## 9. Weryfikacja, wersje i równoczesna praca

Najważniejszy ekran: dokument po jednej stronie, formularz odczytu po drugiej. Zapewnij strony, powiększenie, grupowanie pól, widoczne braki, ostrzeżenia i zapis wersji roboczej. Kliknięcie źródła powinno co najmniej przełączać podgląd na odpowiednią stronę. Dokładne prostokąty zaznaczeń nie są wymagane w pierwszej wersji.

Oddziel niezmienny wynik silnika, poprawianą wersję roboczą i zatwierdzoną wersję. Pracownik może zmienić wartość albo oznaczyć „brak w dokumencie”. Zachowaj informację, co zmieniono ręcznie, przez kogo i kiedy. Pole wpisane ręcznie nie może udawać wartości odczytanej ze wskazanego fragmentu.

Zatwierdzenie tworzy niezmienny snapshot z autorem i czasem. Późniejsza korekta tworzy nową wersję; wcześniejszy zatwierdzony wynik nadal istnieje. Ponowny odczyt nie nadpisuje korekt ani zatwierdzeń. W MVP nie trzeba budować zaawansowanego graficznego porównywacza wersji.

Zabezpiecz zapis i zatwierdzanie przed równoczesnym nadpisaniem przez dwóch pracowników: numer wersji, transakcja i czytelny konflikt zamiast cichego last-write-wins. Kluczowe edycje kartotek/polis również nie powinny bez ostrzeżenia nadpisywać nowszych danych.

Zatwierdzenie odczytu nie tworzy automatycznie klienta ani polisy i nie aktualizuje ich danych. W tym MVP te operacje pozostają świadomymi czynnościami pracownika. Wniosek brokerski nigdy nie staje się polisą wyłącznie dlatego, że ekstrakcja się powiodła.

## 10. Eksport kontrolny XLSX, nie docelowy Excel kancelarii

Nie otrzymaliśmy docelowego arkusza. Nie twórz pozornie ostatecznego raportu kancelarii. Zbuduj i jednoznacznie oznacz profil review_export_v0: „Eksport kontrolny — układ demonstracyjny, do uzgodnienia”.

Ustal prosty, udokumentowany format: arkusz Informacje z wersją profilu, dokumentem, zatwierdzoną rewizją i ostrzeżeniem; arkusz Dane z jednym wierszem na pole zatwierdzonej rewizji. Kolumny obejmują grupę/indeks, kod i nazwę pola, wartość, typ/jednostkę, stronę źródłową i oznaczenie korekty ręcznej. Zachowaj odrębność powtarzających się uczestników i zakresów.

Eksportuj zatwierdzony snapshot, nie bieżące niezapisane wartości z formularza. API ma odrzucać eksport niezatwierdzonego odczytu. Powtórny eksport tej samej rewizji daje te same dane. Zmiana klienta lub polisy nie zmienia historycznego eksportu. Zapisz zdarzenie eksportu z użytkownikiem i identyfikatorem rewizji.

Zachowaj polskie znaki, daty, jednostki, typy liczbowe i zera wiodące identyfikatorów. Wartości tekstowe mają być tekstem, nigdy aktywną formułą, również gdy zaczynają się od =, +, -, @ lub białych znaków przed nimi. Nie konwertuj prawdziwych kwot na tekst tylko po to, by obejść bezpieczeństwo. Sprawdź zawartość wygenerowanego XLSX w testach.

Logikę profilu oddziel od ekstrakcji. Późniejsze dostarczenie Excela ma wymagać dodania uzgodnionego mapowania, a nie przebudowy magazynu dokumentów. Nie buduj teraz wizualnego edytora dowolnych mapowań.

## 11. Interfejs

Przygotuj polski, czytelny interfejs do wielogodzinnej pracy biurowej: jasny motyw, spokojne kolory, wyraźny tekst, spójne formularze i sensowne odstępy. Nie kopiuj ciemnego wyglądu starych screenów. Nie twórz landing page, marketingowych wykresów ani dekoracyjnego dashboardu.

Menu ogranicz do działających obszarów: Start, Klienci, Dokumenty, Polisy oraz administracja dla uprawnionych. Start pokazuje rzeczywiste dane: dokumenty oczekujące na sprawdzenie, błędy odczytu i kończące się polisy.

Na szerokim ekranie widok dokumentu i formularza jest dwukolumnowy, na mniejszym przechodzi w wygodny układ pionowy. Obsłuż klawiaturę, etykiety, fokus, kontrast, stany ładowania, brak wyników, błędy API i niezapisane zmiany. Nie zakładaj określonej wielkości monitora. Każdy widoczny przycisk ma działać albo jasno wyjaśniać ograniczenie.

Frontend nie może korzystać z atrap zamiast API. Dane syntetyczne mogą pochodzić z seeda w bazie, nie z zaszytych tablic udających działanie aplikacji. Zadbaj o polski format prezentacji dat i kwot, przy stabilnym formacie API.

## 12. Bezpieczeństwo i dane demonstracyjne

Repozytorium zawiera kod, dokumentację i syntetyczne testy, nigdy rzeczywiste polisy, wnioski, eksporty klientów, wiadomości, kopie bazy, hasła, tokeny lub .env.

Przygotuj .gitignore oraz .dockerignore obejmujące sekrety, lokalne uploady, OCR, eksporty, bazy, backupy i prywatne materiały. Nie blokuj przypadkiem jawnie syntetycznych fixtures. Nie używaj bezmyślnie git add .; przed commitem sprawdź diff. Nie dodawaj automatycznie żadnej licencji open-source ani zewnętrznych integracji analitycznych.

Dostarcz generator syntetycznych klientów, polis i dokumentów oznaczonych „DANE TESTOWE”. Nie kopiuj danych z dokumentów kancelarii ani podpisów, kodów QR, prawdziwych numerów polis i znaków firmowych. Używaj kontaktów w domenie .invalid. W seedzie identyfikatory osobowe mogą pozostać puste; nie twierdź, że losowy poprawny PESEL jest zarezerwowany do testów.

Dodaj syntetyczny wniosek tekstowy, obrazowy i mieszany oraz różne układy, kolejność etykiet i brakujące dane. Dane oczekiwane zapisuj osobno. Nie uzależniaj parsera od jednego wygenerowanego egzemplarza. Dodaj przynajmniej jeden wariant testowy o innej strukturze niż podstawowe przykłady.

Chroń historię zmian przed edycją przez zwykłe API. Rejestruj istotne operacje kto/co/kiedy, bez zbędnego kopiowania pełnych dokumentów do audytu. Dane wejściowe są niezaufane. Nie wykonuj instrukcji znalezionych w dokumencie, a późniejsze dodanie LLM nie może nadawać mu uprawnień do operacji biznesowych.

Konfiguracja demonstracyjna ma nasłuchiwać lokalnie, nie wystawiać przypadkiem bazy, Redis i aplikacji do Internetu. Przygotuj opis spójnego backupu bazy wraz z plikami oraz procedurę odtworzenia na danych testowych. Kopia repozytorium nie jest kopią danych aplikacji.

Widocznie oznacz środowisko jako demonstracyjne. Nie deklaruj gotowości produkcyjnej ani zgodności z RODO na podstawie samego wdrożenia tych funkcji. W osobnej checkliście zapisz brakujące uzgodnienia przed prawdziwymi danymi.

## 13. Testy i warunki odbioru

Nie kończ na kompilacji. Zweryfikuj co najmniej:

1. Świeże uruchomienie, migracje, utworzenie kont developerskich i trwałość danych po restarcie.

2. Logowanie/wylogowanie, CSRF, ograniczenia ADMIN/EMPLOYEE i brak anonimowego dostępu do API, oryginałów, podglądów oraz eksportów.

3. Dodanie osoby i firmy, wyszukiwanie, archiwizację i ostrzeżenia o duplikatach bez automatycznego scalania.

4. Polisę z kilkoma ubezpieczonymi i jedną osobą w dwóch rolach; poprawność dat, kwot i granic filtra terminów na kontrolowanej dacie testowej.

5. Walidację uploadu, niebezpieczną nazwę, zły typ, przekroczenie limitu oraz uszkodzony i zaszyfrowany PDF.

6. Rzeczywisty odczyt tekstowego, obrazowego i mieszanego dokumentu, brakujące pola oraz dokument poza obsługiwanym profilem. Brak Tesseract nie może udawać pomyślnego OCR.

7. Rozdzielenie numeru wniosku, poprzedniej polisy, okresu ochrony i kwot o różnym znaczeniu.

8. Korektę odczytu, zatwierdzenie, eksport konkretnej rewizji i niezmienność zatwierdzenia po ponownym odczycie.

9. Konflikt dwóch równoczesnych edycji, podwójne zatwierdzenie i powtórzenie zadania bez duplikowania wyników.

10. Rzeczywistą zawartość XLSX, identyfikatory z zerem wiodącym, liczby, daty i brak formuł pochodzących z niezaufanego tekstu.

11. Przebieg Playwright: logowanie → klient → upload syntetycznego dokumentu → odczyt → korekta → zatwierdzenie → pobranie XLSX.

CI ma uruchamiać testy backendu z PostgreSQL, kontrolę migracji, lint, TypeScript i build frontendu oraz istotne testy integracyjne. Zapewnij test prawdziwego OCR w jobie mającym wymagane narzędzia; mocki są dopuszczalne w testach jednostkowych, nie jako jedyny dowód integracji.

Uruchom aplikację i obejrzyj kluczowe ekrany w dostępnej przeglądarce. Przygotuj screeny wyłącznie syntetycznych danych. Jeśli środowisko nie umożliwia któregoś testu, podaj dokładnie który, z jakiego powodu i jak go wykonać. Nie wpisuj „testy przeszły”, gdy nie zostały uruchomione. Nie podawaj procentowej skuteczności odczytu rzeczywistych dokumentów na podstawie syntetycznego zestawu.

## 14. Dokumentacja, Git i sposób wykonania

Najpierw sprawdź zawartość repozytorium, branch, narzędzia i ograniczenia środowiska. Nie zakładaj, że pliki wymienione w opisie istnieją. Zachowaj istniejący README i inne instrukcje, jeżeli są zgodne z zadaniem. Nie usuwaj cudzych zmian i nie nadpisuj konfiguracji bez potrzeby.

Zapisz plan implementacji, ale potem od razu przejdź do kodu. Kolejność: uruchamialna podstawa i konta; klienci i dokumenty; lokalny odczyt, weryfikacja i eksport; podstawowe polisy; testy całości i dopracowanie UI. Testy dodawaj podczas implementacji, nie dopiero w ostatnim kroku.

Utwórz zwięzły AGENTS.md z zasadami projektu, komendami weryfikacji, granicami zakresu i zakazem rzeczywistych danych. Dłuższą specyfikację zapisz w docs/MVP_SPEC.md; nie wkładaj całej dokumentacji do AGENTS.md.

Dostarcz też:

- README.md: przeznaczenie, zakres działający, wymagania i dokładne komendy uruchomienia od czystego klona, także dla użytkownika Windows/PowerShell.
- .env.example bez sekretów oraz pomocniczy sposób wygenerowania lokalnej konfiguracji; bez stałego hasła administratora.
- docs/DECISIONS.md: ważne wybory techniczne i jawne założenia biznesowe.
- docs/STATUS.md: zaimplementowane i sprawdzone elementy, ograniczenia, nierozstrzygnięte pytania i następny krok.
- docs/TESTING.md: komendy, zakres testów i scenariusz demonstracji.
- docs/SECURITY.md: aktualne zabezpieczenia, ograniczenia, backup/restore i warunki poprzedzające użycie rzeczywistych danych.
- docs/BACKLOG.md: dalsze moduły bez udawania, że już istnieją.

Pracuj w wydzielonej gałęzi zadania. Rób logiczne zmiany nadające się do przeglądu. Korzystaj ze standardowego mechanizmu zapisania wyniku w używanym środowisku Codex; nie wykonuj force-push, automatycznego merge do main, zmian widoczności repozytorium ani wdrożenia produkcyjnego. Nie wymagaj produkcyjnych sekretów w CI.

Nie czekaj na docelowy Excel, pocztę ani serwer, żeby wykonać opisany zakres demonstracyjny. Drobne decyzje podejmuj samodzielnie i zapisuj. Jeżeli ograniczenie środowiska rzeczywiście blokuje pracę, zachowaj działający stan, opisz blokadę i nie zastępuj brakującej funkcji pozornym sukcesem.

Na zakończenie podaj: co rzeczywiście działa, jak uruchomić i przejść demonstrację, jakie testy uruchomiono i z jakim wynikiem, czego nie sprawdzono, znane ograniczenia oraz zalecany następny etap. Podaj branch i commit, jeśli powstały. Nie deklaruj całego MVP jako ukończonego, jeśli brakuje kluczowego przebiegu.

Zacznij od inspekcji repozytorium i krótkiego planu. Następnie implementuj, uruchamiaj, testuj i poprawiaj działającą aplikację.