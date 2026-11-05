from __future__ import annotations

import json
from collections import Counter
from typing import Any

import httpx
import pytest
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


@pytest.mark.parametrize("endpoint_mode", ["default", "china", "dedicated", "owned"])
def test_model_requests_follow_endpoint_priority_and_key_binding(
    client,
    admin_headers,
    monkeypatch,
    create_site,
    create_gateway_key,
    endpoint_mode,
) -> None:
    import app.gateway.service.proxy.proxy_upstream as proxy_upstream

    payload = _two_credential_site_payload()
    payload["base_urls"][0]["url"] = "https://main.example"
    for credential in payload["credentials"]:
        payload["protocols"][0]["models"].extend(
            [
                {
                    "credential_id": credential["id"],
                    "model_name": "shared-model",
                    "protocol": "anthropic",
                },
                {
                    "credential_id": credential["id"],
                    "model_name": f"only-{credential['id']}",
                    "protocol": "openai_chat",
                },
            ]
        )
    if endpoint_mode != "default":
        payload["base_urls"].append(
            {"id": "china", "kind": "china", "url": "https://china.example"}
        )
        payload["protocols"].append(
            {"id": "pc-china", "base_url_id": "china", "protocols": ["openai_chat"]}
        )
    if endpoint_mode in {"dedicated", "owned"}:
        payload["base_urls"].append(
            {"id": "claude", "kind": "anthropic", "url": "https://claude.example"}
        )
        payload["protocols"].append(
            {"id": "pc-claude", "base_url_id": "claude", "protocols": ["anthropic"]}
        )
    if endpoint_mode == "owned":
        payload["credentials"].append(
            {
                "id": "cred-owned",
                "name": "owned-key",
                "api_key": "test-owned",
                "base_url_id": "claude",
            }
        )
        payload["protocols"][-1]["models"] = [
            {
                "credential_id": "cred-owned",
                "model_name": "shared-model",
                "protocol": "anthropic",
            }
        ]
    site = create_site(payload)
    assert {
        (model["credential_id"], model["model_name"])
        for config in site["protocols"]
        for model in config["models"]
    } >= {
        ("cred-primary", "shared-model"),
        ("cred-secondary", "shared-model"),
        ("cred-primary", "only-cred-primary"),
        ("cred-secondary", "only-cred-secondary"),
    }
    group = next(
        group
        for group in client.get("/api/admin/model-groups", headers=admin_headers).json()
        if group["name"] == "shared-model"
    )
    response = client.put(
        f"/api/admin/model-groups/{group['id']}",
        headers=admin_headers,
        json={"strategy": "round_robin"},
    )
    assert response.status_code == 200, response.text
    seen: list[tuple[str, str, str]] = []

    async def fake_send(_client, upstream, *, stream, body_bytes):
        url = httpx.URL(upstream.url)
        credential = (
            upstream.headers.get("authorization") or upstream.headers["x-api-key"]
        )
        seen.append((url.host, url.path, credential.removeprefix("Bearer ")))
        body = (
            {
                "id": "msg-test",
                "type": "message",
                "role": "assistant",
                "model": "shared-model",
                "content": [{"type": "text", "text": "ok"}],
                "stop_reason": "end_turn",
                "usage": {"input_tokens": 1, "output_tokens": 1},
            }
            if url.path.endswith("/messages")
            else {
                "id": "chat-test",
                "model": "shared-model",
                "choices": [
                    {
                        "index": 0,
                        "message": {"role": "assistant", "content": "ok"},
                        "finish_reason": "stop",
                    }
                ],
            }
        )
        return httpx.Response(
            200, json=body, request=httpx.Request("POST", upstream.url)
        )

    monkeypatch.setattr(proxy_upstream, "_send_upstream", fake_send)
    headers = gateway_headers(create_gateway_key())
    for path in ("chat/completions", "messages"):
        seen.clear()
        for _ in range(4):
            response = client.post(
                f"/v1/{path}",
                headers=headers,
                json={
                    "model": "shared-model",
                    "messages": [{"role": "user", "content": "hi"}],
                    "max_tokens": 16,
                },
            )
            assert response.status_code == 200, response.text
        expected_host = (
            "claude.example"
            if path == "messages" and endpoint_mode in {"dedicated", "owned"}
            else "main.example"
            if endpoint_mode == "default"
            else "china.example"
        )
        assert {(host, sent_path) for host, sent_path, _ in seen} == {
            (expected_host, f"/v1/{path}")
        }
        counts = Counter(credential for _, _, credential in seen)
        if path == "messages" and endpoint_mode == "owned":
            assert counts == {"test-owned": 4}
        else:
            assert counts == {
                payload["credentials"][0]["api_key"]: 2,
                payload["credentials"][1]["api_key"]: 2,
            }
    for credential in payload["credentials"][:2]:
        seen.clear()
        response = client.post(
            "/v1/chat/completions",
            headers=headers,
            json={
                "model": f"only-{credential['id']}",
                "messages": [{"role": "user", "content": "hi"}],
            },
        )
        assert response.status_code == 200, response.text
        assert [key for _, _, key in seen] == [credential["api_key"]]


