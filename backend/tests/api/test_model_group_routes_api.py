from __future__ import annotations

import json

import httpx
from conftest import gateway_headers, valid_site_payload

from app.core.runtime_channel_ids import compose_runtime_channel_id
from app.models.protocols import ProtocolKind


def test_route_group_uses_execution_group_fallbacks(
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
