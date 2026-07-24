from __future__ import annotations

import json
from typing import Any

import httpx
import pytest
from conftest import (
    gateway_headers,
    json_response,
    run_async,
    valid_site_payload,
)
from fastapi.responses import JSONResponse

from lens_api.core.runtime_channel_ids import compose_runtime_channel_id
from lens_api.models import ProtocolKind
from lens_api.persistence.entities import GatewayApiKeyEntity


def _protocol_group_item(protocol: str, model_name: str) -> dict[str, Any]:
    return {
        "channel_id": compose_runtime_channel_id("pc-1", ProtocolKind(protocol)),
        "credential_id": "cred-1",
        "model_name": model_name,
        "enabled": True,
    }


async def _set_gateway_spend(app_state: Any, key_id: str, spent: float) -> None:
    async with app_state.session_factory() as session:
        entity = await session.get(GatewayApiKeyEntity, key_id)
        assert entity is not None
        entity.spent_cost_usd = spent
        await session.commit()


@pytest.mark.parametrize(
    ("path", "body", "expected"),
    [
        (
            "/v1/chat/completions",
            {"model": "gpt-4o"},
            {
                "error": {
                    "message": "Missing gateway API key",
                    "type": "unauthorized",
                    "param": None,
                    "code": None,
                }
            },
        ),
        (
            "/v1/messages",
            {"model": "claude-3"},
            {
                "type": "error",
                "error": {
                    "type": "authentication_error",
                    "message": "Missing gateway API key",
                },
            },
        ),
        (
            "/v1beta/models/gemini-2.5-flash:generateContent",
            {"contents": []},
            {
                "error": {
                    "code": 401,
                    "message": "Missing gateway API key",
                    "status": "UNAUTHENTICATED",
                }
            },
        ),
    ],
)
def test_proxy_uses_protocol_error_format_for_missing_gateway_key(
    client,
    path: str,
    body: dict[str, Any],
    expected: dict[str, Any],
) -> None:
    response = client.post(path, json=body)

    assert response.status_code == 401
    assert response.json() == expected


def test_gateway_key_auth_accepts_x_api_key_header(
    client,
    create_site_group_and_key,
) -> None:
    _site, _group, key = create_site_group_and_key()

    response = client.get("/v1/models", headers={"x-api-key": key["api_key"]})

    assert response.status_code == 200
    assert response.json()["data"][0]["id"] == "gpt-4o"


def test_gateway_key_auth_accepts_x_goog_api_key_header(
    client,
    create_site,
    create_model_group,
    create_gateway_key,
) -> None:
    create_site(valid_site_payload(protocols=["gemini"], model_name="gemini-pro"))
    create_model_group(
        name="gemini-pro",
        protocols=["gemini"],
        items=[_protocol_group_item("gemini", "gemini-pro")],
    )
    key = create_gateway_key()

    response = client.get("/v1beta/models", headers={"x-goog-api-key": key["api_key"]})

    assert response.status_code == 200
    assert response.json()["models"][0]["name"] == "models/gemini-pro"


def test_gateway_key_auth_rejects_invalid_disabled_expired_and_spent_keys(
    client,
    app_state,
    create_gateway_key,
) -> None:
    invalid = client.get("/v1/models", headers={"x-api-key": "missing"})
    disabled_key = create_gateway_key(enabled=False)
    disabled = client.get("/v1/models", headers=gateway_headers(disabled_key))
    expired_key = create_gateway_key(expires_at="2000-01-01T00:00:00Z")
    expired = client.get("/v1/models", headers=gateway_headers(expired_key))
    spent_key = create_gateway_key(max_cost_usd=1)
    run_async(_set_gateway_spend(app_state, spent_key["id"], 1))
    spent = client.get("/v1/models", headers=gateway_headers(spent_key))

    assert invalid.status_code == 401
    assert invalid.json()["error"]["message"] == "Invalid gateway API key"
    assert disabled.json()["error"]["message"] == "Gateway API key is disabled"
    assert expired.json()["error"]["message"] == "Gateway API key has expired"
    assert spent.json()["error"]["message"] == (
        "Gateway API key has reached the max balance"
    )


