from __future__ import annotations

import asyncio
import json
from concurrent.futures import ThreadPoolExecutor
from threading import Event
from time import sleep
from typing import Any

import httpx
import pytest
from conftest import gateway_headers, json_response, valid_site_payload

from app.models.protocols import ProtocolKind


@pytest.mark.parametrize("protocol", ["openai_chat", "openai_responses", "anthropic"])
def test_proxy_preserves_client_identity_and_uses_upstream_credentials(
    client,
    admin_headers,
    monkeypatch,
    create_site,
    create_model_group,
    create_gateway_key,
    protocol,
) -> None:
    import app.gateway.service.proxy.proxy_upstream as proxy_upstream

    identity_headers = {
        "accept": "application/json, text/event-stream",
        "x-client-request-id": "client-request",
    }
    if protocol == "anthropic":
        identity_headers.update(
            {
                "user-agent": "claude-cli/2.1.90 (external, cli)",
                "anthropic-version": "2023-06-01",
                "anthropic-beta": "claude-code-20250219",
                "x-app": "cli",
                "x-stainless-lang": "js",
                "x-stainless-helper-method": "stream",
                "x-claude-code-session-id": "claude-session",
            }
        )
        path = "/v1/messages"
        body = {
            "messages": [{"role": "user", "content": "hello"}],
            "system": [
                {
                    "type": "text",
                    "text": "You are Claude Code, Anthropic's official CLI for Claude.",
                }
            ],
            "metadata": {
                "user_id": '{"device_id":"device","account_uuid":"","session_id":"session"}'
            },
            "max_tokens": 64,
        }
        payload = {
            "id": "msg_test",
            "type": "message",
            "role": "assistant",
            "content": [{"type": "text", "text": "hello"}],
            "stop_reason": "end_turn",
            "usage": {"input_tokens": 1, "output_tokens": 1},
        }
    else:
        identity_headers.update(
            {
                "user-agent": "codex_cli_rs/0.159.0",
                "originator": "codex_cli_rs",
                "version": "0.159.0",
                "openai-beta": "responses=experimental",
                "session_id": "codex-session",
                "conversation_id": "codex-conversation",
                "x-codex-window-id": "codex-window",
                "x-codex-turn-state": "codex-turn",
                "x-openai-responses-lite": "true",
            }
        )
        if protocol == "openai_responses":
            path = "/v1/responses"
            body = {
                "input": "hello",
                "store": False,
                "client_metadata": {"x-codex-window-id": "codex-window"},
            }
            payload = {
                "id": "resp_test",
                "status": "completed",
                "output": [
                    {
                        "type": "message",
                        "role": "assistant",
                        "content": [{"type": "output_text", "text": "hello"}],
                    }
                ],
                "usage": {"input_tokens": 1, "output_tokens": 1},
            }
        else:
            path = "/v1/chat/completions"
            body = {"messages": [{"role": "user", "content": "hello"}]}
            payload = {
                "choices": [{"message": {"role": "assistant", "content": "hello"}}],
                "usage": {"prompt_tokens": 1, "completion_tokens": 1},
            }

    site = valid_site_payload(protocols=[protocol], model_name="native-model")
    site["headers"] = [
        {"name": "Accept-Language", "action": "override", "value": "zh-CN"}
    ]
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
    sent = []

    async def send(_client, upstream, *, stream, body_bytes):
        headers = httpx.Headers(upstream.headers)
        assert all(
            headers.get(name) == value for name, value in identity_headers.items()
        )
        assert headers["accept-language"] == "zh-CN"
        assert headers["content-type"] == "application/json"
        assert (
            not {
                "cookie",
                "host",
                "connection",
                "x-unrelated",
                "x-goog-api-key",
                "x-codex-hop",
                "x-claude-code-hop",
            }
            & headers.keys()
        )
        if protocol == "anthropic":
            assert headers["x-api-key"] == "upstream-secret"
            assert "authorization" not in headers
        else:
            assert headers["authorization"] == "Bearer upstream-secret"
            assert "x-api-key" not in headers
        sent.append(json.loads(body_bytes))
        return httpx.Response(
            200,
            json=payload,
            headers={
                "request-id": "upstream-request",
                "x-codex-turn-state": "next-turn",
            },
            request=httpx.Request("POST", upstream.url),
        )

    monkeypatch.setattr(proxy_upstream, "_send_upstream", send)
    response = client.post(
        path,
        headers={
            **gateway_headers(create_gateway_key()),
            **identity_headers,
            "accept-language": "en-US",
            "x-api-key": "client-secret",
            "x-goog-api-key": "client-secret",
            "cookie": "session=private",
            "x-unrelated": "private",
            "connection": "x-codex-hop, x-claude-code-hop",
            "x-codex-hop": "private",
            "x-claude-code-hop": "private",
        },
        json={"model": "public-model", **body},
    )

    assert response.status_code == 200, response.text
    assert sent == [{"model": "native-model", **body}]
    assert response.headers["request-id"] == "upstream-request"
    assert response.headers["x-codex-turn-state"] == "next-turn"


