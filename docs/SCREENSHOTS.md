# Ekrany demonstracji

Zrzuty z działającej aplikacji i prawdziwej bazy, 5 września 2026. Wszystkie widoczne osoby, organizacje, dokumenty i polisy są syntetyczne. Stan pokazuje moment wykonania zrzutu, nie dane zaszyte we frontendzie.

- [Logowanie](screenshots/01-login.png)
- [Start](screenshots/02-start.png)
- [Klienci](screenshots/03-clients.png)
- [Kartoteka](screenshots/04-client.png)
- [Weryfikacja dokumentu — szeroki ekran](screenshots/05-review-desktop.png)
- [Weryfikacja — telefon](screenshots/06-review-mobile.png)
- [Pola weryfikacji — telefon](screenshots/07-review-mobile-fields.png)
- [Lista polis](screenshots/08-policies.png)
- [Polisa i uczestnicy](screenshots/09-policy.png)

Poniższe zrzuty wykonano po dodaniu wspólnej skrzynki, na działającym lokalnym backendzie PostgreSQL i źródle IMAP Dovecot z syntetycznymi wiadomościami. „Połączono” dotyczy wyłącznie lokalnego serwera testowego. Nie sprawdzano na nich konta Interii.

- [Skrzynka, stan importu, filtry i liczniki — szeroki ekran](screenshots/10-mailbox-desktop.png)
- [Wiadomość HTML-only pokazana jako zwykły tekst i niezależna obsługa](screenshots/11-message-desktop.png)
- [Wiadomość — telefon, szerokość 390 px](screenshots/12-message-mobile.png)
- [Obsługa wiadomości — telefon](screenshots/13-message-mobile-work.png)

Widok HTML-only sprawdzono także przez inspekcję DOM i żądań przeglądarki: brak obrazów, ramek i skryptów wewnątrz treści oraz brak żądań do zewnętrznych hostów podczas otwierania. Dokument przy szerokości widoku 390 px zachowuje szerokość 390 px. Zrzuty przedstawiają nieprzydzieloną wiadomość; samo otwarcie nie przejmuje ani nie zamyka obsługi.
