from __future__ import annotations


def test_app_info_returns_runtime_settings_for_admin(client, admin_headers) -> None:
    response = client.get("/api/admin/app-info", headers=admin_headers)

    assert response.status_code == 200
    payload = response.json()
    assert payload["site_name"] == "Lens"
    assert payload["time_zone"]
    assert "openai_chat" in payload["protocol_conversions"]
