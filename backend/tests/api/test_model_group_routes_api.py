from __future__ import annotations

import json
from typing import Any

import httpx
from conftest import assert_error, gateway_headers, valid_site_payload

from app.core.runtime_channel_ids import compose_runtime_channel_id
from app.models.protocols import ProtocolKind


def test_anthropic_route_prefers_native_channel_over_earlier_chat_member(
    client,
    monkeypatch,
    create_site,
    create_model_group,
    create_gateway_key,
) -> None:
    import app.gateway.service.proxy_upstream as proxy_upstream

    create_site(
        valid_site_payload(
            protocols=["openai_chat", "anthropic"],
            model_name="upstream-model",
        )
    )
    create_model_group(
        name="client-model",
        items=[
            {
                "channel_id": compose_runtime_channel_id(
                    "pc-1", ProtocolKind.OPENAI_CHAT
                ),
                "credential_id": "cred-1",
                "model_name": "upstream-model",
                "enabled": True,
            },
            {
                "channel_id": compose_runtime_channel_id(
                    "pc-1", ProtocolKind.ANTHROPIC
                ),
                "credential_id": "cred-1",
                "model_name": "upstream-model",
                "enabled": True,
            },
        ],
    )
    attempted_urls: list[str] = []

    async def fake_send_upstream(
        _client: httpx.AsyncClient,
        upstream: Any,
        *,
        stream: bool,
        body_bytes: bytes,
    ) -> httpx.Response:
        assert not stream
        attempted_urls.append(upstream.url)
        return httpx.Response(
            400,
            json={"error": {"message": "stop after capturing primary"}},
            request=httpx.Request("POST", upstream.url),
        )

    monkeypatch.setattr(proxy_upstream, "_send_upstream", fake_send_upstream)
    key = create_gateway_key()

    response = client.post(
        "/v1/messages",
        headers=gateway_headers(key),
        json={
            "model": "client-model",
            "messages": [{"role": "user", "content": "ping"}],
            "max_tokens": 16,
        },
    )

    assert response.status_code == 400, response.text
    assert len(attempted_urls) == 1
    assert attempted_urls[0].endswith("/v1/messages")


def test_create_route_group_rejects_invalid_route_targets(
    client,
    admin_headers,
    create_model_group,
) -> None:
    target = create_model_group(name="target")
    route = create_model_group(
        name="route",
        route_group_id=target["id"],
    )

    missing = client.post(
        "/api/admin/model-groups",
        headers=admin_headers,
        json={
            "name": "missing-target",
            "route_group_id": "missing",
        },
    )
    missing_protocol = client.post(
        "/api/admin/model-groups",
        headers=admin_headers,
        json={
            "name": "missing-protocol",
            "route_group_id": target["id"],
        },
    )
    chained = client.post(
        "/api/admin/model-groups",
        headers=admin_headers,
        json={
            "name": "chained",
            "route_group_id": route["id"],
        },
    )

    assert_error(missing, 400, "Route target model group not found")
    assert missing_protocol.status_code == 201, missing_protocol.text
    assert_error(chained, 400, "Route target must be an execution group")


def test_update_model_group_rejects_self_route(
    client, admin_headers, create_model_group
) -> None:
    group = create_model_group(name="self-route")

    response = client.put(
        f"/api/admin/model-groups/{group['id']}",
        headers=admin_headers,
        json={"route_group_id": group["id"]},
    )

    assert_error(response, 400, "cannot route to itself")


def test_referenced_execution_group_cannot_become_a_route_group(
    client,
    admin_headers,
    create_model_group,
) -> None:
    execution = create_model_group(name="execution")
    create_model_group(name="route", route_group_id=execution["id"])
    target = create_model_group(name="target")

    response = client.put(
        f"/api/admin/model-groups/{execution['id']}",
        headers=admin_headers,
        json={"route_group_id": target["id"]},
    )

    assert_error(response, 400, "cannot become route groups")


def test_route_group_inherits_execution_group_fallbacks(
    client,
    admin_headers,
    monkeypatch,
    create_site,
    create_model_group,
    create_gateway_key,
) -> None:
    import app.gateway.service.proxy_upstream as proxy_upstream

    create_site(
        valid_site_payload(
            name="Primary",
            base_id="base-primary",
            credential_id="cred-primary",
            protocol_config_id="pc-primary",
            model_name="model-primary",
        )
    )
    create_site(
        valid_site_payload(
            name="Fallback",
            base_id="base-fallback",
            credential_id="cred-fallback",
            protocol_config_id="pc-fallback",
            model_name="model-fallback",
        )
    )
    fallback = create_model_group(
        name="fallback-group",
        items=[
            {
                "channel_id": compose_runtime_channel_id(
                    "pc-fallback", ProtocolKind.OPENAI_CHAT
                ),
                "credential_id": "cred-fallback",
                "model_name": "model-fallback",
                "enabled": True,
            }
        ],
    )
    primary = create_model_group(
        name="primary-group",
        items=[
            {
                "channel_id": compose_runtime_channel_id(
                    "pc-primary", ProtocolKind.OPENAI_CHAT
                ),
                "credential_id": "cred-primary",
                "model_name": "model-primary",
                "enabled": True,
            }
        ],
    )
    updated = client.put(
        f"/api/admin/model-groups/{primary['id']}",
        headers=admin_headers,
        json={"fallback_group_ids": [fallback["id"]]},
    )
    assert updated.status_code == 200, updated.text
    create_model_group(name="alias", route_group_id=primary["id"])

    sent: list[str] = []

    async def fake_send(_client, upstream, *, stream, body_bytes):
        assert not stream
        model = json.loads(body_bytes)["model"]
        sent.append(model)
        if model == "model-primary":
            return httpx.Response(
                500,
                json={"error": {"message": "primary failed"}},
                request=httpx.Request("POST", upstream.url),
            )
        return httpx.Response(
            200,
            json={
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

    monkeypatch.setattr(proxy_upstream, "_send_upstream", fake_send)
    response = client.post(
        "/v1/chat/completions",
        headers=gateway_headers(create_gateway_key()),
        json={
            "model": "alias",
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "describe"},
                        {
                            "type": "image_url",
                            "image_url": {"url": "https://example.invalid/image.png"},
                        },
                    ],
                }
            ],
        },
    )

    assert response.status_code == 200, response.text
    assert sent == ["model-primary", "model-fallback"]


def test_delete_model_group_rejects_referenced_execution_group(
    client,
    admin_headers,
    create_model_group,
) -> None:
    execution_group = create_model_group(name="gpt-4o")
    create_model_group(
        name="public-gpt-4o",
        route_group_id=execution_group["id"],
    )

    response = client.delete(
        f"/api/admin/model-groups/{execution_group['id']}",
        headers=admin_headers,
    )

    assert_error(response, 400, "still referenced")
