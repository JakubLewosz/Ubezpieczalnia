import pytest
from rest_framework.test import APIClient
from accounts.models import User

pytestmark = pytest.mark.django_db


def test_login_csrf_session_logout(user):
    browser = APIClient(enforce_csrf_checks=True)
    data = {"username": user.username, "password": "Synthetic-test-only-483!"}
    assert browser.post("/api/auth/login/", data, format="json").status_code == 403
    assert browser.get("/api/auth/csrf/").status_code == 200
    token = browser.cookies["csrftoken"].value
    assert browser.post("/api/auth/login/", data, format="json", HTTP_X_CSRFTOKEN=token).status_code == 200
    assert browser.get("/api/auth/me/").json()["role"] == "EMPLOYEE"
    old_session = browser.cookies["sessionid"].value
    assert browser.post("/api/auth/logout/", {}, format="json").status_code == 403
    assert (
        browser.post(
            "/api/auth/logout/", {}, format="json", HTTP_X_CSRFTOKEN=browser.cookies["csrftoken"].value
        ).status_code
        == 200
    )
    browser.cookies["sessionid"] = old_session
    assert browser.get("/api/auth/me/").status_code == 403


def test_login_throttle_cannot_bypass_with_changed_username(user, settings):
    browser = APIClient(enforce_csrf_checks=True)
    browser.get("/api/auth/csrf/")
    for index in range(settings.LOGIN_MAX_ATTEMPTS):
        response = browser.post(
            "/api/auth/login/",
            {"username": f"missing{index}", "password": "wrong"},
            format="json",
            HTTP_X_CSRFTOKEN=browser.cookies["csrftoken"].value,
        )
        assert response.status_code == 400
    response = browser.post(
        "/api/auth/login/",
        {"username": user.username, "password": "Synthetic-test-only-483!"},
        format="json",
        HTTP_X_CSRFTOKEN=browser.cookies["csrftoken"].value,
    )
    assert response.status_code == 429


@pytest.mark.parametrize(
    "url",
    [
        "/api/auth/me/",
        "/api/clients/",
        "/api/policies/",
        "/api/documents/",
        "/api/dashboard/",
        "/api/documents/1/original/",
        "/api/documents/1/pages/1/",
        "/api/documents/1/review/",
        "/api/revisions/1/",
        "/api/revisions/1/export/",
    ],
)
def test_anonymous_endpoints_denied(url):
    assert APIClient().get(url).status_code == 403


def test_employee_cannot_admin_even_with_django_staff_flag(api, user):
    User.objects.filter(pk=user.pk).update(is_staff=True)
    assert api.get("/admin/accounts/user/").status_code == 302
    admin = User.objects.create_user("test_admin", password="Another-synthetic-748!", role="ADMIN")
    api.force_login(admin)
    assert api.get("/admin/accounts/user/").status_code == 200
    assert api.post("/api/auth/register/", {}).status_code == 404


def test_mutating_api_requires_csrf(user):
    browser = APIClient(enforce_csrf_checks=True)
    browser.force_login(user)
    assert (
        browser.post("/api/clients/", {"kind": "person", "first_name": "X", "last_name": "Test"}).status_code
        == 403
    )


def test_admin_login_has_no_independent_password_endpoint():
    response = APIClient().post("/admin/login/", {"username": "x", "password": "x"})
    assert response.status_code == 302


def test_admin_can_create_and_reset_employee_account(api):
    from django.contrib.auth import authenticate

    admin = User.objects.create_user("manager_test", password="Synthetic-manager-94!", role="ADMIN")
    api.force_login(admin)
    response = api.post(
        "/admin/accounts/user/add/",
        {
            "username": "new_employee",
            "password1": "Created-test-only-748!",
            "password2": "Created-test-only-748!",
            "usable_password": "true",
            "role": "EMPLOYEE",
        },
    )
    assert response.status_code == 302
    employee = User.objects.get(username="new_employee")
    assert employee.role == "EMPLOYEE" and not employee.is_staff
    response = api.post(
        f"/admin/accounts/user/{employee.pk}/password/",
        {
            "password1": "Reset-test-only-159!",
            "password2": "Reset-test-only-159!",
            "usable_password": "true",
        },
    )
    assert response.status_code == 302
    assert authenticate(username=employee.username, password="Created-test-only-748!") is None
    assert authenticate(username=employee.username, password="Reset-test-only-159!").pk == employee.pk
