from __future__ import annotations

import json
from typing import Any

import httpx
from conftest import (
    assert_error,
    gateway_headers,
    openai_chat_channel_id,
    valid_site_payload,
)

REVERSE_PLUGIN = """
from app.plugins.contract import (
    EXT_ROUTE_STRATEGY,
    PluginContext,
    PluginDefinition,
    PluginManifest,
)


class Reversed:
    name = "reversed"

    def extension(self) -> str:
        return EXT_ROUTE_STRATEGY

    def order(self, pool, seats):
        return list(reversed(range(len(seats))))


def register(context: PluginContext) -> None:
    context.add_route_strategy(Reversed())


PLUGIN = PluginDefinition(
    manifest=PluginManifest(id="spread_plugin", name="Spread"),
    register=register,
)
"""


def test_model_group_plugin_strategy_round_trip(client, admin_headers) -> None:
    created = client.post(
        "/api/admin/model-groups",
        headers=admin_headers,
        json={"name": "spread-group", "strategy": "demo_plugin/spread", "items": []},
    )
    assert created.status_code == 201, created.text
    assert created.json()["strategy"] == "demo_plugin/spread"
    group_id = created.json()["id"]

    fetched = client.get(f"/api/admin/model-groups/{group_id}", headers=admin_headers)
    assert fetched.status_code == 200
    assert fetched.json()["strategy"] == "demo_plugin/spread"

    updated = client.put(
        f"/api/admin/model-groups/{group_id}",
        headers=admin_headers,
        json={"strategy": "round_robin"},
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["strategy"] == "round_robin"

    rejected = client.put(
        f"/api/admin/model-groups/{group_id}",
        headers=admin_headers,
        json={"strategy": "Demo Plugin/spread"},
    )
    assert_error(rejected, 422)


def test_plugin_strategy_orders_group_members(
    client,
    admin_headers,
    monkeypatch,
    install_plugin,
    create_site,
    create_gateway_key,
) -> None:
    import app.gateway.service.proxy_upstream as proxy_upstream

    upstream_models: list[str] = []

    async def fake_send_upstream(
        _client: httpx.AsyncClient,
        upstream: Any,
        *,
        stream: bool,
        body_bytes: bytes,
    ) -> httpx.Response:
        model = json.loads(body_bytes)["model"]
        upstream_models.append(model)
        return httpx.Response(
            200,
            json={
                "id": "chatcmpl-1",
                "object": "chat.completion",
                "created": 1,
                "model": model,
                "choices": [
                    {
                        "index": 0,
                        "message": {"role": "assistant", "content": "ok"},
                        "finish_reason": "stop",
                    }
                ],
                "usage": {
                    "prompt_tokens": 1,
                    "completion_tokens": 1,
                    "total_tokens": 2,
                },
            },
            request=httpx.Request("POST", upstream.url),
        )

    monkeypatch.setattr(proxy_upstream, "_send_upstream", fake_send_upstream)
    plugin = install_plugin(REVERSE_PLUGIN, "spread_plugin")
    assert plugin["strategies"] == ["spread_plugin/reversed"]
    site_payload = valid_site_payload(model_name="model-a")
    site_payload["protocols"][0]["models"].append(
        {
            "credential_id": "cred-1",
            "model_name": "model-b",
            "enabled": True,
            "protocol": "openai_chat",
        }
    )
    create_site(site_payload)
    group = client.post(
        "/api/admin/model-groups",
        headers=admin_headers,
        json={
            "name": "spread-group",
            "strategy": "spread_plugin/reversed",
            "items": [
                {
                    "channel_id": openai_chat_channel_id(),
                    "credential_id": "cred-1",
                    "model_name": model_name,
                    "enabled": True,
                }
                for model_name in ("model-a", "model-b")
            ],
        },
    )
    assert group.status_code == 201, group.text
    headers = gateway_headers(create_gateway_key())
    request = {"model": "spread-group", "messages": [{"role": "user", "content": "hi"}]}

    reordered = client.post("/v1/chat/completions", headers=headers, json=request)
    assert reordered.status_code == 200, reordered.text

    # 插件停用后策略不再被提供，模型组按列出的顺序。
    disabled = client.put(
        "/api/admin/plugins/spread_plugin",
        headers=admin_headers,
        json={"enabled": False},
    )
    assert disabled.status_code == 200, disabled.text
    listed = client.post("/v1/chat/completions", headers=headers, json=request)
    assert listed.status_code == 200, listed.text

    assert upstream_models == ["model-b", "model-a"]
