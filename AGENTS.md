# Broker Office
- Polski interfejs i dokumentacja; angielskie identyfikatory kodu.
- Wyłącznie syntetyczne dane oznaczone DANE TESTOWE; kontakty `.invalid`. Nie dodawaj sekretów, `.env`, magazynu, OCR, eksportów ani backupów do Git.
- Modularny monolit Django 5.2 / DRF / PostgreSQL, React strict / Vite / Tailwind, Celery / Redis i lokalny Tesseract. Sesje i CSRF pod jednym originem.
- Nie wdrażaj produkcyjnie. Brak poczty, zewnętrznego AI, automatycznego tworzenia polis z wniosków.
- Kontroluj wersje edycji; zatwierdzone rewizje i wyniki silnika są niezmienne. Pliki tylko przez uwierzytelnione API.
- Weryfikacja: `uv run --project backend pytest backend/tests`, `uv run --project backend python backend/manage.py makemigrations --check --dry-run`, `uv run --project backend ruff check backend scripts`, `cd frontend && npm run check && npm test && npm run build`, `npm run test:e2e` przy działających usługach.
- Szczegóły: docs/MVP_SPEC.md, docs/API.md, docs/DECISIONS.md, docs/TESTING.md. Przed commitem przejrzyj diff i listę dodawanych plików; nie używaj `git add .`.
