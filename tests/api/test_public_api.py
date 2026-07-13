from __future__ import annotations

from conftest import assert_error


def test_public_branding_uses_default_runtime_settings(client) -> None:
    response = client.get("/api/public/branding")

    assert response.status_code == 200
    assert response.json() == {"site_name": "Lens", "logo_url": ""}


def test_app_info_requires_admin_token(client) -> None:
    response = client.get("/api/admin/app-info")

    assert_error(response, 401, "Not authenticated")


def test_app_info_returns_runtime_settings_for_admin(client, admin_headers) -> None:
    response = client.get("/api/admin/app-info", headers=admin_headers)

    assert response.status_code == 200
    payload = response.json()
    assert payload["site_name"] == "Lens"
    assert payload["time_zone"]
    assert "openai_chat" in payload["protocol_conversions"]