@pytest.mark.parametrize(
    ("failure", "status"), [("interrupted", 502), ("timeout", 504)]
)
def test_failed_stream_closes_upstream_and_finalizes_logs(
    client,
    admin_headers,
    monkeypatch,
    create_site_group_and_key,
    failure,
    status,
) -> None:
    import app.gateway.service.proxy.proxy_upstream as proxy_upstream

    _, _, key = create_site_group_and_key()
    settings = client.put(
        "/api/admin/settings",
        headers=admin_headers,
        json={"items": [{"key": "stream_idle_timeout_seconds", "value": "0.1"}]},
    )
    assert settings.status_code == 200, settings.text

    class BrokenStream(httpx.AsyncByteStream):
        is_closed = False

        async def __aiter__(self):
            yield b'data: {"choices":[{"index":0,"delta":{"content":"hello"}}]}\n\n'
            if failure == "timeout":
                await asyncio.Event().wait()
            raise httpx.ReadError("upstream connection interrupted")

        async def aclose(self):
            self.is_closed = True

    upstream_stream = BrokenStream()

    async def send(_client, upstream, *, stream, body_bytes):
        return httpx.Response(
            200,
            stream=upstream_stream,
            headers={"content-type": "text/event-stream"},
            request=httpx.Request("POST", upstream.url),
        )

    monkeypatch.setattr(proxy_upstream, "_send_upstream", send)
    response = client.post(
        "/v1/chat/completions",
        headers=gateway_headers(key),
        json={
            "model": "gpt-4o",
            "stream": True,
            "messages": [{"role": "user", "content": "hello"}],
        },
    )
    assert response.status_code == 200, response.text
    assert '"error"' in response.text
    assert upstream_stream.is_closed
    logs = client.get("/api/admin/request-logs/page", headers=admin_headers).json()[
        "items"
    ]
    log = client.get(
        f"/api/admin/request-logs/{logs[0]['id']}", headers=admin_headers
    ).json()
    assert log["lifecycle_status"] == "failed"
    assert log["status_code"] == status
    assert log["attempts"][-1]["success"] is False


