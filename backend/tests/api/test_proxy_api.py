from __future__ import annotations

import json
from typing import Any

import httpx
import pytest
from conftest import gateway_headers, json_response, valid_site_payload

from app.models.protocols import ProtocolKind


def test_proxy_routes_accept_supported_request_shapes(
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
        request_path: str = "",
    ):
        calls.append(
            {
                "protocol": protocol.value,
                "body": body,
                "gateway_key_id": gateway_key.id,
                "user_agent": user_agent,
                "path_suffix": path_suffix,
                "multipart_files": multipart_files or [],
            }
        )
        return json_response({"ok": True, "protocol": protocol.value})

    import app.gateway.service.proxy_routes as proxy_routes

    monkeypatch.setattr(proxy_routes, "proxy_protocol", fake_proxy)
    headers = {**gateway_headers(key), "User-Agent": "lens-tests"}
    cases = [
        ("/v1/chat/completions", {"model": "gpt-4o"}, "openai_chat"),
        ("/v1/responses", {"model": "gpt-4o", "input": "hello"}, "openai_responses"),
        ("/v1/embeddings", {"model": "text-embedding-3-small"}, "openai_embedding"),
        (
            "/v1/images/generations",
            {"model": "gpt-image-1", "prompt": "test"},
            "openai_image",
        ),
        ("/v1/rerank", {"model": "reranker"}, "rerank"),
        ("/v1/messages", {"model": "claude-3", "messages": []}, "anthropic"),
        (
            "/v1beta/models/gemini-2.5-flash:generateContent",
            {"contents": [{"role": "user", "parts": [{"text": "hello"}]}]},
            "gemini",
        ),
    ]

    for path, body, expected_protocol in cases:
        response = client.post(path, headers=headers, json=body)

        assert response.status_code == 200, response.text
        assert response.json()["protocol"] == expected_protocol
        expected_body = (
            {**body, "model": "gemini-2.5-flash", "stream": False}
            if expected_protocol == "gemini"
            else body
        )
        assert calls[-1]["body"] == expected_body
        assert calls[-1]["gateway_key_id"] == key["id"]
        assert calls[-1]["user_agent"] == "lens-tests"


@pytest.mark.parametrize(
    ("protocol", "base_url", "usage", "input_tokens"),
    [
        (
            "openai_embedding",
            "https://upstream.example/v1",
            {"usage": {"prompt_tokens": 12, "total_tokens": 12}},
            12,
        ),
        ("rerank", "https://upstream.example/v1", {"usage": {"total_tokens": 12}}, 12),
        (
            "rerank",
            "https://upstream.example/v2",
            {"meta": {"billed_units": {"input_tokens": 12}}},
            12,
        ),
        (
            "openai_embedding",
            "https://upstream.example/v1",
            {"usage": {"total_tokens": 12}},
            12,
        ),
        (
            "rerank",
            "https://upstream.example/v1",
            {"meta": {"billed_units": {"search_units": 1}}},
            0,
        ),
    ],
    ids=[
        "embedding",
        "embedding-total-usage",
        "jina-rerank",
        "cohere-v2-rerank",
        "cohere-search-units",
    ],
)
def test_native_embedding_and_rerank_forward_payload_and_record_usage(
    client,
    admin_headers,
    monkeypatch,
    create_site,
    create_model_group,
    create_gateway_key,
    protocol,
    base_url,
    usage,
    input_tokens,
) -> None:
    import app.gateway.service.proxy.proxy_upstream as proxy_upstream

    site = valid_site_payload(protocols=[protocol], model_name="native-model")
    site["base_urls"][0]["url"] = base_url
    create_site(site)
    create_model_group(
        name="public-model",
        items=[
            {
                "channel_id": f"pc-1_{protocol}",
                "credential_id": "cred-1",
                "model_name": "native-model",
                "enabled": True,
            }
        ],
    )
    if protocol == "openai_embedding":
        path = "/v1/embeddings"
        body = {
            "input": ["hello", "world"],
            "encoding_format": "base64",
            "dimensions": 2,
        }
        payload = {
            "object": "list",
            "model": "native-model",
            "data": [{"object": "embedding", "index": 0, "embedding": "AACAPwAAAEA="}],
            **usage,
        }
    else:
        path = "/v1/rerank"
        body = {"query": "hello", "documents": ["world", "hello"], "top_n": 1}
        payload = {"results": [{"index": 1, "relevance_score": 0.95}], **usage}
    sent = []

    async def send(_client, upstream, *, stream, body_bytes):
        assert stream is False
        assert upstream.url == f"{base_url}/{path.rsplit('/', 1)[-1]}"
        assert upstream.headers["authorization"] == "Bearer upstream-secret"
        sent.append(json.loads(body_bytes))
        return httpx.Response(
            200, json=payload, request=httpx.Request("POST", upstream.url)
        )

    monkeypatch.setattr(proxy_upstream, "_send_upstream", send)
    key = create_gateway_key()
    response = client.post(
        path,
        headers=gateway_headers(key),
        json={"model": "public-model", "stream": True, **body},
    )

    assert response.status_code == 200, response.text
    assert response.json() == payload
    assert sent == [{"model": "native-model", **body}]
    logs = client.get("/api/admin/request-logs/page", headers=admin_headers).json()[
        "items"
    ]
    assert logs[0]["success"] is True
    assert (
        logs[0]["input_tokens"],
        logs[0]["output_tokens"],
        logs[0]["total_tokens"],
    ) == (input_tokens, 0, input_tokens)


