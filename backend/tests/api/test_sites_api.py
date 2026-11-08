from __future__ import annotations

import json

import httpx
from conftest import gateway_headers, valid_site_payload


def test_site_crud_round_trip(client, admin_headers, create_site) -> None:
    assert client.get("/api/admin/sites", headers=admin_headers).json() == []

    preflight = client.options(
        "/api/admin/sites",
        headers={
            "Origin": "https://console.example",
            "Access-Control-Request-Headers": "authorization",
        },
    )
    assert preflight.status_code == 204
    assert preflight.headers["access-control-allow-origin"] == "*"

    site = create_site(valid_site_payload())
    assert site["name"] == "OpenAI Site"
    assert site["protocols"][0]["models"][0]["model_name"] == "gpt-4o"

    update = client.put(
        f"/api/admin/sites/{site['id']}",
        headers={**admin_headers, "Origin": "https://console.example"},
        json=valid_site_payload(name="Renamed Site", model_name="gpt-4.1"),
    )
    assert update.status_code == 200
    assert update.json()["name"] == "Renamed Site"
    assert update.headers["access-control-allow-origin"] == "*"

    delete = client.delete(f"/api/admin/sites/{site['id']}", headers=admin_headers)
    assert delete.status_code == 204
    assert client.get("/api/admin/sites", headers=admin_headers).json() == []


def test_site_accepts_long_credential_model_pattern(
    client, admin_headers, create_site
) -> None:
    pattern = "|".join(f"^model-{index}$" for index in range(80))
    payload = valid_site_payload()
    payload["credentials"][0]["model_pattern"] = pattern

    response = client.post("/api/admin/sites", headers=admin_headers, json=payload)

    assert response.status_code == 201, response.text
    assert response.json()["credentials"][0]["model_pattern"] == pattern


def test_site_changes_reach_other_gateway_instance(
    client, peer_client, admin_headers, create_site_group_and_key, monkeypatch
) -> None:
    import app.gateway.service.proxy.proxy_upstream as proxy_upstream

    site, _, key = create_site_group_and_key()
    headers = gateway_headers(key)
    body = {"model": "gpt-4o", "messages": [{"role": "user", "content": "hello"}]}
    sent = []

    async def send(_client, upstream, *, stream, body_bytes):
        sent.append((upstream.url, httpx.Headers(upstream.headers)["authorization"]))
        return httpx.Response(
            200,
            json={"choices": [{"message": {"role": "assistant", "content": "ok"}}]},
            request=httpx.Request("POST", upstream.url),
        )

    monkeypatch.setattr(proxy_upstream, "_send_upstream", send)
    initial = peer_client.post("/v1/chat/completions", headers=headers, json=body)
    assert initial.status_code == 200, initial.text
    backup = client.get("/api/admin/backups/export", headers=admin_headers).json()

    payload = valid_site_payload(name="Updated Site")
    payload["base_urls"][0]["url"] = "https://updated.example/v1"
    payload["credentials"][0]["api_key"] = "rotated-test-key"
    saved = client.put(
        f"/api/admin/sites/{site['id']}", headers=admin_headers, json=payload
    )
    assert saved.status_code == 200, saved.text
    updated = peer_client.post("/v1/chat/completions", headers=headers, json=body)
    assert updated.status_code == 200, updated.text
    assert sent[-1] == (
        "https://updated.example/v1/chat/completions",
        "Bearer rotated-test-key",
    )

    disabled = client.put(
        f"/api/admin/sites/{site['id']}/enabled",
        headers=admin_headers,
        json={"enabled": False},
    )
    assert disabled.status_code == 200, disabled.text
    assert peer_client.get("/v1/models", headers=headers).json()["data"] == []

    restored = client.post(
        "/api/admin/backups/import",
        headers=admin_headers,
        files={"file": ("backup.json", json.dumps(backup), "application/json")},
    )
    assert restored.status_code == 200, restored.text
    resumed = peer_client.post("/v1/chat/completions", headers=headers, json=body)
    assert resumed.status_code == 200, resumed.text
    assert sent[-1] == sent[0]
    deleted = client.delete(f"/api/admin/sites/{site['id']}", headers=admin_headers)
    assert deleted.status_code == 204, deleted.text
    assert peer_client.get("/v1/models", headers=headers).json()["data"] == []
