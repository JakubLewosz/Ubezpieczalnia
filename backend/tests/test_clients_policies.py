from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import patch
import pytest
from clients.models import Client
from policies.models import Policy, PolicyParticipant

pytestmark = pytest.mark.django_db


def person(**overrides):
    return {"kind": "person", "first_name": "Łucja", "last_name": "Próba", **overrides}


def policy_payload(customer, **overrides):
    return {
        "insurer": "Ubezpieczyciel Testowy",
        "number": "DEMO-001",
        "insurance_type": "Komunikacyjne",
        "start_date": "2026-09-01",
        "end_date": "2027-08-31",
        "premium": "1250.50",
        "currency": "PLN",
        "participants": [
            {"client": customer.pk, "role": "policyholder"},
            {"client": customer.pk, "role": "insured"},
        ],
        **overrides,
    }


def test_client_person_organization_search_archive_and_conflict(api):
    response = api.post("/api/clients/", person(phone="+48 000 123 456"), format="json")
    assert response.status_code == 201, response.data
    first = response.json()
    org = api.post(
        "/api/clients/", {"kind": "organization", "organization_name": "DANE TESTOWE Firma"}, format="json"
    )
    assert org.status_code == 201
    for term in ["Lucja", "proba", "000123456"]:
        assert api.get("/api/clients/", {"search": term}).json()["count"] == 1
    response = api.patch(f"/api/clients/{first['id']}/", {"version": 1, "archived": True}, format="json")
    assert response.status_code == 200
    assert (
        api.patch(f"/api/clients/{first['id']}/", {"version": 1, "note": "stale"}, format="json").status_code
        == 409
    )
    assert api.get("/api/clients/").json()["count"] == 1
    assert api.get("/api/clients/", {"archived": "true"}).json()["count"] == 1
    assert api.delete(f"/api/clients/{first['id']}/").status_code == 405
    assert api.get(f"/api/clients/{first['id']}/history/").json()[0]["action"] == "client.archived"


def test_identity_unique_and_contact_warning_without_merge(api):
    first = api.post(
        "/api/clients/", person(pesel="00000000000", email="shared@example.invalid"), format="json"
    )
    assert first.status_code == 201
    duplicate = api.post("/api/clients/", person(pesel="00000000000"), format="json")
    assert duplicate.status_code == 409
    second = api.post(
        "/api/clients/", person(first_name="Inna", email="shared@example.invalid"), format="json"
    )
    assert second.status_code == 201
    assert second.json()["duplicate_warnings"]
    assert Client.objects.count() == 2


def test_client_validation_optional_data_and_pagination(api):
    assert api.post("/api/clients/", {"kind": "person"}, format="json").status_code == 400
    assert api.post("/api/clients/", {"kind": "organization"}, format="json").status_code == 400
    assert api.post("/api/clients/", person(pesel="123"), format="json").status_code == 400
    for index in range(23):
        Client.objects.create(**person(first_name=f"Test{index}"))
    first = api.get("/api/clients/").json()
    assert first["count"] == 23 and len(first["results"]) == 20 and first["next"]
    assert len(api.get("/api/clients/?page=2").json()["results"]) == 3


def test_policy_multiple_people_same_person_two_roles_and_versions(api, customer):
    other = Client.objects.create(**person())
    payload = policy_payload(customer)
    payload["participants"].append({"client": other.pk, "role": "insured"})
    response = api.post("/api/policies/", payload, format="json")
    assert response.status_code == 201, response.data
    obj = Policy.objects.get()
    assert obj.premium == Decimal("1250.50")
    assert obj.participants.count() == 3
    assert api.get("/api/clients/", {"search": "demo001"}).json()["count"] == 2
    updated = api.patch(f"/api/policies/{obj.pk}/", {"version": 1, "premium": None}, format="json")
    assert updated.status_code == 200 and updated.json()["premium"] is None
    assert (
        api.patch(f"/api/policies/{obj.pk}/", {"version": 1, "number": "stale"}, format="json").status_code
        == 409
    )
    assert (
        api.patch(f"/api/policies/{obj.pk}/", {"version": 2, "archived": True}, format="json").status_code
        == 200
    )
    assert api.get("/api/policies/").json()["count"] == 0


def test_policy_validation_and_same_number_different_insurer(api, customer):
    assert (
        api.post("/api/policies/", policy_payload(customer, end_date="2020-01-01"), format="json").status_code
        == 400
    )
    assert (
        api.post("/api/policies/", policy_payload(customer, premium="-1.00"), format="json").status_code
        == 400
    )
    payload = policy_payload(customer)
    payload["participants"].append(payload["participants"][0])
    assert api.post("/api/policies/", payload, format="json").status_code == 400
    first = api.post("/api/policies/", policy_payload(customer), format="json")
    assert first.status_code == 201
    assert api.post("/api/policies/", policy_payload(customer), format="json").json()["duplicate_warnings"]
    third = api.post("/api/policies/", policy_payload(customer, insurer="Inny Testowy"), format="json")
    assert third.status_code == 201 and not third.json()["duplicate_warnings"]


def test_expiring_inclusive_warsaw_dates(api, customer):
    today = date(2026, 9, 5)
    for offset in [-1, 0, 7, 8]:
        obj = Policy.objects.create(
            insurer="Test",
            number=f"DEMO-{offset}",
            insurance_type="Test",
            start_date=today - timedelta(days=365),
            end_date=today + timedelta(days=offset),
        )
        PolicyParticipant.objects.create(policy=obj, client=customer, role="insured")
    with patch("django.utils.timezone.localdate", return_value=today):
        response = api.get("/api/policies/?expires_in=7").json()
        assert {p["number"] for p in response["results"]} == {"DEMO-0", "DEMO-7"}
        assert all(p["coverage_status"] == "active" for p in response["results"])
    assert api.get("/api/policies/?expires_in=-1").status_code == 400


def test_removed_participant_retains_audit_history(api, customer):
    from common.models import AuditEvent

    other = Client.objects.create(**person())
    payload = policy_payload(customer)
    payload["participants"].append({"client": other.pk, "role": "insured"})
    obj = api.post("/api/policies/", payload, format="json").json()
    response = api.patch(
        f"/api/policies/{obj['id']}/",
        {"version": 1, "participants": policy_payload(customer)["participants"]},
        format="json",
    )
    assert response.status_code == 200
    assert AuditEvent.objects.filter(client=other, action="policy.updated", object_id=obj["id"]).exists()
