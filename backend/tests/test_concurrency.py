from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
import pytest
from django.db import close_old_connections
from rest_framework.test import APIClient
from accounts.models import User
from clients.models import Client

pytestmark = pytest.mark.django_db(transaction=True)


def run_two(user, action):
    barrier = Barrier(2)

    def worker(index):
        close_old_connections()
        client = APIClient()
        client.force_login(User.objects.get(pk=user.pk))
        barrier.wait(timeout=10)
        try:
            response = action(client, index)
            return response.status_code
        finally:
            close_old_connections()

    with ThreadPoolExecutor(max_workers=2) as pool:
        return sorted(pool.map(worker, range(2)))


def test_simultaneous_identity_insert_one_wins(user):
    statuses = run_two(
        user,
        lambda api, i: api.post(
            "/api/clients/",
            {
                "kind": "person",
                "first_name": f"Test{i}",
                "last_name": "DANE TESTOWE",
                "pesel": "00000000000",
            },
            format="json",
        ),
    )
    assert statuses == [201, 409]
    assert Client.objects.filter(pesel="00000000000").count() == 1


def test_simultaneous_client_edit_one_wins(user, customer):
    statuses = run_two(
        user,
        lambda api, i: api.patch(
            f"/api/clients/{customer.pk}/", {"version": 1, "note": f"DANE TESTOWE {i}"}, format="json"
        ),
    )
    assert statuses == [200, 409]
    customer.refresh_from_db()
    assert customer.version == 2
