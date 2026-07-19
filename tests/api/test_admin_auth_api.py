from __future__ import annotations

from conftest import assert_error


def test_login_returns_bearer_token(client) -> None:
    response = client.post(
        "/api/admin/session",
        json={"username": "admin", "password": "password"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["token_type"] == "bearer"
    assert payload["access_token"]
    assert payload["expires_in"] > 0


def test_login_rejects_bad_credentials(client) -> None:
    response = client.post(
        "/api/admin/session",
        json={"username": "admin", "password": "wrong"},
    )

    assert_error(response, 401, "Incorrect username or password")


def test_current_admin_returns_profile(client, admin_headers) -> None:
    response = client.get("/api/admin/session", headers=admin_headers)

    assert response.status_code == 200
    assert response.json()["username"] == "admin"


def test_current_admin_rejects_invalid_token(client) -> None:
    response = client.get(
        "/api/admin/session",
        headers={"Authorization": "Bearer invalid-token"},
    )

    assert_error(response, 401, "Invalid token")


def test_update_profile_rejects_blank_username(client, admin_headers) -> None:
    response = client.put(
        "/api/admin/profile",
        headers=admin_headers,
        json={"username": " "},
    )

    assert_error(response, 400, "Username is required")


def test_update_profile_renames_admin_and_returns_new_token(
    client,
    admin_headers,
) -> None:
    response = client.put(
        "/api/admin/profile",
        headers=admin_headers,
        json={"username": "operator"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["profile"]["username"] == "operator"
    assert payload["access_token"]

    new_headers = {"Authorization": f"Bearer {payload['access_token']}"}
    profile = client.get("/api/admin/session", headers=new_headers)
    assert profile.status_code == 200
    assert profile.json()["username"] == "operator"


def test_update_profile_requires_current_password_when_changing_password(
    client,
    admin_headers,
) -> None:
    response = client.put(
        "/api/admin/profile",
        headers=admin_headers,
        json={"username": "admin", "new_password": "changed-password"},
    )

    assert_error(response, 400, "Current password is required")


def test_change_password_rejects_wrong_current_password(client, admin_headers) -> None:
    response = client.put(
        "/api/admin/password",
        headers=admin_headers,
        json={"current_password": "wrong", "new_password": "changed-password"},
    )

    assert_error(response, 400, "Current password is incorrect")


def test_change_password_updates_admin_password(client, admin_headers) -> None:
    response = client.put(
        "/api/admin/password",
        headers=admin_headers,
        json={"current_password": "password", "new_password": "changed-password"},
    )

    assert response.status_code == 204
    old_login = client.post(
        "/api/admin/session",
        json={"username": "admin", "password": "password"},
    )
    new_login = client.post(
        "/api/admin/session",
        json={"username": "admin", "password": "changed-password"},
    )
    assert old_login.status_code == 401
    assert new_login.status_code == 200