@pytest.mark.parametrize(
    ("protocol", "path", "body", "first_event"),
    [
        (
            "openai_image",
            "/v1/images/generations",
            {"prompt": "hello"},
            {
                "type": "image_generation.partial_image",
                "b64_json": "YWJj",
                "partial_image_index": 0,
            },
        ),
        (
            "openai_responses",
            "/v1/responses",
            {"input": "hello"},
            {
                "type": "response.output_text.delta",
                "delta": "hello",
                "output_index": 0,
                "content_index": 0,
            },
        ),
    ],
)
def test_native_openai_stream_errors_are_logged_as_failed(
    client,
    admin_headers,
    monkeypatch,
    create_site,
    create_model_group,
    create_gateway_key,
    protocol,
    path,
    body,
    first_event,
) -> None:
    import app.gateway.service.proxy.proxy_upstream as proxy_upstream

    settings = client.put(
        "/api/admin/settings",
        headers=admin_headers,
        json={
            "items": [
                {"key": "circuit_breaker_threshold", "value": "1"},
                {
                    "key": "cooldown_detection_rules",
                    "value": json.dumps(
                        {
                            "rules": [
                                {
                                    "name": "stream provider limit",
                                    "status_code": 200,
                                    "body_regex": "rate_limit_exceeded",
                                    "scope": "channel",
                                    "action": "retry_channel",
                                    "category": "not_found",
                                    "cooldown_seconds": 41,
                                }
                            ]
                        }
                    ),
                },
            ]
        },
    )
    assert settings.status_code == 200, settings.text
    create_site(valid_site_payload(protocols=[protocol], model_name="native-model"))
    create_model_group(
        name="public-model",
        items=[
            {
                "channel_id": f"pc-1_{protocol}",
                "credential_id": "cred-1",
                "model_name": "native-model",
                "enabled": True,
            }
        ],
    )
    error = {
        "type": "error",
        "code": "rate_limit_exceeded",
        "message": "rate limit exceeded",
    }
    content = "".join(
        f"data: {json.dumps(event)}\n\n" for event in [first_event, error]
    )

    async def send(_client, upstream, *, stream, body_bytes):
        return httpx.Response(
            200,
            content=content,
            headers={"content-type": "text/event-stream", "Retry-After": "67"},
            request=httpx.Request("POST", upstream.url),
        )

    monkeypatch.setattr(proxy_upstream, "_send_upstream", send)
    key = create_gateway_key()
    response = client.post(
        path,
        headers=gateway_headers(key),
        json={"model": "public-model", "stream": True, **body},
    )
    assert response.status_code == 200, response.text
    assert "rate limit exceeded" in response.text
    logs = client.get("/api/admin/request-logs/page", headers=admin_headers).json()[
        "items"
    ]
    assert logs[0]["success"] is False
    assert "rate limit exceeded" in logs[0]["error_message"]
    routes = client.get("/api/admin/routes", headers=admin_headers)
    assert routes.status_code == 200, routes.text
    health = routes.json()["health"][0]
    assert health["last_error_category"] == "not_found"
    assert health["last_cooldown_seconds"] == 67
    assert all(item["available"] for item in health["credential_health"])
    assert any(item["model_name"] is None for item in health["model_health"])
