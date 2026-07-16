from __future__ import annotations

from conftest import assert_error, run_async
from lens_api.models import SettingItem
from lens_api.persistence.shared import (
    SETTING_LATEST_VERSION,
    SETTING_LATEST_VERSION_URL,
    SETTING_VERSION_CHECK_AT,
)


def test_version_check_requires_admin(client) -> None:
    response = client.get("/api/admin/version-check")

    assert_error(response, 401, "Not authenticated")


def test_version_check_returns_no_update_by_default(client, admin_headers) -> None:
    response = client.get("/api/admin/version-check", headers=admin_headers)

    assert response.status_code == 200
    payload = response.json()
    assert payload["current_version"]
    assert payload["has_update"] is False
    assert payload["latest_version"] == ""


def test_version_check_reports_stored_newer_release(
    client,
    admin_headers,
    app_state,
    monkeypatch,
) -> None:
    import lens_api.gateway.service.auth as auth_mod

    monkeypatch.setattr(auth_mod, "_read_system_version", lambda: "1.0.0")
    run_async(
        app_state.settings_repo.upsert_settings(
            [
                SettingItem(key=SETTING_LATEST_VERSION, value="1.2.0"),
                SettingItem(
                    key=SETTING_LATEST_VERSION_URL,
                    value="https://example.test/releases/1.2.0",
                ),
                SettingItem(
                    key=SETTING_VERSION_CHECK_AT,
                    value="2026-01-01T00:00:00Z",
                ),
            ]
        )
    )

    response = client.get("/api/admin/version-check", headers=admin_headers)

    assert response.status_code == 200
    assert response.json() == {
        "current_version": "1.0.0",
        "latest_version": "1.2.0",
        "release_url": "https://example.test/releases/1.2.0",
        "has_update": True,
        "checked_at": "2026-01-01T00:00:00Z",
    }
