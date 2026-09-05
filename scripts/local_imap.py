"""Explicit local Dovecot fixture server; this helper never accepts a remote host."""

import argparse
import base64
import hashlib
import imaplib
import json
import os
import secrets
import socket
import ssl
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DIRECTORY = ROOT / ".local/imap-test"
USERNAME = "shared@example.invalid"
PROJECT = "broker-imap-test"
DOVECOT_CONFIG = """# DANE TESTOWE — wyłącznie lokalny serwer IMAP.
dovecot_config_version = 2.4.3
dovecot_storage_version = 2.4.3
protocols = imap
base_dir = /run/dovecot
state_dir = /run/dovecot
log_path = /dev/stdout
auth_mechanisms = plain login
auth_allow_cleartext = no
ssl = required
imap4rev2_enable = no
mail_utf8_extensions = no
mail_driver = maildir
mail_home = /srv/vmail/mailbox
mail_path = ~/mail
mail_uid = vmail
mail_gid = vmail
namespace inbox {
  inbox = yes
  separator = /
}
passdb passwd-file {
  passwd_file_path = /broker-config/users
}
userdb passwd-file {
  passwd_file_path = /broker-config/users
}
ssl_server {
  cert_file = /broker-config/tls.crt
  key_file = /broker-config/tls.key
}
!include /etc/dovecot/vendor.d/rootless.conf
service imap-login {
  chroot =
  inet_listener imap {
    port = 0
  }
}
"""


def environment(directory=DIRECTORY):
    info = json.loads((directory / "local.json").read_text())
    return {"MAIL_SYNC_ENABLED": "true", "MAIL_HOST": "127.0.0.1", "MAIL_PORT": str(info["port"]),
            "MAIL_USERNAME": USERNAME, "MAIL_PASSWORD_FILE": str(directory / "password"),
            "MAIL_CA_FILE": str(directory / "tls.crt"), "MAIL_FOLDER": "INBOX", "MAIL_POLL_SECONDS": "15"}


def compose(directory, *arguments, **kwargs):
    info = json.loads((directory / "local.json").read_text())
    env = {**os.environ, "BROKER_IMAP_DIR": str(directory), "BROKER_IMAP_PORT": str(info["port"])}
    return subprocess.run(["docker", "compose", "--project-name", PROJECT, "--file",
                           str(ROOT / "compose.imap-test.yaml"), *arguments],
                          cwd=ROOT, env=env, check=True, **kwargs)


def connection(directory=DIRECTORY):
    cfg = environment(directory)
    context = ssl.create_default_context(cafile=cfg["MAIL_CA_FILE"])
    client = imaplib.IMAP4_SSL("127.0.0.1", int(cfg["MAIL_PORT"]), ssl_context=context, timeout=10)
    client.login(USERNAME, Path(cfg["MAIL_PASSWORD_FILE"]).read_text().strip())
    return client


def initialize(directory, port):
    if directory.exists():
        raise SystemExit("Konfiguracja już istnieje; użyj start. Nie nadpisano sekretów ani skrzynki.")
    with socket.socket() as probe:
        try:
            probe.bind(("127.0.0.1", port))
        except OSError:
            raise SystemExit("Lokalny port IMAP jest zajęty; wybierz inny --port.") from None
    directory.mkdir(parents=True, mode=0o700)
    password = secrets.token_urlsafe(32)
    if os.environ.get("GITHUB_ACTIONS") == "true":
        print("::add-mask::" + password, flush=True)
    (directory / "password").write_text(password + "\n")
    hashed = base64.b64encode(hashlib.sha256(password.encode()).digest()).decode()
    (directory / "users").write_text(f"{USERNAME}:{{SHA256}}{hashed}:1000:1000::/srv/vmail/mailbox::\n")
    (directory / "dovecot.conf").write_text(DOVECOT_CONFIG)
    (directory / "local.json").write_text(json.dumps({"data": "DANE TESTOWE", "port": port, "project": PROJECT}))
    subprocess.run(["openssl", "req", "-x509", "-newkey", "rsa:2048", "-sha256", "-nodes", "-days", "30",
                    "-subj", "/CN=imap-test", "-addext",
                    "subjectAltName=DNS:imap-test,DNS:localhost,DNS:host.docker.internal,IP:127.0.0.1",
                    "-keyout", str(directory / "tls.key"), "-out", str(directory / "tls.crt")],
                   check=True, capture_output=True)
    for path in directory.iterdir():
        path.chmod(0o600)
    print("DANE TESTOWE: wygenerowano lokalne konto i certyfikat; sekretów nie wypisano.")


def inject(directory, fixture, seen=False):
    fixtures = (ROOT / "fixtures/mail").resolve()
    path = fixture.resolve()
    if not path.is_relative_to(fixtures) or path.suffix != ".eml" or fixture.is_symlink():
        raise SystemExit("Dopuszczalne są wyłącznie syntetyczne .eml z fixtures/mail.")
    raw = path.read_bytes()
    if b"DANE TESTOWE" not in raw or len(raw) > 40 * 1024 * 1024:
        raise SystemExit("Brak oznaczenia DANE TESTOWE lub przekroczony limit fixture.")
    # APPEND is confined to this explicit fixture injector connected ONLY to loopback.
    # Production IMAPClient has no mutation methods.
    with connection(directory) as client:
        result, _ = client.append("INBOX", "(\\Seen)" if seen else None, None, raw)
        if result != "OK":
            raise SystemExit("Lokalny serwer nie przyjął fixture.")
    print("DANE TESTOWE: dodano jedną wiadomość do lokalnego INBOX.")


def main():
    os.umask(0o077)
    parser = argparse.ArgumentParser(description="Lokalny Dovecot TLS — nigdy Interia.")
    parser.add_argument("action", choices=("init", "start", "stop", "status", "inject", "run-dev"))
    parser.add_argument("--port", type=int, default=19993)
    parser.add_argument("--fixture", type=Path)
    parser.add_argument("--seen", action="store_true", help="Ustaw Seen wyłącznie przy jawnym dodaniu fixture.")
    args = parser.parse_args()
    if args.action == "init":
        if not 1024 <= args.port <= 65535:
            parser.error("Port poza zakresem 1024–65535.")
        initialize(DIRECTORY, args.port)
    elif args.action == "start":
        compose(DIRECTORY, "up", "-d")
        for _ in range(30):
            try:
                with connection() as client:
                    client.select("INBOX", readonly=True)
                break
            except (OSError, imaplib.IMAP4.error):
                time.sleep(1)
        else:
            raise SystemExit("Lokalny IMAP nie rozpoczął poprawnej pracy TLS w ciągu 30 sekund.")
        print("DANE TESTOWE: lokalny IMAP TLS działa. Import aplikacji włącz świadomie jako ADMIN.")
    elif args.action == "stop":
        compose(DIRECTORY, "down")
    elif args.action == "status":
        compose(DIRECTORY, "ps")
    elif args.action == "inject":
        if args.fixture is None:
            parser.error("Wymagane --fixture fixtures/mail/<plik>.eml.")
        inject(DIRECTORY, args.fixture, args.seen)
    else:
        cfg = {**os.environ, **environment()}
        # Keep the process ID and SIGTERM handling of dev.py; no orphan wrapper.
        os.chdir(ROOT)
        os.execve(sys.executable, [sys.executable, str(ROOT / "scripts/dev.py")], cfg)


if __name__ == "__main__":
    main()
