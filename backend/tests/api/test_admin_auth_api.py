from __future__ import annotations


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
