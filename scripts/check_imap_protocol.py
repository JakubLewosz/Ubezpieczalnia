"""Exercise the production read-only client against a real local Dovecot TLS server."""

import argparse
import hashlib
import imaplib
import json
import re
import sys
from dataclasses import replace
from pathlib import Path

from local_imap import DIRECTORY, ROOT, USERNAME, connection, environment, inject

sys.path.insert(0, str(ROOT / "backend"))
from correspondence.config import MailConfig
from correspondence.imap_client import IMAPClient, MailError


def snapshot():
    with connection() as client:
        capabilities = {value.lower() for value in client.capabilities}
        assert "imap4rev1" in capabilities and "imap4rev2" not in capabilities
        assert client.select("INBOX", readonly=True)[0] == "OK"
        uids = client.uid("SEARCH", None, "ALL")[1][0].split()
        if len(uids) > 100:
            raise SystemExit("Lokalna skrzynka ma ponad 100 pozycji; użyj osobnej, jawnej demonstracji.")
        result = {}
        for raw_uid in uids:
            uid = int(raw_uid)
            status, data = client.uid("FETCH", str(uid), "(UID FLAGS BODY.PEEK[])")
            assert status == "OK"
            item = next(item for item in data if isinstance(item, tuple))
            # Recent is a session notification, not a stored user flag.
            flags = sorted(flag.decode() for flag in imaplib.ParseFlags(item[0]) if flag != b"\\Recent")
            returned = re.search(rb"\bUID\s+(\d+)", item[0])
            assert returned and int(returned[1]) == uid
            result[uid] = {"sha256": hashlib.sha256(item[1]).hexdigest(), "flags": flags}
        return result


def main():
    parser = argparse.ArgumentParser(description="Wymagany test prawdziwego protokołu lokalnego IMAP/TLS.")
    parser.add_argument("--fixture", type=Path, required=True)
    args = parser.parse_args()
    cfg = environment()
    config = MailConfig(enabled=True, host="127.0.0.1", port=int(cfg["MAIL_PORT"]), username=USERNAME,
                        password=Path(cfg["MAIL_PASSWORD_FILE"]).read_text().strip(), ca_file=cfg["MAIL_CA_FILE"])
    initial = snapshot()
    inject(DIRECTORY, args.fixture, seen=False)
    inject(DIRECTORY, args.fixture, seen=True)
    before = snapshot()
    fresh = sorted(set(before) - set(initial))
    assert len(fresh) == 2
    assert "\\Seen" not in before[fresh[0]]["flags"] and "\\Seen" in before[fresh[1]]["flags"]
    try:
        with IMAPClient(replace(config, ca_file="")):
            raise AssertionError("Przyjęto niezaufany certyfikat lokalnego serwera.")
    except MailError as error:
        assert error.code == "tls_certificate" and error.permanent
    with IMAPClient(config) as client:
        folder = client.open_folder()
        assert client.search_uids(folder.uidnext, folder.uidnext + 3) == []
        assert client.search_uids(folder.uidnext, folder.uidnext - 1) == []
        found = client.search_uids(fresh[0], fresh[-1])
        assert found == fresh
        for uid in found:
            received = client.fetch_message(uid)
            assert hashlib.sha256(received.raw).hexdigest() == before[uid]["sha256"]
            assert received.received_at.utcoffset().total_seconds() == 0
        for command, arguments in (("store", (str(fresh[0]), "+FLAGS", "\\Seen")),
                                   ("uid", ("STORE", str(fresh[0]), "+FLAGS", "\\Seen"))):
            try:
                getattr(client.connection, command)(*arguments)
                raise AssertionError("Klient produkcyjny dopuścił modyfikację flag.")
            except MailError as error:
                assert error.code == "forbidden_command"
    assert snapshot() == before, "Odczyt zmienił flagi, tożsamości UID lub zawartość INBOX."
    result = {"data": "DANE TESTOWE", "server": "Dovecot 2.4.5", "protocol": "IMAP4rev1 over TLS",
              "real_client_messages": 2, "untrusted_certificate_rejected": True,
              "flags_and_content_unchanged": True, "finite_empty_ranges": True,
              "mutating_commands_rejected": True}
    (DIRECTORY / "protocol-result.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