def test_upstream_retry_after_and_single_recovery_probe(
    client, admin_headers, monkeypatch, create_site_group_and_key
) -> None:
    import app.gateway.service.proxy.proxy_upstream as proxy_upstream

    _, _, key = create_site_group_and_key()
    probe_started = Event()
    release_probe = Event()
    calls = 0

    async def send(_client, upstream, *, stream, body_bytes):
        nonlocal calls
        calls += 1
        request = httpx.Request("POST", upstream.url)
        if calls == 1:
            return httpx.Response(
                503,
                headers={"Retry-After": "1"},
                json={"error": {"message": "upstream maintenance"}},
                request=request,
            )
        if calls == 2:
            probe_started.set()
            assert await asyncio.to_thread(release_probe.wait, 10)
        return httpx.Response(
            200,
            json={"choices": [{"message": {"role": "assistant", "content": "ok"}}]},
            request=request,
        )

    monkeypatch.setattr(proxy_upstream, "_send_upstream", send)
    headers = gateway_headers(key)
    body = {"model": "gpt-4o", "messages": [{"role": "user", "content": "hello"}]}
    first = client.post("/v1/chat/completions", headers=headers, json=body)
    assert first.status_code == 503, first.text
    routes = client.get("/api/admin/routes", headers=admin_headers).json()
    assert routes["health"][0]["last_cooldown_seconds"] == 1
    waiting = client.post("/v1/chat/completions", headers=headers, json=body)
    assert waiting.status_code == 503, waiting.text
    assert int(waiting.headers["Retry-After"]) > 0
    assert calls == 1

    sleep(1.05)
    with ThreadPoolExecutor(max_workers=1) as executor:
        probe = executor.submit(
            client.post, "/v1/chat/completions", headers=headers, json=body
        )
        try:
            assert probe_started.wait(5)
            concurrent = client.post("/v1/chat/completions", headers=headers, json=body)
            assert concurrent.status_code == 503, concurrent.text
            assert int(concurrent.headers["Retry-After"]) > 0
            health = client.get("/api/admin/routes", headers=admin_headers).json()[
                "health"
            ][0]
            assert health["available"] is False
            assert calls == 2
        finally:
            release_probe.set()
        assert probe.result(timeout=5).status_code == 200
    recovered = client.post("/v1/chat/completions", headers=headers, json=body)
    assert recovered.status_code == 200, recovered.text
    assert calls == 3


def test_chat_stream_accepts_empty_tool_deltas(
    client, admin_headers, monkeypatch, create_site_group_and_key
) -> None:
    import app.gateway.service.proxy.proxy_upstream as proxy_upstream

    _, _, key = create_site_group_and_key()
    chunks = [
        {"choices": [{"index": 0, "delta": {"tool_calls": [{"index": 0}]}}]},
        {
            "choices": [
                {
                    "index": 0,
                    "delta": {
                        "tool_calls": [
                            {
                                "index": 0,
                                "id": "call_empty_delta",
                                "type": "function",
                                "function": {"name": "lookup", "arguments": "{}"},
                            }
                        ]
                    },
                }
            ]
        },
        {"choices": [{"index": 0, "delta": {}, "finish_reason": "tool_calls"}]},
    ]
    content = (
        "".join(f"data: {json.dumps(chunk)}\n\n" for chunk in chunks)
        + "data: [DONE]\n\n"
    )

    async def send(_client, upstream, *, stream, body_bytes):
        return httpx.Response(
            200,
            content=content,
            headers={"Content-Type": "text/event-stream"},
            request=httpx.Request("POST", upstream.url),
        )

    monkeypatch.setattr(proxy_upstream, "_send_upstream", send)
    response = client.post(
        "/v1/chat/completions",
        headers=gateway_headers(key),
        json={
            "model": "gpt-4o",
            "stream": True,
            "messages": [{"role": "user", "content": "hello"}],
        },
    )
    assert response.status_code == 200, response.text
    assert '"name": "lookup"' in response.text
    assert "[DONE]" in response.text
    assert '"error"' not in response.text
    logs = client.get("/api/admin/request-logs/page", headers=admin_headers).json()[
        "items"
    ]
    assert logs[0]["success"] is True
    assert logs[0]["lifecycle_status"] == "succeeded"


def test_upstream_header_change_clears_cooldown(
    client, admin_headers, monkeypatch, create_site_group_and_key
) -> None:
    import app.gateway.service.proxy.proxy_upstream as proxy_upstream

    _, _, key = create_site_group_and_key()
    calls = []

    async def send(_client, upstream, *, stream, body_bytes):
        calls.append(upstream.headers)
        request = httpx.Request("POST", upstream.url)
        if len(calls) == 1:
            return httpx.Response(
                503,
                headers={"Retry-After": "60"},
                json={"error": {"message": "upstream maintenance"}},
                request=request,
            )
        return httpx.Response(
            200,
            json={"choices": [{"message": {"role": "assistant", "content": "ok"}}]},
            request=request,
        )

    monkeypatch.setattr(proxy_upstream, "_send_upstream", send)
    headers = gateway_headers(key)
    body = {"model": "gpt-4o", "messages": [{"role": "user", "content": "hello"}]}
    assert (
        client.post("/v1/chat/completions", headers=headers, json=body).status_code
        == 503
    )
    assert (
        client.post("/v1/chat/completions", headers=headers, json=body).status_code
        == 503
    )
    assert len(calls) == 1

    saved = client.put(
        "/api/admin/settings",
        headers=admin_headers,
        json={
            "items": [
                {
                    "key": "upstream_headers_config",
                    "value": json.dumps(
                        {
                            "rules": [
                                {
                                    "name": "x-route",
                                    "action": "override",
                                    "value": "repaired",
                                }
                            ]
                        }
                    ),
                }
            ]
        },
    )
    assert saved.status_code == 200, saved.text
    recovered = client.post("/v1/chat/completions", headers=headers, json=body)
    assert recovered.status_code == 200, recovered.text
    assert len(calls) == 2
    assert calls[-1]["x-route"] == "repaired"


