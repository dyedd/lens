from __future__ import annotations

import httpx
from conftest import gateway_headers, openai_chat_channel_id


def test_gateway_api_key_crud_round_trip(
    client,
    admin_headers,
    create_gateway_key,
) -> None:
    assert client.get("/api/admin/gateway-api-keys", headers=admin_headers).json() == []

    key = create_gateway_key(
        remark="  primary  ",
        allowed_models=[" gpt-4o ", "", "gpt-4o"],
        max_cost_usd=5,
    )
    assert key["remark"] == "primary"
    assert key["api_key"].startswith("sk-lens-")
    assert key["allowed_models"] == ["gpt-4o"]
    assert key["spent_cost_usd"] == 0

    updated = client.put(
        f"/api/admin/gateway-api-keys/{key['id']}",
        headers=admin_headers,
        json={
            "remark": "disabled",
            "enabled": False,
            "allowed_models": ["gpt-4.1"],
            "max_cost_usd": 10,
            "expires_at": None,
        },
    )
    assert updated.status_code == 200
    assert updated.json()["enabled"] is False
    assert updated.json()["allowed_models"] == ["gpt-4.1"]

    listed = client.get("/api/admin/gateway-api-keys", headers=admin_headers)
    assert listed.status_code == 200
    assert [item["id"] for item in listed.json()] == [key["id"]]

    deleted = client.delete(
        f"/api/admin/gateway-api-keys/{key['id']}", headers=admin_headers
    )
    assert deleted.status_code == 204
    assert client.get("/api/admin/gateway-api-keys", headers=admin_headers).json() == []


def test_gateway_key_enforces_model_identity_and_limits(
    client,
    admin_headers,
    create_site_group_and_key,
    create_model_group,
    create_gateway_key,
    monkeypatch,
) -> None:
    import app.gateway.service.proxy.proxy_upstream as proxy_upstream

    _site, _group, key = create_site_group_and_key(
        model_name="team",
        gateway_overrides={"allowed_models": ["team"], "max_cost_usd": 1},
    )
    create_model_group(
        name="TEAM",
        items=[
            {
                "channel_id": openai_chat_channel_id(),
                "credential_id": "cred-1",
                "model_name": "team",
                "enabled": True,
            }
        ],
    )
    calls = []

    async def send(_client, upstream, **_kwargs):
        calls.append(upstream.url)
        return httpx.Response(
            200,
            request=httpx.Request("POST", upstream.url),
            json={
                "id": "reply",
                "model": "team",
                "choices": [
                    {
                        "index": 0,
                        "message": {"role": "assistant", "content": "ok"},
                        "finish_reason": "stop",
                    }
                ],
                "usage": {
                    "prompt_tokens": 10,
                    "completion_tokens": 1,
                    "total_tokens": 11,
                },
            },
        )

    monkeypatch.setattr(proxy_upstream, "_send_upstream", send)
    headers = gateway_headers(key)
    catalog = client.get("/v1/models", headers=headers)
    assert catalog.status_code == 200
    assert [item["id"] for item in catalog.json()["data"]] == ["team"]
    body = {"model": "TEAM", "messages": [{"role": "user", "content": "hello"}]}
    assert (
        client.post("/v1/chat/completions", headers=headers, json=body).status_code
        == 403
    )
    body["model"] = "team"
    for options in ({"enabled": False}, {"expires_at": "2000-01-01T00:00:00Z"}):
        restricted = create_gateway_key(**options)
        response = client.post(
            "/v1/chat/completions", headers=gateway_headers(restricted), json=body
        )
        assert response.status_code == 401
    assert calls == []
    saved = client.put(
        "/api/admin/model-prices/team",
        headers=admin_headers,
        json={"input_price_per_million": 1_000_000},
    )
    assert saved.status_code == 200
    assert (
        client.post("/v1/chat/completions", headers=headers, json=body).status_code
        == 200
    )
    assert (
        client.post("/v1/chat/completions", headers=headers, json=body).status_code
        == 401
    )
    assert len(calls) == 1
