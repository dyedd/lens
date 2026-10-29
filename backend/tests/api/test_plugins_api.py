from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient

BRIDGE = "channel_credential_bridge"
STAMP = "response_header_stamp"


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
    bridge = plugins[BRIDGE]
    assert bridge["state"] == "active"
    assert bridge["author"] == "Lens"
    assert bridge["source"] == "builtin"
    assert set(bridge["extensions"]) == {
        "upstream_request",
        "upstream_credential",
        "request_observer",
        "model_catalog",
    }
    assert {item["key"] for item in bridge["settings"]} == {
        "marker_header",
        "credential",
        "observe",
    }

    # 依赖 bridge 的插件在 bridge 停用后进入 pending，且不再挂扩展点。
    disable_response = client.put(
        f"/api/admin/plugins/{BRIDGE}",
        headers=admin_headers,
        json={"enabled": False},
    )
    assert disable_response.status_code == 200, disable_response.text
    pending = _list_plugins(client, admin_headers)[STAMP]
    assert pending["state"] == "pending"
    assert pending["extensions"] == []

    enable_response = client.put(
        f"/api/admin/plugins/{BRIDGE}",
        headers=admin_headers,
        json={"enabled": True},
    )
    assert enable_response.status_code == 200, enable_response.text
    restored = _list_plugins(client, admin_headers)[STAMP]
    assert restored["state"] == "active"
    assert restored["extensions"] == ["upstream_response"]


def test_plugin_settings_update(
    client: TestClient, admin_headers: dict[str, str]
) -> None:
    response = client.put(
        f"/api/admin/plugins/{BRIDGE}/settings",
        headers=admin_headers,
        json={"values": {"marker_header": "x-tenant", "observe": False}},
    )
    assert response.status_code == 200, response.text
    settings = {item["key"]: item["value"] for item in response.json()["settings"]}
    assert settings["marker_header"] == "x-tenant"
    assert settings["observe"] is False
    # 关闭观察后，请求观察扩展点随之撤下。
    assert "request_observer" not in response.json()["extensions"]

    invalid = client.put(
        f"/api/admin/plugins/{BRIDGE}/settings",
        headers=admin_headers,
        json={"values": {"unknown_key": 1}},
    )
    assert invalid.status_code == 400, invalid.text


def test_plugin_reload_rescans_directory(
    client: TestClient, admin_headers: dict[str, str]
) -> None:
    response = client.post("/api/admin/plugins/reload", headers=admin_headers)
    assert response.status_code == 200, response.text
    ids = {item["id"] for item in response.json()}
    assert {BRIDGE, STAMP} <= ids
    # 平台计划任务始终在，不随插件变化。
    assert {"version_check", "model_price_sync"} <= _cronjob_ids(client, admin_headers)
