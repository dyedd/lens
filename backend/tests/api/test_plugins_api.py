from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient


def _list_plugins(
    client: TestClient, admin_headers: dict[str, str]
) -> dict[str, dict[str, Any]]:
    response = client.get("/api/admin/plugins", headers=admin_headers)
    assert response.status_code == 200, response.text
    return {item["id"]: item for item in response.json()}


def _cronjob_ids(client: TestClient, admin_headers: dict[str, str]) -> set[str]:
    response = client.get("/api/admin/cronjobs", headers=admin_headers)
    assert response.status_code == 200, response.text
    return {item["id"] for item in response.json()}


def test_plugin_toggle_controls_its_cronjobs(
    client: TestClient, admin_headers: dict[str, str]
) -> None:
    plugins = _list_plugins(client, admin_headers)
    price_sync = plugins["model_price_sync"]
    assert price_sync["state"] == "active"
    assert [task["id"] for task in price_sync["cronjobs"]] == ["model_price_sync"]

    disable_response = client.put(
        "/api/admin/plugins/model_price_sync",
        headers=admin_headers,
        json={"enabled": False},
    )
    assert disable_response.status_code == 200, disable_response.text
    assert disable_response.json()["state"] == "disabled"
    assert "model_price_sync" not in _cronjob_ids(client, admin_headers)

    enable_response = client.put(
        "/api/admin/plugins/model_price_sync",
        headers=admin_headers,
        json={"enabled": True},
    )
    assert enable_response.status_code == 200, enable_response.text
    assert enable_response.json()["state"] == "active"
    assert "model_price_sync" in _cronjob_ids(client, admin_headers)