def test_proxy_json_endpoints_forward_expected_protocol_and_body(
    client,
    monkeypatch,
    create_gateway_key,
) -> None:
    key = create_gateway_key()
    calls: list[dict[str, Any]] = []

    async def fake_proxy(
        protocol: ProtocolKind,
        body: dict[str, Any],
        gateway_key: Any,
        user_agent: str | None,
        forwarded_headers: dict[str, str] | None = None,
        *,
        path_suffix: str = "",
        multipart_files: list[Any] | None = None,
    ) -> JSONResponse:
        calls.append(
            {
                "protocol": protocol.value,
                "body": body,
                "gateway_key_id": gateway_key.id,
                "user_agent": user_agent,
                "forwarded_headers": forwarded_headers or {},
                "path_suffix": path_suffix,
                "multipart_files": multipart_files or [],
            }
        )
        return json_response({"ok": True, "protocol": protocol.value})

    from lens_api.gateway.service import proxy_routes

    monkeypatch.setattr(proxy_routes, "_proxy_protocol", fake_proxy)
    headers = {**gateway_headers(key), "User-Agent": "lens-tests"}

    cases = [
        (
            "post",
            "/v1/chat/completions",
            {"model": "gpt-4o", "stream": True},
            "openai_chat",
            {"model": "gpt-4o", "stream": True},
        ),
        (
            "post",
            "/v1/responses",
            {"model": "gpt-4o", "input": "hello"},
            "openai_responses",
            {"model": "gpt-4o", "input": "hello"},
        ),
        (
            "post",
            "/v1/embeddings",
            {"model": "text-embedding-3-small", "stream": True},
            "openai_embedding",
            {"model": "text-embedding-3-small"},
        ),
        (
            "post",
            "/v1/rerank",
            {"model": "reranker", "stream": True},
            "rerank",
            {"model": "reranker"},
        ),
        (
            "post",
            "/v1/images/generations",
            {"model": "gpt-image-1", "prompt": "test"},
            "openai_image",
            {"model": "gpt-image-1", "prompt": "test"},
        ),
        (
            "post",
            "/v1/messages",
            {"model": "claude-3", "messages": []},
            "anthropic",
            {"model": "claude-3", "messages": []},
        ),
        (
            "post",
            "/v1beta/models/gemini-2.5-flash:generateContent",
            {"contents": []},
            "gemini",
            {"contents": [], "model": "gemini-2.5-flash", "stream": False},
        ),
        (
            "post",
            "/v1beta/models/gemini-2.5-flash:streamGenerateContent",
            {"contents": []},
            "gemini",
            {"contents": [], "model": "gemini-2.5-flash", "stream": True},
        ),
    ]

    for _method, path, body, expected_protocol, expected_body in cases:
        response = client.post(path, headers=headers, json=body)
        assert response.status_code == 200, response.text
        assert response.json()["protocol"] == expected_protocol
        assert calls[-1]["body"] == expected_body
        assert calls[-1]["gateway_key_id"] == key["id"]
        assert calls[-1]["user_agent"] == "lens-tests"

    image_call = next(item for item in calls if item["protocol"] == "openai_image")
    assert image_call["path_suffix"] == "images/generations"


def test_responses_proxy_preserves_input_shape(
    client,
    monkeypatch,
    create_site,
    create_model_group,
    create_gateway_key,
) -> None:
    from lens_api.gateway.service import proxy_upstream

    captured_bodies: list[dict[str, Any]] = []

    async def fake_send_upstream(
        _client: httpx.AsyncClient,
        upstream: Any,
        *,
        stream: bool,
        body_bytes: bytes,
    ) -> httpx.Response:
        assert not stream
        captured_bodies.append(json.loads(body_bytes))
        return httpx.Response(
            200,
            json={
                "id": "resp_1",
                "object": "response",
                "model": "gpt-5.6-sol",
                "output": [],
                "usage": {
                    "input_tokens": 1,
                    "output_tokens": 1,
                    "total_tokens": 2,
                },
            },
            request=httpx.Request("POST", upstream.url),
        )

    monkeypatch.setattr(proxy_upstream, "_send_upstream", fake_send_upstream)
    create_site(
        valid_site_payload(
            protocols=[ProtocolKind.OPENAI_RESPONSES.value],
            model_name="gpt-5.6-sol",
        )
    )
    create_model_group(
        name="response-model",
        protocols=[ProtocolKind.OPENAI_RESPONSES.value],
        items=[
            {
                "channel_id": compose_runtime_channel_id(
                    "pc-1", ProtocolKind.OPENAI_RESPONSES
                ),
                "credential_id": "cred-1",
                "model_name": "gpt-5.6-sol",
                "enabled": True,
            }
        ],
    )
    key = create_gateway_key()
    input_items = [
        {"role": "user", "content": "Use the lookup tool."},
        {
            "type": "function_call",
            "call_id": "call_1",
            "name": "lookup",
            "arguments": '{"query":"lens"}',
        },
        {"role": "assistant", "content": ""},
        {
            "type": "function_call_output",
            "call_id": "call_1",
            "output": "result",
        },
    ]
    request_bodies = [
        {"model": "response-model", "input": "  Keep surrounding whitespace.  "},
        {"model": "response-model", "input": input_items},
    ]

    for body in request_bodies:
        response = client.post(
            "/v1/responses",
            headers=gateway_headers(key),
            json=body,
        )
        assert response.status_code == 200, response.text

    assert captured_bodies == [
        {"model": "gpt-5.6-sol", "input": body["input"]} for body in request_bodies
    ]
