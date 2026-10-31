from __future__ import annotations

import json
from typing import Any

import httpx
from conftest import gateway_headers, valid_site_payload

from app.core.runtime_channel_ids import compose_runtime_channel_id
from app.models.protocols import ProtocolKind


def _two_credential_site_payload() -> dict[str, Any]:
    payload = valid_site_payload(
        name="Multi-key",
        credential_id="cred-primary",
        model_name="shared-model",
    )
    payload["credentials"].append(
        {
            "id": "cred-secondary",
            "name": "secondary-key",
            "api_key": "{{SECRET_secondary_1234}}",
        }
    )
    payload["protocols"][0]["models"].append(
        {
            "credential_id": "cred-secondary",
            "model_name": "shared-model",
            "enabled": True,
            "protocol": ProtocolKind.OPENAI_CHAT.value,
        }
    )
    return payload


def test_route_group_uses_execution_group_fallbacks(
    client,
    admin_headers,
    monkeypatch,
    create_site,
    create_model_group,
    create_gateway_key,
) -> None:
    import app.gateway.service.proxy.proxy_upstream as proxy_upstream

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


def test_rate_limit_retries_a_sibling_credential(
    client,
    monkeypatch,
    create_site,
    create_model_group,
    create_gateway_key,
) -> None:
    import app.gateway.service.proxy.proxy_upstream as proxy_upstream

    create_site(_two_credential_site_payload())
    channel_id = compose_runtime_channel_id("pc-1", ProtocolKind.OPENAI_CHAT)
    create_model_group(
        name="shared-model",
        items=[
            {
                "channel_id": channel_id,
                "credential_id": credential_id,
                "model_name": "shared-model",
                "enabled": True,
            }
            for credential_id in ("cred-primary", "cred-secondary")
        ],
    )
    seen_credentials: list[str] = []

    async def fake_send(_client, upstream, *, stream, body_bytes):
        assert not stream
        seen_credentials.append(upstream.headers["authorization"])
        request = httpx.Request("POST", upstream.url)
        if len(seen_credentials) == 1:
            return httpx.Response(
                429, json={"error": {"message": "rate limited"}}, request=request
            )
        return httpx.Response(
            200,
            json={
                "model": "shared-model",
                "choices": [
                    {
                        "index": 0,
                        "message": {"role": "assistant", "content": "ok"},
                        "finish_reason": "stop",
                    }
                ],
            },
            request=request,
        )

    monkeypatch.setattr(proxy_upstream, "_send_upstream", fake_send)
    response = client.post(
        "/v1/chat/completions",
        headers=gateway_headers(create_gateway_key()),
        json={"model": "shared-model", "messages": [{"role": "user", "content": "hi"}]},
    )

    assert response.status_code == 200, response.text
    assert len(seen_credentials) == 2
    assert seen_credentials[0] != seen_credentials[1]


def test_request_error_does_not_retry_another_target(
    client,
    monkeypatch,
    create_site,
    create_model_group,
    create_gateway_key,
) -> None:
    import app.gateway.service.proxy.proxy_upstream as proxy_upstream

    create_site(_two_credential_site_payload())
    channel_id = compose_runtime_channel_id("pc-1", ProtocolKind.OPENAI_CHAT)
    create_model_group(
        name="terminal-model",
        items=[
            {
                "channel_id": channel_id,
                "credential_id": credential_id,
                "model_name": "shared-model",
                "enabled": True,
            }
            for credential_id in ("cred-primary", "cred-secondary")
        ],
    )
    attempts = 0

    async def fake_send(_client, upstream, *, stream, body_bytes):
        nonlocal attempts
        assert not stream
        attempts += 1
        return httpx.Response(
            400,
            json={"error": {"message": "invalid request"}},
            request=httpx.Request("POST", upstream.url),
        )

    monkeypatch.setattr(proxy_upstream, "_send_upstream", fake_send)
    response = client.post(
        "/v1/chat/completions",
        headers=gateway_headers(create_gateway_key()),
        json={
            "model": "terminal-model",
            "messages": [{"role": "user", "content": "hi"}],
        },
    )

    assert response.status_code == 400, response.text
    assert attempts == 1


def test_cooldown_skips_target_on_the_next_request(
    client,
    monkeypatch,
    create_site,
    create_model_group,
    create_gateway_key,
) -> None:
    import app.gateway.service.proxy.proxy_upstream as proxy_upstream

    create_site(
        valid_site_payload(
            model_name="cooldown-model",
            credential_id="cred-cooldown",
        )
    )
    create_model_group(
        name="cooldown-model",
        items=[
            {
                "channel_id": compose_runtime_channel_id(
                    "pc-1", ProtocolKind.OPENAI_CHAT
                ),
                "credential_id": "cred-cooldown",
                "model_name": "cooldown-model",
                "enabled": True,
            }
        ],
    )
    attempts = 0

    async def fake_send(_client, upstream, *, stream, body_bytes):
        nonlocal attempts
        attempts += 1
        return httpx.Response(
            429,
            json={"error": {"message": "rate limited"}},
            request=httpx.Request("POST", upstream.url),
        )

    monkeypatch.setattr(proxy_upstream, "_send_upstream", fake_send)
    headers = gateway_headers(create_gateway_key())
    body = {"model": "cooldown-model", "messages": [{"role": "user", "content": "hi"}]}
    first = client.post("/v1/chat/completions", headers=headers, json=body)
    second = client.post("/v1/chat/completions", headers=headers, json=body)

    assert first.status_code == 429, first.text
    assert second.status_code == 503, second.text
    assert "in cooldown" in second.text
    assert attempts == 1
