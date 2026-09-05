"""Copy local synthetic test configuration into volumes with separate service owners."""

import os
import shutil
from pathlib import Path

SOURCE = Path("/source")


def main():
    for destination, owner, names in (
        (Path("/target/server"), 1000, ("dovecot.conf", "users", "tls.crt", "tls.key")),
        (Path("/target/client"), 10001, ("tls.crt", "password")),
    ):
        destination.mkdir(parents=True, exist_ok=True)
        os.chown(destination, owner, owner)
        destination.chmod(0o700)
        for name in names:
            target = destination / name
            source = SOURCE / name
            if source.is_symlink() or not source.is_file():
                raise SystemExit("Nieprawidłowa konfiguracja lokalnej skrzynki testowej.")
            if target.exists() and target.read_bytes() != source.read_bytes():
                raise SystemExit("Odmowa zastąpienia konfiguracji istniejącej skrzynki testowej.")
            shutil.copyfile(source, target)
            os.chown(target, owner, owner)
            target.chmod(0o600)
    mailbox = Path("/target/mail")
    os.chown(mailbox, 1000, 1000)
    mailbox.chmod(0o700)
    print("DANE TESTOWE: przygotowano prywatne wolumeny lokalnego IMAP.")


if __name__ == "__main__":
    main()
