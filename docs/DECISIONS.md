# Decyzje i robocze założenia MVP

Potrzeba biznesowa to wspólna kartoteka, mniej przepisywania danych, powiązanie dokumentów i polis oraz kontrola terminów. Informacja o około 10 pracownikach i 500 klientach pochodzi od właściciela. Nie jest pomiarem wydajności ani ustalonym modelem uprawnień.

## Architektura

1. Modularny monolit Django 5.2 LTS z modułami accounts, clients, documents, extraction, exports, policies i correspondence. Celery jest procesem technicznym tej samej aplikacji, a PostgreSQL jedynym źródłem danych biznesowych. Nie ma mikroserwisów ani SQLite jako substytutu testów integracyjnych.
2. Python 3.12 jest wspierany przez Django 5.2; PostgreSQL 17 mieści się w obsługiwanym zakresie. [Dokumentacja Django](https://docs.djangoproject.com/en/5.2/faq/install/), [wymagania backendu PostgreSQL](https://docs.djangoproject.com/en/5.2/ref/databases/#postgresql-notes). Instalację utrwalają `backend/uv.lock` i `frontend/package-lock.json`.
3. PostgreSQL 17 ma planowane wsparcie do listopada 2029. Obraz demonstracji używa 17.11 i digestu pobranego z oficjalnego rejestru. Aktualizacja poprawkowa wymaga ponowienia testów i świadomego odświeżenia przypięcia. [Polityka wersjonowania](https://www.postgresql.org/support/versioning/).
4. Redis 8 jest kolejką z trwałością AOF; wyniki i statusy są w PostgreSQL. Compose przypina dostępny obraz 8.2.9, lokalny Homebrew dostarczył 8.10.1. Nie są to identyczne wydania: zgodność kolejki jest sprawdzana na lokalnym wydaniu, obraz Compose został oddzielnie zbudowany i uruchomiony podczas naprawy A01. Redis 8 udostępnia AGPLv3 oraz alternatywnie RSALv2/SSPLv1; nie oznaczamy go jako BSD. [Informacja autora o licencjach](https://redis.io/legal/licenses/).
5. Sesje Django i CSRF obejmują również logowanie. Vite przekazuje `/api/`, `/admin/` i `/static/` do Django. Brak szerokiego CORS i publicznego `/media/`. HTTP jest dopuszczony tylko przy jawnym `DJANGO_ENV=development`.
6. Oryginalny plik i jego SHA-256 pozostają bez zmian. pypdf pozyskuje tekst, pypdfium2 renderuje PNG, Tesseract wykonuje lokalny OCR tylko tam, gdzie warstwa tekstowa nie jest użyteczna. Ograniczony numerowany układ ma profil `broker_motor_application_v1`, a wcześniejszy układ pozostaje `broker_motor_application_v0`; bez oceny skuteczności na rzeczywistych dokumentach.
7. Worker ma domyślnie jedno zadanie jednocześnie, prefetch=1 i okresową wymianę procesu. Lease zadania oraz cykliczne odzyskiwanie przez Celery beat przeciwdziałają zadaniom pozostającym bezterminowo w stanie running. Powtórnie dostarczone zadanie nie powinno tworzyć drugiego wyniku. Compose dodaje limity RAM/CPU/procesów; lokalne uruchomienie nie zapewnia równoważnej izolacji.
8. Niezmienny wynik silnika, edytowalny szkic i zatwierdzone rewizje są osobnymi rekordami. Edycje wykorzystują numer wersji i transakcje; konflikt zwraca HTTP 409. Ponowny odczyt nie zastępuje korekt. Reset szkicu do najnowszego wyniku jest jawną operacją.
9. Profil XLSX `review_export_v0` jest odrębny od odczytu. Eksportuje konkretny zatwierdzony snapshot. Arkusz Informacje opisuje pochodzenie; Dane ma jeden wiersz na pole, wraz z grupą/indeksem, typem, jednostką i informacją o korekcie. Tekst nie staje się formułą; kwoty zachowują typ liczbowy.

## Założenia biznesowe wymagające potwierdzenia

- EMPLOYEE obsługuje wszystkie kartoteki i dokumenty. ADMIN dodatkowo administruje kontami. To założenie demonstracyjne, bez uzgodnionej segmentacji klientów i dokumentów.
- Klient jest osobą lub organizacją. Osoba wymaga imienia i nazwiska, organizacja nazwy; identyfikatory i kontakty pozostają opcjonalne. Brak danych nie jest uzupełniany domysłem.
- Niepusty, znormalizowany PESEL osoby lub NIP organizacji jest unikalny również wśród zarchiwizowanych kartotek. Ograniczenie PostgreSQL obejmuje równoczesne dodawanie. Identyczny identyfikator wymaga sprawdzenia istniejącej kartoteki; nie uruchamia scalania. Wspólny kontakt lub podobna nazwa powoduje tylko ostrzeżenie.
- Numer polisy nie jest globalnie unikalny. Ten sam ubezpieczyciel i numer dają ostrzeżenie o możliwym duplikacie. Celowo nie ma automatycznego scalenia ani globalnej unikalności numeru.
- Jedna osoba może pełnić obie role, a polisa mieć kilku ubezpieczonych. Unikalna jest trójka polisa/klient/rola. Dokument ma jedną główną kartotekę i opcjonalną polisę, co wymaga późniejszego uzgodnienia.
- Daty są kalendarzowe. Termin jest w przedziale domkniętym `[dzisiaj, dzisiaj + N dni]` według Europe/Warsaw. Ochrona jest aktywna także w dniu końcowym. 7/30/60 dni to demonstracyjne ustawienia, bez wysyłki powiadomień.
- Kwoty są Decimal; pusta składka pozostaje NULL. Suma ubezpieczenia nie jest składką, a oczekiwany zakres wniosku nie stanowi potwierdzonej ochrony.
- Zatwierdzenie odczytu nie tworzy ani nie zmienia kartoteki lub polisy. Te operacje wykonuje świadomie pracownik.

## Granice demonstracji

Brak uzgodnionego docelowego Excela, procesu odnowień, masowej migracji 500 klientów i infrastruktury produkcyjnej. Zasady przychodzącej wspólnej poczty zlecono w REMEDIATION_SPEC i wdrożono w module correspondence. DOCX/XLSX to wyłącznie załączniki. Nie ma antywirusa, MFA, audytu zgodności ani gwarancji niezawodności usług. Repozytorium nie otrzymało automatycznie licencji open-source.

## Naprawa A i nowa skrzynka

- Pozytywny profil numerowanego wniosku rozpoznaje strukturę i sekcje, nie nazwę pliku ani pojedyncze słowo. Kolejność, warianty i holdout są osobnymi próbami. NNW ma własną kwotę w coverage_items; nie jest składką całej polisy. OCR może mylić Pln/Pin i O/0, dlatego brak pozostaje ostrzeżeniem.
- Tożsamością ręcznej grupy jest UUID serwera, a indeks pomocniczy nie jest ponownie używany. Pochodzenie manual ma autora/czas, nie udaje OCR. Historyczne wyniki i rewizje nie są przepisywane podczas migracji.
- Walidacja formatu to robocza reguła, nie dowód prawdziwości VIN, identyfikatora, daty lub kwoty. Błędna wartość może pozostać do korekty; zatwierdzenie konkretnej wersji wymaga aktualnego potwierdzenia ostrzeżeń i notatki przy sprzeczności. Eksport świadomie zachowanej niepoprawnej liczby/daty pozostawia tekst źródłowy, nie dopowiada wartości.
- Serwer filtruje relacje przed paginacją, UI osobno zachowuje wybrane ID. Zmiana uczestników nie przenosi automatycznie dokumentów. Bieżące blokady sprawdzają archiwizację i uczestników ponownie.
- Jedna wiadomość = jedna pozycja pracy. Osobisty ReadReceipt nie wpływa na wersję wspólnej obsługi. Odpowiedź w dawnym temacie jest nowym todo. Nadawca/Message-ID nie autoryzuje klienta i nie scala pracy.
- Odbieramy tylko INBOX od jednorazowej granicy pierwszej aktywacji. Stan synchronizacji, lease i pending są w PostgreSQL; Redis nie jest źródłem kursora. UIDVALIDITY wymaga jawnej odbudowy z porównaniem pełnych bajtów i metadanych, zawsze bez automatycznego dziedziczenia done.
- Osobny worker OCR i worker mail/maintenance w tej samej aplikacji. Nie wprowadzono kolejnego frameworka, bibliotek sieciowych ani usług AI; IMAP i MIME korzystają ze stdlib Python. Dovecot jest izolowanym serwerem testowym, nie obowiązkowym komponentem połączenia z Interią.
- Tekstowy widok poczty nie wykonuje HTML i nie pobiera odnośników. Załącznik musi przejść wspólne reguły uploadu przed utworzeniem Document. Źródłowa część MIME jest trwałą tożsamością operacji.

Szczegółowe przejścia, prawa, odbudowa, limity i przyszły test dostawcy: [MAILBOX](MAILBOX.md). Wyniki prób: [REMEDIATION_STATUS](REMEDIATION_STATUS.md), [STATUS](STATUS.md).
