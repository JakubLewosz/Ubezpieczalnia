"""Opt-in real Dovecot TLS + production synchronization + PostgreSQL + API."""
import os
import sys
from pathlib import Path

import pytest

from correspondence.config import current_mailbox
from correspondence.models import Message, ReadReceipt
from correspondence.sync import synchronize, test_connection as connection_test

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.django_db(transaction=True)
@pytest.mark.skipif(os.getenv("RUN_LOCAL_IMAP_TESTS") != "1", reason="Wymaga jawnie uruchomionego lokalnego Dovecot TLS; wykonaj RUN_LOCAL_IMAP_TESTS=1.")
def test_real_tls_server_to_database_and_personal_open_preserves_provider_flags(monkeypatch, api, user):
    sys.path.insert(0, str(ROOT / "scripts"))
    from check_imap_protocol import snapshot
    from local_imap import DIRECTORY, environment, inject

    for name, value in environment().items():
        monkeypatch.setenv(name, value)
    monkeypatch.delenv("MAIL_PASSWORD", raising=False)
    mailbox = current_mailbox()
    assert not mailbox.enabled and mailbox.boundary_uid is None
    assert connection_test()["ok"]
    mailbox.refresh_from_db()
    assert not mailbox.enabled and mailbox.boundary_uid is None
    mailbox.enabled = True
    mailbox.save()
    assert synchronize(mailbox.pk)["status"] == "completed"
    before_inject = snapshot()
    inject(DIRECTORY, ROOT / "fixtures/mail/newsletter.eml", seen=False)
    inject(DIRECTORY, ROOT / "fixtures/mail/newsletter.eml", seen=True)
    before_import = snapshot()
    new_uids = set(before_import) - set(before_inject)
    assert len(new_uids) == 2
    assert synchronize(mailbox.pk)["status"] == "completed"
    messages = Message.objects.filter(mailbox=mailbox)
    assert set(messages.values_list("uid", flat=True)) == new_uids
    assert all(message.status == "todo" and message.fetch_state == "ready" and message.raw_file for message in messages)
    message = messages.first()
    version = message.version
    assert api.get(f"/api/messages/{message.pk}/").status_code == 200
    assert not ReadReceipt.objects.exists()
    assert api.post(f"/api/messages/{message.pk}/read/", {}, format="json").status_code == 200
    message.refresh_from_db()
    assert message.status == "todo" and message.version == version
    assert ReadReceipt.objects.get(message=message).user == user
    assert synchronize(mailbox.pk)["status"] == "completed"
    assert Message.objects.filter(mailbox=mailbox).count() == 2
    assert snapshot() == before_import
