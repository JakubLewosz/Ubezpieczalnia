"""Build and start a fresh isolated synthetic Compose demo; retain its data for inspection."""

import argparse
import json
import os
import secrets
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description="Czysta demonstracja Compose na odrębnych wolumenach.")
    parser.add_argument("--port", type=int, default=5174)
    parser.add_argument("--local-imap", action="store_true", help="Jawnie dołącz uruchomiony lokalny Dovecot testowy.")
    args = parser.parse_args()
    if not 1024 <= args.port <= 65535:
        parser.error("Port musi należeć do zakresu 1024–65535.")
    with socket.socket() as probe:
        try:
            probe.bind(("127.0.0.1", args.port))
        except OSError:
            parser.error("Port jest zajęty; wybierz inny --port. Istniejące procesy pozostają bez zmian.")
    project = "broker-check-" + secrets.token_hex(5)
    directory = ROOT / ".local" / "compose-checks" / project
    directory.mkdir(parents=True, mode=0o700)
    configuration = directory / ".env"
    subprocess.run([sys.executable, str(ROOT / "scripts/generate_local_config.py"),
                    "--output", str(configuration)], check=True)
    with configuration.open("a") as stream:
        stream.write(f"DJANGO_CSRF_TRUSTED_ORIGINS=http://127.0.0.1:{args.port}\n")
        stream.write("DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1,testserver\n")
    env = {**os.environ, "BROKER_ENV_FILE": str(configuration), "BROKER_HTTP_PORT": str(args.port)}
    command = ["docker", "compose", "--project-name", project, "--env-file", str(configuration),
               "--file", str(ROOT / "compose.yaml")]
    if args.local_imap:
        if not (ROOT / ".local/imap-test/local.json").is_file():
            parser.error("Najpierw wykonaj scripts/local_imap.py init oraz start.")
        command.extend(["--file", str(ROOT / "compose.local-imap.yaml")])
    username = "compose.demo"
    password = secrets.token_urlsafe(32)
    credentials = {"username": username, "password": password, "second_username": "compose.second",
                   "second_password": secrets.token_urlsafe(32), "admin_username": "compose.admin",
                   "admin_password": secrets.token_urlsafe(32)}
    if os.environ.get("GITHUB_ACTIONS") == "true":
        for key in ("password", "second_password", "admin_password"):
            print("::add-mask::" + credentials[key], flush=True)
    credentials_path = directory / "credentials.json"
    descriptor = os.open(credentials_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "w") as stream:
        json.dump(credentials, stream)
    metadata = {"project": project, "port": args.port, "environment_file": str(configuration),
                "credentials_file": str(credentials_path), "data": "DANE TESTOWE", "completed": False,
                "local_imap": args.local_imap}
    (directory / "result.json").write_text(json.dumps(metadata, indent=2) + "\n")

    def run(*arguments, **kwargs):
        subprocess.run([*command, *arguments], cwd=ROOT, env=env, check=True, **kwargs)

    try:
        run("build")
        run("up", "-d", "db", "redis", "--wait")
        run("run", "--rm", "backend", "python", "manage.py", "migrate", "--noinput")
        run("run", "--rm", "backend", "python", "manage.py", "makemigrations", "--check", "--dry-run")
        run("run", "--rm", "backend", "python", "/app/scripts/check_ocr.py")
        for prefix, role in (("", "EMPLOYEE"), ("second_", "EMPLOYEE"), ("admin_", "ADMIN")):
            run("run", "--rm", "-T", "backend", "python", "manage.py", "seed_demo", "--username",
                credentials[prefix + "username"], "--role", role, "--password-stdin", "--without-documents",
                input=credentials[prefix + "password"] + "\n", text=True)
        run("up", "-d", "--wait")
        for _ in range(30):
            try:
                with urllib.request.urlopen(f"http://127.0.0.1:{args.port}/api/auth/csrf/", timeout=3) as response:
                    if response.status == 200:
                        break
            except (OSError, ValueError):
                time.sleep(1)
        else:
            raise RuntimeError("Frontend nie udostępnił prawdziwego API pod jednym originem.")
        run("exec", "-T", "worker", "celery", "-A", "config", "inspect", "ping", "--timeout=10")
        metadata["completed"] = True
        print(f"DANE TESTOWE: {project} działa pod http://127.0.0.1:{args.port}.")
        print(f"Konto zapisane prywatnie w {credentials_path}; hasło nie zostało wypisane.")
        print("Teraz uruchom Playwright i scenariusz dokumentowy z tym adresem i kontem.")
    finally:
        (directory / "result.json").write_text(json.dumps(metadata, indent=2) + "\n")
        print(f"Zachowano odrębne wolumeny i metadane próby: {directory}.")
        print("Zatrzymanie bez usuwania danych: powtórz docker compose z project-name/env-file z result.json i down.")


if __name__ == "__main__":
    main()
