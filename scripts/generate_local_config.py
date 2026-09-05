"""Create explicit development configuration without printing secrets."""

import argparse
import os
import secrets
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description="Wygeneruj lokalną konfigurację DANE TESTOWE.")
    parser.add_argument("--output", type=Path, default=Path(__file__).resolve().parents[1] / ".env")
    args = parser.parse_args()
    values = {
        "DJANGO_ENV": "development",
        "DJANGO_SECRET_KEY": secrets.token_urlsafe(64),
        "DJANGO_ALLOWED_HOSTS": "localhost,127.0.0.1",
        "DJANGO_CSRF_TRUSTED_ORIGINS": "http://127.0.0.1:5173,http://localhost:5173",
        "POSTGRES_DB": "broker_office",
        "POSTGRES_USER": "broker",
        "POSTGRES_PASSWORD": secrets.token_urlsafe(32),
        "POSTGRES_HOST": "127.0.0.1",
        "POSTGRES_PORT": "54329",
        "REDIS_URL": "redis://127.0.0.1:56379/0",
        "OCR_CONCURRENCY": "1",
        "VITE_API_PROXY_TARGET": "http://127.0.0.1:8000",
    }
    try:
        descriptor = os.open(args.output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        parser.exit(1, "Plik już istnieje; nie zmieniono konfiguracji ani sekretów.\n")
    with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
        stream.write("# DANE TESTOWE - konfiguracja lokalna, nie dodawać do Git.\n")
        stream.writelines(f"{name}={value}\n" for name, value in values.items())
    print(f"Utworzono {args.output}. Sekrety nie zostały wypisane. Konto utwórz poleceniem seed_demo.")


if __name__ == "__main__":
    main()
