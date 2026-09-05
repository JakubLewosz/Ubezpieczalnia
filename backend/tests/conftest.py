import pytest
from rest_framework.test import APIClient
from accounts.models import User
from clients.models import Client


@pytest.fixture
def user(db):
    return User.objects.create_user(
        username="test_employee", password="Synthetic-test-only-483!", role="EMPLOYEE"
    )


@pytest.fixture
def api(user):
    client = APIClient()
    client.force_login(user)
    return client


@pytest.fixture
def customer(db):
    return Client.objects.create(
        kind="person", first_name="Alicja", last_name="Testowa", email="alicja@example.invalid"
    )


@pytest.fixture(autouse=True)
def private_test_media(settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path / "media"
    settings.ALLOWED_HOSTS = ["testserver", "localhost", "127.0.0.1"]