def test_context_window_routing_keeps_executable_endpoints(
    client, monkeypatch, create_site, create_model_group, create_gateway_key
) -> None:
    import app.gateway.service.proxy.proxy_upstream as proxy_upstream

    members = []
    for suffix, protocol, size in [
        ("small", "openai_chat", 1000),
        ("large", "anthropic", 100000),
    ]:
        site = valid_site_payload(
            name=suffix,
            base_id=f"base-{suffix}",
            credential_id=f"cred-{suffix}",
            protocol_config_id=f"pc-{suffix}",
            protocols=[protocol],
        )
        site["base_urls"][0]["kind"] = "default" if suffix == "small" else "anthropic"
        site["protocols"][0]["models"][0]["context_window"] = size
        create_site(site)
        members.append(
            {
                "channel_id": f"pc-{suffix}_{protocol}",
                "credential_id": f"cred-{suffix}",
                "model_name": "gpt-4o",
                "enabled": True,
            }
        )
    create_model_group(name="context-group", items=members)
    sent = []

    async def send(_client, upstream, *, stream, body_bytes):
        sent.append(upstream.url)
        return httpx.Response(
            200,
            json={"choices": [{"message": {"role": "assistant", "content": "ok"}}]},
            request=httpx.Request("POST", upstream.url),
        )

    monkeypatch.setattr(proxy_upstream, "_send_upstream", send)
    response = client.post(
        "/v1/chat/completions",
        headers=gateway_headers(create_gateway_key()),
        json={
            "model": "context-group",
            "messages": [{"role": "user", "content": "long prompt " * 2000}],
        },
    )
    assert response.status_code == 200, response.text
    assert sent == ["https://upstream.example/v1/chat/completions"]


def test_context_window_error_with_escaped_chinese_uses_fallback(
    client, monkeypatch, create_site, create_model_group, create_gateway_key
) -> None:
    import app.gateway.service.proxy.proxy_upstream as proxy_upstream

    members = []
    for suffix in ("first", "second"):
        create_site(
            valid_site_payload(
                name=suffix,
                base_id=f"base-{suffix}",
                credential_id=f"cred-{suffix}",
                protocol_config_id=f"pc-{suffix}",
            )
        )
        members.append(
            {
                "channel_id": f"pc-{suffix}_openai_chat",
                "credential_id": f"cred-{suffix}",
                "model_name": "gpt-4o",
                "enabled": True,
            }
        )
    create_model_group(name="context-group", items=members)
    calls = 0

    async def send(_client, upstream, *, stream, body_bytes):
        nonlocal calls
        calls += 1
        request = httpx.Request("POST", upstream.url)
        if calls == 1:
            return httpx.Response(
                400,
                content=json.dumps({"error": {"message": "上下文超过最大长度"}}),
                headers={"Content-Type": "application/json"},
                request=request,
            )
        return httpx.Response(
            200,
            json={"choices": [{"message": {"role": "assistant", "content": "ok"}}]},
            request=request,
        )

    monkeypatch.setattr(proxy_upstream, "_send_upstream", send)
    response = client.post(
        "/v1/chat/completions",
        headers=gateway_headers(create_gateway_key()),
        json={
            "model": "context-group",
            "messages": [{"role": "user", "content": "hello"}],
        },
    )
    assert response.status_code == 200, response.text
    assert calls == 2


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
