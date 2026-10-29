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


def test_plugin_extension_round_trip(
    client: TestClient, admin_headers: dict[str, str]
) -> None:
    plugins = _list_plugins(client, admin_headers)
    bridge = plugins["channel_credential_bridge"]
    assert bridge["state"] == "active"
    assert bridge["extensions"] == ["upstream_credential"]

    # 平台自身的计划任务不因插件启停而消失。
    disable_response = client.put(
        "/api/admin/plugins/channel_credential_bridge",
        headers=admin_headers,
        json={"enabled": False},
    )
    assert disable_response.status_code == 200, disable_response.text
    disabled = disable_response.json()
    assert disabled["state"] == "disabled"
    assert disabled["extensions"] == []
    assert {"version_check", "model_price_sync"} <= _cronjob_ids(client, admin_headers)

    enable_response = client.put(
        "/api/admin/plugins/channel_credential_bridge",
        headers=admin_headers,
        json={"enabled": True},
    )
    assert enable_response.status_code == 200, enable_response.text
    assert enable_response.json()["extensions"] == ["upstream_credential"]
