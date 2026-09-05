import secrets
from io import StringIO

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import override_settings

from accounts.models import User
from clients.models import Client
from policies.models import Policy, PolicyParticipant


@pytest.mark.django_db
def test_seed_requires_explicit_development():
    with override_settings(DEVELOPMENT=False), pytest.raises(CommandError, match="development"):
        call_command("seed_demo", without_documents=True)
    assert not User.objects.exists()


@pytest.mark.django_db
def test_seed_is_repeatable_and_has_no_default_password(monkeypatch):
    password = secrets.token_urlsafe(24)
    monkeypatch.setattr("sys.stdin", StringIO(password + "\n"))
    output = StringIO()
    with override_settings(DEVELOPMENT=True):
        call_command("seed_demo", username="seed.demo", password_stdin=True, without_documents=True, stdout=output)
        call_command("seed_demo", username="seed.demo", without_documents=True, stdout=output)
    assert User.objects.get(username="seed.demo").check_password(password)
    assert User.objects.count() == 1
    assert Client.objects.count() == 3
    assert Policy.objects.count() == 2
    assert PolicyParticipant.objects.count() == 5
    assert not Client.objects.exclude(pesel="", nip="").exists()
    assert all(client.email.endswith(".invalid") and "DANE TESTOWE" in client.display_name
               for client in Client.objects.all())
    assert password not in output.getvalue()