def test_round_robin_counts_keys_once_and_keeps_protocol_fallbacks(
    client,
    admin_headers,
    monkeypatch,
    create_site,
    create_gateway_key,
) -> None:
    import app.gateway.service.proxy.proxy_upstream as proxy_upstream

    payload = _two_credential_site_payload()
    payload["protocols"][0]["models"].append(
        {
            "credential_id": "cred-primary",
            "model_name": "shared-model",
            "protocol": "anthropic",
        }
    )
    for credential in payload["credentials"]:
        credential["base_url_id"] = "china"
    payload["credentials"].append(
        {"id": "cred-fallback", "name": "fallback-key", "api_key": "fallback-secret"}
    )
    payload["base_urls"].append(
        {"id": "china", "kind": "china", "url": "https://china.example/v1"}
    )
    payload["protocols"].append(
        {
            "id": "pc-china",
            "base_url_id": "china",
            "models": payload["protocols"][0]["models"],
        }
    )
    payload["protocols"][0]["models"] = [
        {
            "credential_id": "cred-fallback",
            "model_name": "shared-model",
            "protocol": "openai_chat",
        }
    ]
    create_site(payload)
    group = next(
        item
        for item in client.get("/api/admin/model-groups", headers=admin_headers).json()
        if item["name"] == "shared-model"
    )
    response = client.put(
        f"/api/admin/model-groups/{group['id']}",
        headers=admin_headers,
        json={"strategy": "round_robin"},
    )
    assert response.status_code == 200, response.text
    seen: list[tuple[str, str, str]] = []
    failures_left = 0

    async def fake_send(_client, upstream, *, stream, body_bytes):
        nonlocal failures_left
        assert not stream
        url = httpx.URL(upstream.url)
        credential = (
            upstream.headers.get("authorization") or upstream.headers["x-api-key"]
        )
        seen.append((credential, url.host, url.path))
        request = httpx.Request("POST", upstream.url)
        if failures_left:
            failures_left -= 1
            return httpx.Response(
                500, json={"error": {"message": "failed"}}, request=request
            )
        body = (
            {
                "id": "msg-test",
                "type": "message",
                "role": "assistant",
                "model": "shared-model",
                "content": [{"type": "text", "text": "ok"}],
                "stop_reason": "end_turn",
                "usage": {"input_tokens": 1, "output_tokens": 1},
            }
            if url.path.endswith("/messages")
            else {
                "id": "chat-test",
                "model": "shared-model",
                "choices": [
                    {
                        "index": 0,
                        "message": {"role": "assistant", "content": "ok"},
                        "finish_reason": "stop",
                    }
                ],
            }
        )
        return httpx.Response(200, json=body, request=request)

    monkeypatch.setattr(proxy_upstream, "_send_upstream", fake_send)
    headers = gateway_headers(create_gateway_key())
    body = {"model": "shared-model", "input": "hi"}
    for _ in range(8):
        response = client.post("/v1/responses", headers=headers, json=body)
        assert response.status_code == 200, response.text
    assert sorted(
        Counter(
            credential.removeprefix("Bearer ") for credential, _, _ in seen
        ).values()
    ) == [4, 4]
    assert {host for _, host, _ in seen} == {"china.example"}

    response = client.get(
        f"/api/admin/model-groups/{group['id']}", headers=admin_headers
    )
    items = [
        {
            "channel_id": item["channel_id"],
            "credential_id": item["credential_id"],
            "model_name": item["model_name"],
            "enabled": item["credential_id"] != "cred-secondary",
        }
        for item in response.json()["items"]
    ]
    response = client.put(
        f"/api/admin/model-groups/{group['id']}",
        headers=admin_headers,
        json={"items": items},
    )
    assert response.status_code == 200, response.text
    seen.clear()
    failures_left = 2
    response = client.post("/v1/responses", headers=headers, json=body)
    assert response.status_code == 200, response.text
    assert len(seen) == 3
    assert {path for _, _, path in seen[:2]} == {"/v1/chat/completions", "/v1/messages"}
    assert [host for _, host, _ in seen] == [
        "china.example",
        "china.example",
        "upstream.example",
    ]


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
