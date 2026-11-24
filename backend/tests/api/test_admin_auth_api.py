from __future__ import annotations

from threading import BoundedSemaphore
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.gateway.service import auth


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
    assert client.get("/api/admin/session", headers=admin_headers).status_code == 401
    renewed = {"Authorization": f"Bearer {new_login.json()['access_token']}"}
    assert client.get("/api/admin/session", headers=renewed).status_code == 200


def test_change_password_rejects_wrong_current_password(
    client: TestClient, admin_headers: dict[str, str]
) -> None:
    response = client.put(
        "/api/admin/password",
        headers=admin_headers,
        json={"current_password": "incorrect", "new_password": "changed-password"},
    )

    assert response.status_code == 400


def test_unexpected_value_error_returns_server_error(
    client: TestClient,
    admin_headers: dict[str, str],
    app_state: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fail_profile(
        current_username: str,
        next_username: str,
        current_password: str,
        new_password: str,
    ) -> None:
        raise ValueError("internal failure")

    monkeypatch.setattr(app_state.admin_repo, "update_profile", fail_profile)
    response = client.put(
        "/api/admin/profile",
        headers=admin_headers,
        json={"username": "operator"},
    )

    assert response.status_code == 500
    assert response.json()["error"]["message"] == "Internal server error"


def test_login_throttle_expires_attempts_and_resets_after_success(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    now = [100.0]
    monkeypatch.setattr(auth, "monotonic", lambda: now[0])
    invalid_login = {"username": "admin", "password": "incorrect"}

    for _ in range(4):
        assert client.post("/api/admin/session", json=invalid_login).status_code == 401

    valid_login = client.post(
        "/api/admin/session",
        json={"username": "admin", "password": "password"},
    )
    assert valid_login.status_code == 200

    for _ in range(5):
        assert client.post("/api/admin/session", json=invalid_login).status_code == 401

    throttled_login = client.post("/api/admin/session", json=invalid_login)
    assert throttled_login.status_code == 429
    assert throttled_login.headers["retry-after"] == "60"

    now[0] += 60
    assert client.post("/api/admin/session", json=invalid_login).status_code == 401


def test_login_throttle_rejects_when_verification_slots_are_full(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    verification_slots = BoundedSemaphore(auth._LOGIN_CONCURRENT_VERIFICATIONS)
    for _ in range(auth._LOGIN_CONCURRENT_VERIFICATIONS):
        assert verification_slots.acquire(blocking=False)
    monkeypatch.setattr(auth, "_login_verification_slots", verification_slots)

    response = client.post(
        "/api/admin/session",
        json={"username": "admin", "password": "password"},
    )

    assert response.status_code == 429
    assert response.headers["retry-after"] == "1"


def test_login_throttle_is_isolated_between_application_instances(
    client: TestClient,
    peer_client: TestClient,
) -> None:
    invalid_login = {"username": "admin", "password": "incorrect"}
    for _ in range(auth._LOGIN_FAILURE_LIMIT):
        response = client.post("/api/admin/session", json=invalid_login)
        assert response.status_code == 401

    blocked_login = client.post("/api/admin/session", json=invalid_login)
    assert blocked_login.status_code == 429

    peer_login = peer_client.post(
        "/api/admin/session",
        json={"username": "admin", "password": "password"},
    )
    assert peer_login.status_code == 200, peer_login.text
