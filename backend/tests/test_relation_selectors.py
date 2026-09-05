from concurrent.futures import ThreadPoolExecutor
from datetime import date
from threading import Barrier

import pytest
from django.db import close_old_connections
from rest_framework.test import APIClient

from accounts.models import User
from clients.models import Client
from documents.models import Document
from policies.models import Policy, PolicyParticipant


def make_policy(customer, number, **kwargs):
    policy = Policy.objects.create(
        insurer="Ubezpieczyciel DANE TESTOWE", number=number, insurance_type="komunikacyjne",
        start_date=date(2026, 1, 1), end_date=date(2027, 1, 1), **kwargs,
    )
    for role in ("policyholder", "insured"):
        PolicyParticipant.objects.create(policy=policy, client=customer, role=role)
    return policy


def make_document(customer, user, index, **kwargs):
    # List/relation tests do not open a file; all metadata is synthetic.
    return Document.objects.create(
        client=customer, author=user, original_name=f"DANE TESTOWE wniosek {index:03}.pdf",
        file=f"synthetic-list-only/{index}.pdf", mime_type="application/pdf", size=10,
        checksum=f"{index:064x}", page_count=1, **kwargs,
    )


def test_client_exclusion_happens_before_pagination(api, customer):
    others = [Client.objects.create(kind="person", first_name=f"A{n:03}", last_name="DANE TESTOWE")
              for n in range(26)]
    response = api.get("/api/clients/", {"exclude": ",".join(str(item.pk) for item in others[:25])})
    assert response.status_code == 200
    assert response.json()["count"] == 2
    assert {item["id"] for item in response.json()["results"]} == {customer.pk, others[-1].pk}


def test_upload_policy_selector_can_reach_later_pages_and_excludes_archive(api, customer):
    policies = [make_policy(customer, f"TEST-SELECT-{n:03}") for n in range(26)]
    make_policy(customer, "TEST-ARCHIVED", archived=True)
    other = Client.objects.create(kind="organization", organization_name="Firma DANE TESTOWE")
    make_policy(other, "TEST-OTHER")
    page = api.get("/api/policies/", {"client": customer.pk, "page": 2}).json()
    assert page["count"] == 26 and len(page["results"]) == 6
    assert policies[-1].pk in {item["id"] for item in page["results"]}
    found = api.get("/api/policies/", {"client": customer.pk, "search": "TEST-SELECT-025"}).json()
    assert [item["id"] for item in found["results"]] == [policies[-1].pk]


def test_document_selector_filters_before_pagination_and_preserves_current(api, customer, user):
    other = Client.objects.create(kind="organization", organization_name="Inny klient DANE TESTOWE")
    docs = [make_document(customer, user, n) for n in range(30)]
    foreign = make_document(other, user, 100)
    current = make_policy(customer, "TEST-CURRENT")
    elsewhere = make_policy(customer, "TEST-ELSEWHERE")
    docs[0].policy = elsewhere
    docs[0].save(update_fields=["policy"])
    docs[1].policy = current
    docs[1].save(update_fields=["policy"])
    query = {"eligible_for_policy": current.pk, "participant_clients": customer.pk, "page": 2}
    response = api.get("/api/documents/", query)
    assert response.status_code == 200
    body = response.json()
    assert body["count"] == 29 and len(body["results"]) == 9
    assert docs[0].pk not in {row["id"] for row in body["results"]}
    assert foreign.pk not in {row["id"] for row in body["results"]}
    # Current files remain discoverable even if a participant was removed in an unsaved form.
    retained = api.get("/api/documents/", {"eligible_for_policy": current.pk,
                                        "participant_clients": other.pk}).json()
    assert {row["id"] for row in retained["results"]} == {docs[1].pk, foreign.pk}
    assigned = api.get("/api/documents/", {"policy": current.pk}).json()
    assert [row["id"] for row in assigned["results"]] == [docs[1].pk]
    selected = api.get("/api/documents/", {"ids": f"{docs[2].pk},{docs[27].pk}"}).json()
    assert {row["id"] for row in selected["results"]} == {docs[2].pk, docs[27].pk}
    assert api.get("/api/documents/", {"eligible_for_policy": "new"}).json()["count"] == 0


@pytest.mark.parametrize("url,param", [
    ("/api/clients/", "exclude"), ("/api/documents/", "participant_clients"),
    ("/api/documents/", "ids"), ("/api/documents/", "policy"),
])
def test_selector_rejects_invalid_identifiers(api, url, param):
    for value in ["0", "-1", "x", "9223372036854775808", ","]:
        assert api.get(url, {param: value}).status_code == 400


@pytest.mark.django_db(transaction=True)
def test_two_policies_cannot_concurrently_take_same_document(customer, user):
    policies = [make_policy(customer, f"TEST-RACE-{n}") for n in range(2)]
    document = make_document(customer, user, 200)
    barrier = Barrier(2)

    def assign(index):
        close_old_connections()
        client = APIClient()
        client.force_login(User.objects.get(pk=user.pk))
        barrier.wait(timeout=10)
        try:
            return client.patch(f"/api/policies/{policies[index].pk}/",
                                {"version": 1, "document_ids": [document.pk]},
                                format="json").status_code
        finally:
            close_old_connections()

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(assign, range(2)))
    assert results.count(200) == 1
    assert next(status for status in results if status != 200) in {400, 409}
    document.refresh_from_db()
    assert document.policy_id in {item.pk for item in policies}


def test_incompatible_retained_document_requires_explicit_resolution(api, customer, user):
    policy = make_policy(customer, "TEST-RELATION")
    document = make_document(customer, user, 300, policy=policy)
    other = Client.objects.create(kind="organization", organization_name="Zmiana DANE TESTOWE")
    response = api.patch(f"/api/policies/{policy.pk}/", {
        "version": 1, "participants": [{"client": other.pk, "role": "policyholder"},
                                       {"client": other.pk, "role": "insured"}],
        "document_ids": [document.pk],
    }, format="json")
    assert response.status_code == 400
    document.refresh_from_db()
    policy.refresh_from_db()
    assert document.policy_id == policy.pk and policy.version == 1
