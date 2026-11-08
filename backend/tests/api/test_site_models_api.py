from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from typing import Any
from uuid import UUID

import httpx
import pytest
from conftest import assert_error, run_async

from app.gateway.service.tasks.litellm_sync_tasks import (
    _fetch_litellm_payload as _original_fetch_litellm_payload,
)
from app.models.protocols import ProtocolKind
from app.models.settings import SettingItem
from app.models.site_model_test import SiteModelTestResult
from app.persistence.settings_keys import SETTING_FIRST_TOKEN_TIMEOUT_SECONDS


@pytest.fixture(autouse=True)
def offline_model_metadata(monkeypatch):
    import app.gateway.service.tasks.litellm_sync_tasks as metadata

    async def fetch(_proxy):
        return {
            "text-embedding-3-small": {"mode": "embedding"},
            "claude-sonnet-4-5": {"mode": "chat", "litellm_provider": "anthropic"},
            "gpt-5-codex": {"mode": "responses"},
        }

    monkeypatch.setattr(metadata, "_fetch_litellm_payload", fetch)


def _model_test_payload(protocol: ProtocolKind) -> dict[str, Any]:
    return {
        "protocol": protocol.value,
        "base_url": "https://upstream.example/v1",
        "credential": {
            "id": "cred-a",
            "name": "primary",
            "api_key": "upstream-secret",
        },
        "model_name": "test-model",
    }


def test_fetch_site_models_uses_selected_credentials(
    client,
    admin_headers,
    monkeypatch,
) -> None:
    import app.gateway.service.tasks.model_discovery as model_discovery

    seen: list[str] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        credential = request.headers["authorization"].removeprefix("Bearer ")
        seen.append(credential)
        assert request.url.path == "/v1/models"
        assert all(
            timeout is not None and timeout > 0
            for timeout in request.extensions["timeout"].values()
        )
        return httpx.Response(
            200,
            json={
                "data": [
                    {"id": "shared-model"},
                    {"id": f"only-{credential}"},
                    {"id": "gpt-5-codex", "supported_endpoint_types": ["openai"]},
                    {"id": "claude-sonnet-4-5"},
                    {"id": "gemini-2.5-pro"},
                ]
            },
        )

    upstream = httpx.AsyncClient(transport=httpx.MockTransport(handler), timeout=None)
    monkeypatch.setattr(model_discovery, "resolve_http_client", lambda _proxy: upstream)
    try:
        response = client.post(
            "/api/admin/site-model-discoveries",
            headers=admin_headers,
            json={
                "base_url": "https://upstream.example/v1",
                "credentials": [
                    {"id": f"cred-{key}", "name": key, "api_key": f"test-{key}"}
                    for key in ("a", "b", "unused")
                ],
                "credential_ids": ["cred-a", "cred-b"],
            },
        )
    finally:
        run_async(upstream.aclose())

    assert response.status_code == 200
    assert set(seen) == {"test-a", "test-b"}
    assert {
        (item["credential_id"], item["model_name"]) for item in response.json()
    } == {
        ("cred-a", "shared-model"),
        ("cred-b", "shared-model"),
        ("cred-a", "only-test-a"),
        ("cred-b", "only-test-b"),
        *(
            (credential, name)
            for credential in ("cred-a", "cred-b")
            for name in ("gpt-5-codex", "claude-sonnet-4-5", "gemini-2.5-pro")
        ),
    }
    assert {item["model_name"]: item["protocol"] for item in response.json()} == {
        "shared-model": "openai_chat",
        "only-test-a": "openai_chat",
        "only-test-b": "openai_chat",
        "gpt-5-codex": "openai_responses",
        "claude-sonnet-4-5": "anthropic",
        "gemini-2.5-pro": "gemini",
    }


@pytest.mark.parametrize(
    ("protocol", "path", "expected_params", "expected_headers", "upstream_body"),
    [
        pytest.param(
            "anthropic",
            "/v1/models",
            {"limit": "1000"},
            {"x-api-key": "upstream-secret", "anthropic-version": "2023-06-01"},
            {
                "data": [
                    {"id": "model-a", "max_input_tokens": 200_000},
                    {"id": "model-b"},
                ]
            },
            id="anthropic",
        ),
        pytest.param(
            "gemini",
            "/v1beta/models",
            {"key": "upstream-secret", "pageSize": "1000"},
            {"x-goog-api-key": "upstream-secret"},
            {
                "models": [
                    {"name": "models/model-a", "inputTokenLimit": 200_000},
                    {
                        "name": "models/model-b",
                        "supportedGenerationMethods": ["generateContent"],
                    },
                    {
                        "name": "models/embedding-only",
                        "supportedGenerationMethods": ["embedContent"],
                    },
                ]
            },
            id="gemini",
        ),
    ],
)
def test_fetch_site_models_uses_protocol_native_model_list(
    client,
    admin_headers,
    monkeypatch,
    protocol,
    path,
    expected_params,
    expected_headers,
    upstream_body,
) -> None:
    import app.gateway.service.tasks.model_discovery as model_discovery

    captured: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return httpx.Response(200, json=upstream_body)

    upstream_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    monkeypatch.setattr(
        model_discovery, "resolve_http_client", lambda _proxy: upstream_client
    )

    response = client.post(
        "/api/admin/site-model-discoveries",
        headers=admin_headers,
        json={
            "base_url": "https://upstream.example",
            "protocol": protocol,
            "credentials": [
                {"id": "cred-a", "name": "primary", "api_key": "upstream-secret"}
            ],
            "credential_ids": ["cred-a"],
        },
    )

    assert response.status_code == 200, response.text
    assert {item["model_name"]: item["context_window"] for item in response.json()} == {
        "model-a": None,
        "model-b": None,
    }
    request = captured[0]
    assert request.url.path == path
    assert dict(request.url.params) == expected_params
    assert "authorization" not in request.headers
    for name, value in expected_headers.items():
        assert request.headers[name] == value


def test_fetch_site_models_falls_back_to_a_native_model_list(
    client, admin_headers, monkeypatch
) -> None:
    import app.gateway.service.tasks.model_discovery as model_discovery

    def handler(request: httpx.Request) -> httpx.Response:
        if "authorization" in request.headers:
            return httpx.Response(401, json={"error": {"message": "bad key"}})
        return httpx.Response(200, json={"data": [{"id": "claude-sonnet-4-5"}]})

    upstream_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    monkeypatch.setattr(
        model_discovery, "resolve_http_client", lambda _proxy: upstream_client
    )

    response = client.post(
        "/api/admin/site-model-discoveries",
        headers=admin_headers,
        json={
            "base_url": "https://upstream.example",
            "credentials": [{"id": "cred-a", "name": "primary", "api_key": "sk-test"}],
            "credential_ids": ["cred-a"],
        },
    )

    assert response.status_code == 200, response.text
    assert [item["model_name"] for item in response.json()] == ["claude-sonnet-4-5"]


def test_model_protocol_defaults_do_not_call_upstream(
    client, admin_headers, monkeypatch
) -> None:
    sent: list[httpx.Request] = []

    async def unexpected_request(
        _client: httpx.AsyncClient, request: httpx.Request, **_kwargs: Any
    ) -> httpx.Response:
        sent.append(request)
        raise AssertionError("协议预选不得发送上游请求")

    monkeypatch.setattr(httpx.AsyncClient, "send", unexpected_request)
    expected = {
        "gpt-5-codex": ["openai_responses"],
        "openai/gpt-4o": ["openai_responses"],
        "o3-mini": ["openai_responses"],
        "grok-4.7": ["openai_responses"],
        "claude-sonnet-4-5": ["anthropic"],
        "deepseek-v4.1-flash": ["anthropic"],
        "glm-5.3-flash": ["anthropic"],
        "qwen3": ["anthropic"],
        "kimi-k2": ["anthropic"],
        "gemini-2.5-pro": ["gemini"],
        "google/gemma-4-26b": ["gemini"],
        "gemini-3-pro-image": ["gemini"],
        "nano-banana-pro": ["gemini"],
        "text-embedding-3-small": ["openai_embedding"],
        "bge-m3": ["openai_embedding"],
        "bge-reranker-v2-m3": ["rerank"],
        "gpt-image-1": ["openai_image"],
        "grok-imagine-image": ["openai_image"],
        "unknown-model": ["openai_chat"],
    }
    response = client.post(
        "/api/admin/site-model-protocol-detections",
        headers=admin_headers,
        json={"model_names": list(expected)},
    )
    assert response.status_code == 200, response.text
    assert {
        item["model_name"]: item["protocols"] for item in response.json()
    } == expected

    pinned = client.post(
        "/api/admin/site-model-protocol-detections",
        headers=admin_headers,
        json={"endpoint_kind": "openai_chat", "model_names": ["gpt-5-codex"]},
    )
    assert pinned.status_code == 200, pinned.text
    assert pinned.json() == [
        {"model_name": "gpt-5-codex", "protocols": ["openai_chat"]}
    ]
    batch = client.post(
        "/api/admin/site-model-protocol-detections",
        headers=admin_headers,
        json={"model_names": [f"custom-model-{index}" for index in range(1000)]},
    )
    assert batch.status_code == 200, batch.text
    assert len(batch.json()) == 1000
    assert sent == []


def test_fetch_site_models_reports_missing_credentials(client, admin_headers) -> None:
    response = client.post(
        "/api/admin/site-model-discoveries",
        headers=admin_headers,
        json={"base_url": "https://upstream.example/v1", "credential_ids": []},
    )

    assert_error(response, 400, "At least one credential is required")


def test_fetch_site_models_rejects_missing_credentials(client, admin_headers) -> None:
    response = client.post(
        "/api/admin/site-model-discoveries",
        headers=admin_headers,
        json={
            "base_url": "https://upstream.example/v1",
            "headers": [],
            "credentials": [
                {
                    "id": "cred-a",
                    "name": "primary",
                    "api_key": "upstream-secret",
                }
            ],
            "credential_ids": ["missing"],
        },
    )

    assert_error(response, 400, "Credential not found for model discovery")


def test_fetch_site_models_returns_bad_gateway_when_all_upstreams_fail(
    client,
    admin_headers,
    monkeypatch,
) -> None:
    import app.gateway.service.tasks.model_discovery as model_discovery

    upstream = httpx.AsyncClient(
        transport=httpx.MockTransport(
            lambda request: httpx.Response(503, json={"error": "upstream unavailable"})
        )
    )
    monkeypatch.setattr(model_discovery, "resolve_http_client", lambda _proxy: upstream)
    try:
        response = client.post(
            "/api/admin/site-model-discoveries",
            headers=admin_headers,
            json={
                "base_url": "https://upstream.example/v1",
                "headers": [],
                "credentials": [
                    {"id": "cred-a", "name": "primary", "api_key": "upstream-secret"}
                ],
                "credential_ids": ["cred-a"],
            },
        )
    finally:
        run_async(upstream.aclose())

    assert_error(response, 502, "Model discovery failed")


@pytest.mark.parametrize(
    ("protocol", "suffix", "body_field", "upstream_payload", "output"),
    [
        (
            ProtocolKind.OPENAI_CHAT,
            "/v1/chat/completions",
            "messages",
            {"choices": [{"message": {"content": "pong"}}]},
            "pong",
        ),
        (
            ProtocolKind.OPENAI_RESPONSES,
            "/v1/responses",
            "input",
            {
                "status": "completed",
                "output": [
                    {
                        "type": "message",
                        "content": [{"type": "output_text", "text": "pong"}],
                    }
                ],
            },
            "pong",
        ),
        (
            ProtocolKind.OPENAI_EMBEDDING,
            "/v1/embeddings",
            "input",
            {"data": [{"embedding": [0.1, 0.2]}]},
            "<vector dim=2>",
        ),
        (
            ProtocolKind.OPENAI_IMAGE,
            "/v1/images/generations",
            "prompt",
            {"data": [{"b64_json": "YWJj"}]},
            "<image base64>",
        ),
        (
            ProtocolKind.RERANK,
            "/v1/rerank",
            "query",
            {
                "results": [
                    {"index": 0, "relevance_score": 0.95, "document": {"text": "ping"}}
                ]
            },
            "top score=0.9500; index=0; document=ping",
        ),
        (
            ProtocolKind.RERANK,
            "/v2/rerank",
            "query",
            {"results": [{"index": 0, "relevance_score": 0.95}]},
            "top score=0.9500; index=0",
        ),
        (
            ProtocolKind.ANTHROPIC,
            "/v1/messages",
            "messages",
            {"content": [{"type": "text", "text": "pong"}]},
            "pong",
        ),
        (
            ProtocolKind.GEMINI,
            "/v1beta/models/test-model:generateContent",
            "contents",
            {
                "candidates": [
                    {"content": {"role": "model", "parts": [{"text": "pong"}]}}
                ]
            },
            "pong",
        ),
    ],
)
def test_test_site_model_returns_probe_result(
    client,
    admin_headers,
    app_state,
    monkeypatch,
    protocol,
    suffix,
    body_field,
    upstream_payload,
    output,
) -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == suffix
        body = json.loads(request.content)
        assert body_field in body
        assert body.get("stream", False) is False
        if protocol == ProtocolKind.RERANK:
            assert body == {
                "model": "test-model",
                "query": "hi",
                "documents": ["hi"],
                "top_n": 1,
            }
        return httpx.Response(200, json=upstream_payload, request=request)

    import app.gateway.service.tasks.site_model_probe as probe

    upstream_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    monkeypatch.setattr(probe, "app_state", app_state)
    monkeypatch.setattr(probe, "resolve_http_client", lambda _proxy: upstream_client)
    payload = _model_test_payload(protocol)
    if suffix.startswith("/v2/"):
        payload["base_url"] = "https://upstream.example/v2"
    try:
        response = client.post(
            "/api/admin/site-model-tests",
            headers=admin_headers,
            json=payload,
        )
    finally:
        run_async(upstream_client.aclose())

    assert response.status_code == 200
    assert response.json()["success"] is True
    assert response.json()["output_text"] == output


def test_test_site_model_returns_sanitized_probe_debug(
    client, admin_headers, app_state, monkeypatch
) -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["authorization"] == "Bearer upstream-secret"
        return httpx.Response(
            200,
            headers={"content-type": "application/json", "x-request-id": "probe-1"},
            json={"choices": [{"message": {"content": "pong"}}]},
            request=request,
        )

    upstream_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    import app.gateway.service.tasks.site_model_probe as probe

    monkeypatch.setattr(probe, "app_state", app_state)
    monkeypatch.setattr(probe, "resolve_http_client", lambda _proxy: upstream_client)
    try:
        response = client.post(
            "/api/admin/site-model-tests",
            headers=admin_headers,
            json=_model_test_payload(ProtocolKind.OPENAI_CHAT),
        )
    finally:
        run_async(upstream_client.aclose())

    assert response.status_code == 200
    result = response.json()
    assert result["success"] is True
    assert result["debug"]["request"]["path"] == "/v1/chat/completions"
    assert result["debug"]["request"]["body"]["messages"] == [
        {"role": "user", "content": "hi"}
    ]
    assert result["debug"]["response"]["headers"]["x-request-id"] == "probe-1"
    assert "upstream-secret" not in response.text


@pytest.mark.parametrize(
    ("protocol", "test_mode", "event"),
    [
        (
            ProtocolKind.OPENAI_CHAT,
            "codex",
            {"choices": [{"index": 0, "delta": {"content": "hello"}}]},
        ),
        (
            ProtocolKind.OPENAI_RESPONSES,
            "codex",
            {"type": "response.output_text.delta", "delta": "hello"},
        ),
        (
            ProtocolKind.ANTHROPIC,
            "claude",
            {
                "type": "content_block_delta",
                "index": 0,
                "delta": {"type": "text_delta", "text": "hello"},
            },
        ),
    ],
)
def test_model_test_uses_client_identity_and_reads_stream(
    client, admin_headers, monkeypatch, protocol, test_mode, event
) -> None:
    class ProbeStream(httpx.AsyncByteStream):
        async def __aiter__(self) -> AsyncIterator[bytes]:
            yield b": connected\n\n"
            await asyncio.sleep(0.02)
            yield f"data: {json.dumps(event)}\n\ndata: [DONE]\n\n".encode()

    async def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        assert body["stream"] is True
        assert body["temperature"] == 0.2
        assert request.headers["accept"] == "application/json, text/event-stream"
        assert request.headers["x-test"] == "configured"
        if test_mode == "codex":
            assert request.headers["user-agent"].startswith("codex_cli_rs/")
            assert request.headers["originator"] == "codex_cli_rs"
            assert (
                request.headers["user-agent"]
                == f"codex_cli_rs/{request.headers['version']}"
            )
            assert request.headers["openai-beta"] == "responses=experimental"
            assert UUID(request.headers["x-codex-window-id"])
            assert UUID(request.headers["session_id"])
            assert request.headers["authorization"] == "Bearer upstream-secret"
        else:
            assert request.headers["user-agent"].startswith("claude-cli/")
            assert request.headers["x-app"] == "cli"
            assert request.headers["x-stainless-lang"] == "js"
            assert "claude-code-20250219" in request.headers["anthropic-beta"].split(
                ","
            )
            assert request.headers["anthropic-version"] == "2023-06-01"
            assert body["system"] == [
                {
                    "type": "text",
                    "text": "You are Claude Code, Anthropic's official CLI for Claude.",
                }
            ]
            user_id = json.loads(body["metadata"]["user_id"])
            assert len(bytes.fromhex(user_id["device_id"])) == 32
            assert user_id["account_uuid"] == ""
            assert UUID(user_id["session_id"])
            assert request.headers["x-api-key"] == "upstream-secret"
        if protocol == ProtocolKind.OPENAI_RESPONSES:
            assert request.url.path == "/v1/responses"
            assert body["store"] is False
            assert body["input"][0]["content"] == [{"type": "input_text", "text": "hi"}]
        else:
            assert request.url.path == (
                "/v1/messages" if test_mode == "claude" else "/v1/chat/completions"
            )
            assert body["messages"] == [{"role": "user", "content": "hi"}]
        return httpx.Response(
            200,
            headers={"content-type": "text/event-stream"},
            stream=ProbeStream(),
        )

    import app.gateway.service.tasks.site_model_probe as probe

    upstream = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    monkeypatch.setattr(probe, "resolve_http_client", lambda _proxy: upstream)
    try:
        response = client.post(
            "/api/admin/site-model-tests",
            headers=admin_headers,
            json={
                **_model_test_payload(protocol),
                "test_mode": test_mode,
                "headers": [
                    {"name": "X-Test", "action": "override", "value": "configured"}
                ],
                "param_override": [
                    {"path": "temperature", "action": "set", "value": 0.2}
                ],
            },
        )
    finally:
        run_async(upstream.aclose())

    assert response.status_code == 200, response.text
    result = response.json()
    assert result["success"] is True
    assert result["output_text"] == "hello"
    assert result["latency_ms"] >= 15
    headers = result["debug"]["request"]["headers"]
    if test_mode == "codex":
        assert UUID(headers["x-codex-window-id"])
        assert headers["openai-beta"] == "responses=experimental"
    else:
        assert "claude-code-20250219" in headers["anthropic-beta"].split(",")
    assert "upstream-secret" not in response.text


@pytest.mark.parametrize(
    ("protocol", "test_mode", "events", "error"),
    [
        (
            ProtocolKind.OPENAI_CHAT,
            "codex",
            [{"error": {"message": "overloaded"}}],
            "overloaded",
        ),
        (
            ProtocolKind.OPENAI_RESPONSES,
            "codex",
            [
                {"type": "response.output_text.delta", "delta": "partial"},
                {
                    "type": "response.failed",
                    "response": {"error": {"message": "overloaded"}},
                },
            ],
            "overloaded",
        ),
        (
            ProtocolKind.ANTHROPIC,
            "claude",
            [{"type": "error", "error": {"message": "overloaded"}}],
            "overloaded",
        ),
        (ProtocolKind.OPENAI_RESPONSES, "codex", [], "without model output"),
    ],
)
def test_model_test_reports_failed_or_empty_stream(
    client, admin_headers, monkeypatch, protocol, test_mode, events, error
) -> None:
    async def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            headers={"content-type": "text/event-stream"},
            content="".join(f"data: {json.dumps(event)}\n\n" for event in events)
            + "data: [DONE]\n\n",
        )

    import app.gateway.service.tasks.site_model_probe as probe

    upstream = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    monkeypatch.setattr(probe, "resolve_http_client", lambda _proxy: upstream)
    try:
        response = client.post(
            "/api/admin/site-model-tests",
            headers=admin_headers,
            json={**_model_test_payload(protocol), "test_mode": test_mode},
        )
    finally:
        run_async(upstream.aclose())

    assert response.status_code == 200, response.text
    result = response.json()
    assert result["success"] is False
    assert result["status_code"] == 502
    assert error in result["error_message"]


@pytest.mark.parametrize(
    ("protocol", "test_mode", "message"),
    [
        (ProtocolKind.ANTHROPIC, "codex", "Codex tests require OpenAI"),
        (ProtocolKind.OPENAI_CHAT, "claude", "Claude tests require Anthropic"),
    ],
)
def test_model_test_rejects_incompatible_client_protocol(
    client, admin_headers, protocol, test_mode, message
) -> None:
    response = client.post(
        "/api/admin/site-model-tests",
        headers=admin_headers,
        json={**_model_test_payload(protocol), "test_mode": test_mode},
    )
    assert_error(response, 400, message)


def test_test_gemini_probe_debug_hides_api_key(
    client, admin_headers, app_state, monkeypatch
) -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path.endswith("/v1beta/models/test-model:generateContent")
        assert request.headers["x-goog-api-key"] == "upstream-secret"
        return httpx.Response(
            200,
            json={
                "modelVersion": "test-model",
                "candidates": [
                    {
                        "content": {"role": "model", "parts": [{"text": "OK"}]},
                        "finishReason": "STOP",
                    }
                ],
            },
            request=request,
        )

    upstream_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    import app.gateway.service.tasks.site_model_probe as probe

    monkeypatch.setattr(probe, "app_state", app_state)
    monkeypatch.setattr(probe, "resolve_http_client", lambda _proxy: upstream_client)
    try:
        response = client.post(
            "/api/admin/site-model-tests",
            headers=admin_headers,
            json=_model_test_payload(ProtocolKind.GEMINI),
        )
    finally:
        run_async(upstream_client.aclose())

    assert response.status_code == 200
    assert (
        response.json()["debug"]["request"]["path"]
        == "/v1beta/models/test-model:generateContent"
    )
    assert "upstream-secret" not in response.text


def test_test_site_model_returns_timeout_result(
    client,
    admin_headers,
    app_state,
    monkeypatch,
) -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        await asyncio.sleep(60)
        return httpx.Response(200, json={}, request=request)

    upstream_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    import app.gateway.service.tasks.site_model_probe as probe

    monkeypatch.setattr(probe, "app_state", app_state)
    monkeypatch.setattr(probe, "resolve_http_client", lambda _proxy: upstream_client)
    run_async(
        app_state.settings_repo.upsert_settings(
            [SettingItem(key=SETTING_FIRST_TOKEN_TIMEOUT_SECONDS, value="0.01")]
        )
    )

    try:
        response = client.post(
            "/api/admin/site-model-tests",
            headers=admin_headers,
            json=_model_test_payload(ProtocolKind.OPENAI_CHAT),
        )
    finally:
        run_async(upstream_client.aclose())

    assert response.status_code == 200
    assert response.json()["success"] is False
    assert response.json()["status_code"] == 504
    assert "timed out after 0.01s" in response.json()["error_message"]
    assert response.json()["debug"]["request"]["path"] == "/v1/chat/completions"


@pytest.mark.parametrize(
    ("protocol", "forbidden_fields"),
    [
        (ProtocolKind.OPENAI_EMBEDDING, ("stream",)),
        (ProtocolKind.OPENAI_IMAGE, ("stream",)),
        (ProtocolKind.RERANK, ("stream",)),
        (
            ProtocolKind.OPENAI_CHAT,
            ("max_tokens", "max_completion_tokens"),
        ),
    ],
)
def test_test_site_model_omits_unsupported_upstream_fields(
    client,
    admin_headers,
    monkeypatch,
    protocol: ProtocolKind,
    forbidden_fields: tuple[str, ...],
) -> None:
    captured_body: dict[str, Any] = {}

    async def fake_probe(**kwargs: Any) -> SiteModelTestResult:
        captured_body.update(kwargs["body"])
        return SiteModelTestResult(
            success=True,
            status_code=200,
            latency_ms=1,
            model_name=kwargs["model_name"],
            credential_id=kwargs["credential_id"],
        )

    import app.gateway.service.tasks.site_model_probe as probe

    monkeypatch.setattr(probe, "_call_site_model_probe_channel", fake_probe)

    response = client.post(
        "/api/admin/site-model-tests",
        headers=admin_headers,
        json=_model_test_payload(protocol),
    )

    assert response.status_code == 200
    assert all(field not in captured_body for field in forbidden_fields)


def test_test_site_model_rejects_non_object_success_payload(
    client,
    admin_headers,
    app_state,
    monkeypatch,
) -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=[], request=request)

    upstream_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    import app.gateway.service.tasks.site_model_probe as probe

    monkeypatch.setattr(probe, "app_state", app_state)
    monkeypatch.setattr(probe, "resolve_http_client", lambda _proxy: upstream_client)
    try:
        response = client.post(
            "/api/admin/site-model-tests",
            headers=admin_headers,
            json=_model_test_payload(ProtocolKind.OPENAI_CHAT),
        )
    finally:
        run_async(upstream_client.aclose())

    assert response.status_code == 200
    assert response.json()["success"] is False
    assert response.json()["status_code"] == 502
    assert response.json()["error_message"] == (
        "Invalid upstream response: Expected JSON object"
    )


def _model(
    model_name: str,
    *,
    credential_id: str = "cred-a",
    **fields: Any,
) -> dict[str, Any]:
    return {
        "credential_id": credential_id,
        "model_name": model_name,
        "enabled": True,
        "protocol": "openai_chat",
        **fields,
    }


def _sync_site_payload(
    *,
    models: list[dict[str, Any]] | None = None,
    patterns: dict[str, str] | None = None,
    **site_fields: Any,
) -> dict[str, Any]:
    """Build a two-credential site with stored models and per-key filters."""
    filters = patterns or {}
    return {
        "name": "Multi-key Site",
        **site_fields,
        "base_urls": [{"id": "base-1", "url": "https://upstream.example/v1"}],
        "credentials": [
            {
                "id": "cred-a",
                "name": "key-a",
                "api_key": "secret-a",
                "model_pattern": filters.get("cred-a", ""),
            },
            {
                "id": "cred-b",
                "name": "key-b",
                "api_key": "secret-b",
                "model_pattern": filters.get("cred-b", ""),
            },
        ],
        "protocols": [
            {
                "id": "pc-1",
                "base_url_id": "base-1",
                "protocols": ["openai_chat"],
                "models": list(models or []),
            }
        ],
    }


def _create_sync_site(client, admin_headers, payload: dict[str, Any]) -> str:
    response = client.post("/api/admin/sites", headers=admin_headers, json=payload)
    assert response.status_code == 201, response.text
    return response.json()["id"]


def _patch_upstream_models(monkeypatch, fetch: Any) -> None:
    import app.gateway.service.tasks.model_discovery as discovery
    from app.gateway.service.tasks.model_discovery import UpstreamModel

    async def fetch_models(channel: Any) -> list[UpstreamModel]:
        return [
            item if isinstance(item, UpstreamModel) else UpstreamModel(name=item)
            for item in await fetch(channel)
        ]

    monkeypatch.setattr(discovery, "fetch_upstream_models", fetch_models)


def _run_model_sync(client, admin_headers, **body: Any) -> dict[str, Any]:
    response = client.post(
        "/api/admin/channel-model-sync", headers=admin_headers, json=body
    )
    assert response.status_code == 200, response.text
    return response.json()


def _stored_models(client, admin_headers) -> set[tuple[str, str]]:
    site = client.get("/api/admin/sites", headers=admin_headers).json()[0]
    return {
        (model["credential_id"], model["model_name"])
        for model in site["protocols"][0]["models"]
    }


def test_model_context_defaults_and_manual_detection(
    client, admin_headers, monkeypatch
) -> None:
    import app.gateway.service.tasks.litellm_sync_tasks as metadata
    import app.gateway.service.tasks.model_discovery as discovery

    catalog = {
        "gpt-4o": {
            "mode": "chat",
            "max_input_tokens": 128_000,
            "input_cost_per_token": 0.000001,
        }
    }
    upstream = {
        "data": [
            {"id": "gpt-4o", "context_length": 200_000},
            {"id": "unknown-128k", "context_length": 32_000},
        ]
    }
    client_type = httpx.AsyncClient
    catalog_requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if str(request.url) == metadata.LITELLM_PRICE_URL:
            catalog_requests.append(request)
            return httpx.Response(200, json=catalog)
        return httpx.Response(200, json=upstream)

    transport = httpx.MockTransport(handler)
    monkeypatch.setattr(
        metadata.httpx,
        "AsyncClient",
        lambda **_kwargs: client_type(transport=transport),
    )
    upstream_client = client_type(transport=transport)
    monkeypatch.setattr(
        discovery, "resolve_http_client", lambda _proxy: upstream_client
    )
    # 覆盖本模块的默认离线目录，以真实 HTTP 客户端经过网络桩。
    monkeypatch.setattr(
        metadata, "_fetch_litellm_payload", _original_fetch_litellm_payload
    )
    site_id = _create_sync_site(
        client, admin_headers, _sync_site_payload(patterns={"cred-a": "*"})
    )

    def models():
        site = client.get("/api/admin/sites", headers=admin_headers).json()[0]
        return {model["model_name"]: model for model in site["protocols"][0]["models"]}

    try:
        catalog_requests.clear()
        response = client.post(
            "/api/admin/site-model-discoveries",
            headers=admin_headers,
            json={
                "base_url": "https://upstream.example/v1",
                "credentials": [
                    {"id": "cred-a", "name": "test", "api_key": "test-key"}
                ],
                "credential_ids": ["cred-a"],
            },
        )
        assert response.status_code == 200, response.text
        assert {
            item["model_name"]: item["context_window"] for item in response.json()
        } == {"gpt-4o": None, "unknown-128k": None}
        assert not catalog_requests
        response = client.post(
            "/api/admin/model-context-detections",
            headers=admin_headers,
            json={"model_names": ["gpt-4o", "unknown-128k"]},
        )
        assert response.status_code == 200, response.text
        assert response.json() == {"gpt-4o": 128_000, "unknown-128k": None}
        assert len(catalog_requests) == 1
        _run_model_sync(client, admin_headers, site_ids=[site_id])
        assert models()["gpt-4o"]["context_window"] == 128_000
        assert models()["unknown-128k"]["context_window"] is None

        payload = _sync_site_payload(
            patterns={"cred-a": "*"},
            models=[_model("gpt-4o", context_window=64_000), _model("unknown-128k")],
        )
        response = client.put(
            f"/api/admin/sites/{site_id}", headers=admin_headers, json=payload
        )
        assert response.status_code == 200, response.text
        catalog["gpt-4o"]["max_input_tokens"] = 256_000
        _run_model_sync(client, admin_headers, site_ids=[site_id])
        response = client.post(
            "/api/admin/model-price-sync-jobs", headers=admin_headers
        )
        assert response.status_code == 200, response.text
        assert models()["gpt-4o"]["context_window"] == 64_000
        groups = client.get("/api/admin/model-groups", headers=admin_headers).json()
        assert all(group["context_window"] is None for group in groups)

        response = client.post(
            "/api/admin/model-context-detections",
            headers=admin_headers,
            json={"model_names": ["gpt-4o", "unknown-128k"]},
        )
        assert response.status_code == 200, response.text
        assert response.json() == {"gpt-4o": 256_000, "unknown-128k": None}
        payload["protocols"][0]["models"][0]["context_window"] = response.json()[
            "gpt-4o"
        ]
        response = client.put(
            f"/api/admin/sites/{site_id}", headers=admin_headers, json=payload
        )
        assert response.status_code == 200, response.text
        assert models()["gpt-4o"]["context_window"] == 256_000
        catalog.clear()
        response = client.post(
            "/api/admin/model-context-detections",
            headers=admin_headers,
            json={"model_names": ["gpt-4o"]},
        )
        assert response.status_code == 200, response.text
        assert response.json() == {"gpt-4o": None}
        payload["protocols"][0]["models"][0]["context_window"] = None
        response = client.put(
            f"/api/admin/sites/{site_id}", headers=admin_headers, json=payload
        )
        assert response.status_code == 200, response.text
        _run_model_sync(client, admin_headers, site_ids=[site_id])
        assert models()["gpt-4o"]["context_window"] is None
    finally:
        run_async(upstream_client.aclose())


def _added_names(result: dict[str, Any]) -> dict[str, tuple[str, ...]]:
    return {item["credential_id"]: tuple(item["added"]) for item in result["items"]}


def test_channel_model_sync_keeps_manual_models_when_the_filter_is_empty(
    client,
    admin_headers,
    monkeypatch,
) -> None:
    _create_sync_site(
        client,
        admin_headers,
        _sync_site_payload(models=[_model("manual-only")]),
    )

    async def fail_fetch(_channel: Any) -> list[str]:
        raise AssertionError("empty filters must not fetch or sync the catalog")

    _patch_upstream_models(monkeypatch, fail_fetch)

    result = _run_model_sync(client, admin_headers)
    groups = client.get("/api/admin/model-groups", headers=admin_headers).json()

    assert {item["status"] for item in result["items"]} == {"unchanged"}
    assert _stored_models(client, admin_headers) == {
        ("cred-a", "manual-only"),
    }
    assert [group["name"] for group in groups] == ["manual-only"]


def test_channel_model_sync_keeps_only_models_matching_the_key_filter(
    client,
    admin_headers,
    monkeypatch,
) -> None:
    _create_sync_site(
        client,
        admin_headers,
        _sync_site_payload(patterns={"cred-a": "^gpt-4.*", "cred-b": "*"}),
    )

    async def fake_fetch(_channel: Any) -> list[str]:
        return ["gpt-4o", "gpt-4o-mini", "claude-3-opus"]

    _patch_upstream_models(monkeypatch, fake_fetch)

    result = _run_model_sync(client, admin_headers)

    assert _added_names(result)["cred-a"] == ("gpt-4o", "gpt-4o-mini")
    assert _stored_models(client, admin_headers) == {
        ("cred-a", "gpt-4o"),
        ("cred-a", "gpt-4o-mini"),
        ("cred-b", "gpt-4o"),
        ("cred-b", "gpt-4o-mini"),
        ("cred-b", "claude-3-opus"),
    }


def test_channel_model_sync_matches_whole_names_only(
    client,
    admin_headers,
    monkeypatch,
) -> None:
    _create_sync_site(
        client,
        admin_headers,
        _sync_site_payload(patterns={"cred-a": "gpt-4"}),
    )

    async def fake_fetch(_channel: Any) -> list[str]:
        return ["gpt-4", "gpt-4o", "gpt-4o-mini"]

    _patch_upstream_models(monkeypatch, fake_fetch)

    _run_model_sync(client, admin_headers)

    # ``gpt-4`` is a whole name, so its longer siblings stay out.
    assert {
        name
        for credential_id, name in _stored_models(client, admin_headers)
        if credential_id == "cred-a"
    } == {"gpt-4"}


def test_channel_model_sync_treats_dots_in_literal_names_as_text(
    client,
    admin_headers,
    monkeypatch,
) -> None:
    _create_sync_site(
        client,
        admin_headers,
        _sync_site_payload(patterns={"cred-a": "claude-3.5-sonnet"}),
    )

    async def fake_fetch(_channel: Any) -> list[str]:
        return ["claude-3.5-sonnet", "claude-3x5-sonnet"]

    _patch_upstream_models(monkeypatch, fake_fetch)

    _run_model_sync(client, admin_headers)

    assert {
        name
        for credential_id, name in _stored_models(client, admin_headers)
        if credential_id == "cred-a"
    } == {"claude-3.5-sonnet"}


def test_channel_model_sync_wildcard_filter_takes_every_model(
    client,
    admin_headers,
    monkeypatch,
) -> None:
    _create_sync_site(
        client,
        admin_headers,
        _sync_site_payload(patterns={"cred-a": "*", "cred-b": "^none$"}),
    )

    async def fake_fetch(_channel: Any) -> list[str]:
        return ["gpt-4o", "claude-3-opus"]

    _patch_upstream_models(monkeypatch, fake_fetch)

    _run_model_sync(client, admin_headers)

    assert _stored_models(client, admin_headers) == {
        ("cred-a", "gpt-4o"),
        ("cred-a", "claude-3-opus"),
    }


def test_channel_model_sync_stores_a_protocol_per_new_model(
    client,
    admin_headers,
    monkeypatch,
) -> None:
    from app.gateway.service.tasks.model_discovery import UpstreamModel

    site_id = _create_sync_site(
        client, admin_headers, _sync_site_payload(patterns={"cred-a": "*"})
    )

    async def fake_fetch(_channel: Any) -> list[UpstreamModel]:
        return [
            UpstreamModel(name="gpt-4o"),
            UpstreamModel(name="text-embedding-3-small"),
            UpstreamModel(name="gpt-5-codex"),
            UpstreamModel(
                name="claude-sonnet-4-5",
                protocols=(ProtocolKind.OPENAI_CHAT, ProtocolKind.ANTHROPIC),
            ),
        ]

    _patch_upstream_models(monkeypatch, fake_fetch)

    _run_model_sync(client, admin_headers)
    site = client.get("/api/admin/sites", headers=admin_headers).json()[0]

    assert {
        (model["model_name"], model["protocol"])
        for model in site["protocols"][0]["models"]
    } == {
        ("gpt-4o", "openai_responses"),
        ("text-embedding-3-small", "openai_embedding"),
        ("gpt-5-codex", "openai_responses"),
        ("claude-sonnet-4-5", "anthropic"),
    }

    payload = _sync_site_payload(
        patterns={"cred-a": "*"},
        models=[
            _model(
                model["model_name"],
                protocol="openai_chat"
                if model["model_name"] == "gpt-5-codex"
                else model["protocol"],
            )
            for model in site["protocols"][0]["models"]
        ],
    )
    response = client.put(
        f"/api/admin/sites/{site_id}", headers=admin_headers, json=payload
    )
    assert response.status_code == 200, response.text
    _run_model_sync(client, admin_headers, site_ids=[site_id])
    site = client.get("/api/admin/sites", headers=admin_headers).json()[0]
    assert (
        next(
            model["protocol"]
            for model in site["protocols"][0]["models"]
            if model["model_name"] == "gpt-5-codex"
        )
        == "openai_chat"
    )


@pytest.mark.parametrize("china_mode", ["shared", "owned", "absent"])
def test_multi_url_models_keep_each_source_through_save_and_sync(
    client,
    admin_headers,
    monkeypatch,
    china_mode,
) -> None:
    import app.gateway.service.tasks.model_discovery as discovery

    payload = _sync_site_payload(patterns={"cred-a": "*"})
    payload["credentials"] = payload["credentials"][:1]
    payload["base_urls"] = [
        {"id": "main", "kind": "default", "url": "https://main.example/v1"},
        {"id": "china", "kind": "china", "url": "https://china.example/v1"},
        {"id": "claude", "kind": "anthropic", "url": "https://claude.example/v1"},
    ]
    payload["protocols"] = [
        {
            "id": "pc-main",
            "base_url_id": "main",
            "protocols": ["openai_chat", "anthropic"],
            "models": [
                _model("gpt-4o"),
                _model("claude-sonnet-4-5", protocol="anthropic"),
            ],
        },
        {
            "id": "pc-china",
            "base_url_id": "china",
            "protocols": ["openai_chat"],
            "models": [_model("gpt-4o")],
        },
        {
            "id": "pc-claude",
            "base_url_id": "claude",
            "protocols": ["anthropic"],
            "models": [_model("claude-sonnet-4-5", protocol="anthropic")],
        },
    ]
    if china_mode == "owned":
        payload["credentials"].append(
            {
                "id": "cred-china",
                "name": "china-key",
                "api_key": "secret-china",
                "base_url_id": "china",
                "model_pattern": "*",
            }
        )
        payload["protocols"][1]["models"][0]["credential_id"] = "cred-china"
    elif china_mode == "absent":
        payload["base_urls"] = [
            url for url in payload["base_urls"] if url["id"] != "china"
        ]
        payload["protocols"] = [
            config
            for config in payload["protocols"]
            if config["base_url_id"] != "china"
        ]
    site_id = _create_sync_site(client, admin_headers, payload)
    fetched: list[str] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        fetched.append(request.url.host)
        if request.url.host == "claude.example":
            return httpx.Response(200, json={"data": [{"id": "claude-sonnet-4-5"}]})
        return httpx.Response(
            200,
            json={
                "data": [
                    {"id": "gpt-4o", "supported_endpoint_types": ["openai"]},
                    {
                        "id": "claude-sonnet-4-5",
                        "supported_endpoint_types": ["anthropic"],
                    },
                    {"id": "text-embedding-3-small"},
                ]
            },
        )

    upstream = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    monkeypatch.setattr(discovery, "resolve_http_client", lambda _proxy: upstream)

    def stored() -> dict[str, set[tuple[str, str]]]:
        site = client.get("/api/admin/sites", headers=admin_headers).json()[0]
        return {
            config["base_url_id"]: {
                (model["model_name"], model["protocol"]) for model in config["models"]
            }
            for config in site["protocols"]
        }

    try:
        expected = {
            "main": {("gpt-4o", "openai_chat"), ("claude-sonnet-4-5", "anthropic")},
            "claude": {("claude-sonnet-4-5", "anthropic")},
        }
        if china_mode != "absent":
            expected["china"] = {("gpt-4o", "openai_chat")}
        assert stored() == expected
        expected["main"].add(("text-embedding-3-small", "openai_embedding"))
        if china_mode != "absent":
            expected["china"] |= {
                ("text-embedding-3-small", "openai_embedding"),
                ("claude-sonnet-4-5", "anthropic"),
            }
        for _ in range(2):
            result = _run_model_sync(client, admin_headers, site_ids=[site_id])
            assert {item["status"] for item in result["items"]} <= {
                "updated",
                "unchanged",
            }
            assert stored() == expected
        assert fetched.count("china.example") == (0 if china_mode == "absent" else 2)
        assert fetched.count("main.example") == 2
        assert fetched.count("claude.example") == 2
        groups = client.post(
            "/api/admin/model-group-candidates",
            headers=admin_headers,
            json={"items": []},
        )
        assert groups.status_code == 200, groups.text
        expected_names = [
            "claude-sonnet-4-5",
            "gpt-4o",
            "text-embedding-3-small",
        ]
        if china_mode == "owned":
            expected_names *= 2
        assert sorted(
            item["model_name"] for item in groups.json()["candidates"]
        ) == sorted(expected_names)
        update = client.put(
            f"/api/admin/sites/{site_id}", headers=admin_headers, json=payload
        )
        assert update.status_code == 200, update.text
        assert sum(len(models) for models in stored().values()) == (
            3 if china_mode == "absent" else 4
        )
    finally:
        run_async(upstream.aclose())


def test_protocol_endpoint_preserves_both_model_sources_through_save_and_sync(
    client,
    admin_headers,
    monkeypatch,
) -> None:
    payload = _sync_site_payload(patterns={"cred-a": "*"})
    payload["credentials"] = payload["credentials"][:1]
    payload["base_urls"] = [
        {"id": "main", "kind": "default", "url": "https://main.example/v1"},
        {
            "id": "protocol",
            "kind": "protocol",
            "url": "https://protocol.example/v1",
        },
    ]
    payload["protocols"] = [
        {
            "id": "pc-main",
            "base_url_id": "main",
            "protocols": ["openai_chat"],
            "models": [_model("shared-model")],
        },
        {
            "id": "pc-protocol",
            "base_url_id": "protocol",
            "protocols": ["openai_chat"],
            "models": [_model("shared-model")],
        },
    ]
    site_id = _create_sync_site(client, admin_headers, payload)

    def stored() -> dict[str, set[tuple[str, str]]]:
        site = client.get("/api/admin/sites", headers=admin_headers).json()[0]
        return {
            config["base_url_id"]: {
                (model["model_name"], model["protocol"]) for model in config["models"]
            }
            for config in site["protocols"]
        }

    assert stored() == {
        "main": {("shared-model", "openai_chat")},
        "protocol": {("shared-model", "openai_chat")},
    }

    async def fake_fetch(_channel: Any) -> list[str]:
        return ["shared-model"]

    _patch_upstream_models(monkeypatch, fake_fetch)

    result = _run_model_sync(client, admin_headers, site_ids=[site_id])

    assert {item["status"] for item in result["items"]} <= {"updated", "unchanged"}
    assert stored() == {
        "main": {("shared-model", "openai_chat")},
        "protocol": {("shared-model", "openai_chat")},
    }


def test_channel_model_sync_keeps_same_name_targets_for_distinct_protocols(
    client,
    admin_headers,
    monkeypatch,
) -> None:
    payload = _sync_site_payload(patterns={"cred-a": "*"})
    payload["credentials"] = payload["credentials"][:1]
    payload["base_urls"] = [
        {"id": "main", "kind": "default", "url": "https://main.example/v1"},
        {
            "id": "anthropic",
            "kind": "anthropic",
            "url": "https://anthropic.example/v1",
        },
    ]
    payload["protocols"] = [
        {
            "id": "pc-main",
            "base_url_id": "main",
            "protocols": ["openai_chat"],
            "models": [
                _model("shared-model"),
                _model("shared-model", protocol="openai_responses"),
            ],
        },
        {
            "id": "pc-anthropic",
            "base_url_id": "anthropic",
            "protocols": ["anthropic"],
            "models": [_model("shared-model", protocol="anthropic")],
        },
    ]
    site_id = _create_sync_site(client, admin_headers, payload)

    async def fake_fetch(_channel: Any) -> list[str]:
        return ["shared-model"]

    _patch_upstream_models(monkeypatch, fake_fetch)

    result = _run_model_sync(client, admin_headers, site_ids=[site_id])
    site = client.get("/api/admin/sites", headers=admin_headers).json()[0]
    stored = {
        config["base_url_id"]: {
            (model["model_name"], model["protocol"]) for model in config["models"]
        }
        for config in site["protocols"]
    }

    assert all(not item["missing"] for item in result["items"])
    assert stored == {
        "main": {("shared-model", "openai_chat"), ("shared-model", "openai_responses")},
        "anthropic": {("shared-model", "anthropic")},
    }


def test_channel_model_sync_deletes_models_that_leave_the_catalog(
    client,
    admin_headers,
    monkeypatch,
) -> None:
    _create_sync_site(
        client,
        admin_headers,
        _sync_site_payload(patterns={"cred-a": "*", "cred-b": "*"}),
    )
    upstream_models = ["gpt-4o", "gpt-4o-mini"]

    async def fake_fetch(_channel: Any) -> list[str]:
        return list(upstream_models)

    _patch_upstream_models(monkeypatch, fake_fetch)
    _run_model_sync(client, admin_headers)

    upstream_models.remove("gpt-4o-mini")
    result = _run_model_sync(client, admin_headers)

    assert {
        (item["credential_id"], tuple(item["missing"])) for item in result["items"]
    } == {("cred-a", ("gpt-4o-mini",)), ("cred-b", ("gpt-4o-mini",))}
    assert _stored_models(client, admin_headers) == {
        ("cred-a", "gpt-4o"),
        ("cred-b", "gpt-4o"),
    }


def test_channel_model_sync_keeps_admin_settings_on_existing_rows(
    client,
    admin_headers,
    monkeypatch,
) -> None:
    _create_sync_site(
        client,
        admin_headers,
        _sync_site_payload(
            patterns={"cred-a": "*", "cred-b": "*"},
            models=[_model("gpt-4o", enabled=False, context_window=64000)],
        ),
    )

    async def fake_fetch(_channel: Any) -> list[str]:
        return ["gpt-4o"]

    _patch_upstream_models(monkeypatch, fake_fetch)
    _run_model_sync(client, admin_headers)

    site = client.get("/api/admin/sites", headers=admin_headers).json()[0]
    model = next(
        item
        for item in site["protocols"][0]["models"]
        if item["model_name"] == "gpt-4o"
    )

    assert model["enabled"] is False
    assert model["context_window"] == 64000


def test_channel_model_sync_applies_each_key_filter_separately(
    client,
    admin_headers,
    monkeypatch,
) -> None:
    _create_sync_site(
        client,
        admin_headers,
        _sync_site_payload(patterns={"cred-a": "^gpt-.*", "cred-b": "^claude-.*"}),
    )

    async def fake_fetch(_channel: Any) -> list[str]:
        return ["gpt-4o", "claude-3-opus"]

    _patch_upstream_models(monkeypatch, fake_fetch)

    _run_model_sync(client, admin_headers)

    assert _stored_models(client, admin_headers) == {
        ("cred-a", "gpt-4o"),
        ("cred-b", "claude-3-opus"),
    }


def test_channel_model_sync_can_limit_the_credential_scope(
    client,
    admin_headers,
    monkeypatch,
) -> None:
    _create_sync_site(
        client,
        admin_headers,
        _sync_site_payload(
            patterns={"cred-a": "*", "cred-b": "*"},
            models=[
                _model("old-a", credential_id="cred-a"),
                _model("old-b", credential_id="cred-b"),
            ],
        ),
    )

    async def fake_fetch(_channel: Any) -> list[str]:
        return ["new-model"]

    _patch_upstream_models(monkeypatch, fake_fetch)

    site = client.get("/api/admin/sites", headers=admin_headers).json()[0]
    site_id = site["id"]
    result = _run_model_sync(
        client,
        admin_headers,
        site_ids=[site_id],
        credential_ids=["cred-a"],
    )

    assert [item["credential_id"] for item in result["items"]] == ["cred-a"]
    assert _stored_models(client, admin_headers) == {
        ("cred-a", "new-model"),
        ("cred-b", "old-b"),
    }


def test_model_rules_preview_save_and_sync_explicit_names(
    client, admin_headers, monkeypatch
) -> None:
    import app.gateway.service.tasks.model_discovery as discovery

    payload = _sync_site_payload(models=[_model("other-key", credential_id="cred-b")])
    site_id = _create_sync_site(client, admin_headers, payload)
    pattern = "private.v1\nclaude-private\nprivate.v1"
    upstream_names = ["gpt-kept", "gpt-retired", "unmatched"]
    requests: list[httpx.Request] = []
    upstream_available = True

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if not upstream_available:
            return httpx.Response(503, json={"error": {"message": "unavailable"}})
        return httpx.Response(
            200, json={"data": [{"id": name} for name in upstream_names]}
        )

    upstream = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    monkeypatch.setattr(discovery, "resolve_http_client", lambda _proxy: upstream)

    def preview():
        return client.post(
            "/api/admin/site-model-discoveries",
            headers=admin_headers,
            json={
                "base_url": payload["base_urls"][0]["url"],
                "credentials": payload["credentials"],
                "credential_ids": ["cred-a"],
                "model_pattern": pattern,
            },
        )

    def save_models(items):
        payload["credentials"][0]["model_pattern"] = pattern
        payload["protocols"][0]["models"] = [
            _model("other-key", credential_id="cred-b"),
            *[
                _model(
                    item["model_name"],
                    protocol=item["protocol"],
                    enabled=item["model_name"] != "gpt-kept",
                    context_window=64000 if item["model_name"] == "gpt-kept" else None,
                )
                for item in items
            ],
        ]
        saved = client.put(
            f"/api/admin/sites/{site_id}", headers=admin_headers, json=payload
        )
        assert saved.status_code == 200, saved.text

    try:
        response = preview()
        assert response.status_code == 200, response.text
        assert {(item["model_name"], item["protocol"]) for item in response.json()} == {
            ("private.v1", "openai_chat"),
            ("claude-private", "anthropic"),
        }
        assert _stored_models(client, admin_headers) == {("cred-b", "other-key")}
        save_models(response.json())
        _run_model_sync(
            client, admin_headers, site_ids=[site_id], credential_ids=["cred-a"]
        )
        assert requests == []
        explicit_models = {
            ("cred-a", "private.v1"),
            ("cred-a", "claude-private"),
            ("cred-b", "other-key"),
        }
        assert _stored_models(client, admin_headers) == explicit_models

        pattern += "\n(?i)^gpt-.*"
        response = preview()
        assert response.status_code == 200, response.text
        assert {item["model_name"] for item in response.json()} == {
            "private.v1",
            "claude-private",
            "gpt-kept",
            "gpt-retired",
        }
        save_models(response.json())
        _run_model_sync(client, admin_headers, site_ids=[site_id])
        expected = explicit_models | {("cred-a", "gpt-kept"), ("cred-a", "gpt-retired")}
        assert _stored_models(client, admin_headers) == expected
        site = client.get("/api/admin/sites", headers=admin_headers).json()[0]
        kept = next(
            model
            for model in site["protocols"][0]["models"]
            if model["model_name"] == "gpt-kept"
        )
        assert (kept["enabled"], kept["context_window"]) == (False, 64000)

        upstream_available = False
        assert preview().status_code == 502
        result = _run_model_sync(
            client, admin_headers, site_ids=[site_id], credential_ids=["cred-a"]
        )
        assert {item["status"] for item in result["items"]} == {"failed"}
        assert _stored_models(client, admin_headers) == expected

        upstream_available = True
        upstream_names.clear()
        _run_model_sync(client, admin_headers, site_ids=[site_id])
        assert _stored_models(client, admin_headers) == explicit_models
    finally:
        run_async(upstream.aclose())


@pytest.mark.parametrize("pattern", ["(", "private.v1\n("])
def test_site_rejects_an_invalid_model_pattern(client, admin_headers, pattern) -> None:
    payload = _sync_site_payload(patterns={"cred-a": pattern})

    response = client.post("/api/admin/sites", headers=admin_headers, json=payload)

    assert response.status_code == 422, response.text
    assert "Invalid model pattern" in response.text


@pytest.mark.parametrize(
    "catalog_mode",
    [
        "upstream-error",
        "error-envelope",
        "failed-envelope",
        "invalid-list",
        "invalid-entry",
        "empty",
    ],
)
def test_channel_model_sync_handles_each_key_catalog_independently(
    client,
    admin_headers,
    monkeypatch,
    catalog_mode: str,
) -> None:
    import app.gateway.service.tasks.model_discovery as discovery

    payload = _sync_site_payload(
        patterns={"cred-a": "*", "cred-b": "*"},
        models=[_model("gpt-4o", credential_id="cred-a")],
    )
    _create_sync_site(client, admin_headers, payload)

    async def handler(request: httpx.Request) -> httpx.Response:
        if (
            request.headers.get("authorization", "").removeprefix("Bearer ")
            or request.headers.get("x-api-key")
            or request.headers.get("x-goog-api-key")
        ) != payload["credentials"][0]["api_key"]:
            return httpx.Response(200, json={"data": [{"id": "gpt-4o"}]})
        if catalog_mode == "upstream-error":
            return httpx.Response(503, json={"error": {"message": "unavailable"}})
        if catalog_mode == "error-envelope":
            return httpx.Response(
                200, json={"error": {"message": "failed"}, "data": []}
            )
        if catalog_mode == "failed-envelope":
            return httpx.Response(200, json={"success": False, "data": []})
        if catalog_mode == "invalid-list":
            return httpx.Response(200, json={"data": {}})
        if catalog_mode == "invalid-entry":
            return httpx.Response(200, json={"data": [{}]})
        return httpx.Response(200, json={"data": []})

    upstream = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    monkeypatch.setattr(discovery, "resolve_http_client", lambda _proxy: upstream)
    try:
        result = _run_model_sync(client, admin_headers)
    finally:
        run_async(upstream.aclose())

    assert {(item["credential_id"], item["status"]) for item in result["items"]} == {
        ("cred-a", "updated" if catalog_mode == "empty" else "failed"),
        ("cred-b", "updated"),
    }
    expected = {("cred-b", "gpt-4o")}
    if catalog_mode != "empty":
        expected.add(("cred-a", "gpt-4o"))
    assert _stored_models(client, admin_headers) == expected
    groups = client.get("/api/admin/model-groups", headers=admin_headers).json()
    group = next(group for group in groups if group["name"] == "gpt-4o")
    assert {item["credential_id"] for item in group["items"]} == {
        credential_id for credential_id, _ in expected
    }


@pytest.mark.parametrize(
    ("site_fields", "is_site_disabled", "sync_request"),
    [
        pytest.param({}, True, {}, id="site-disabled"),
        pytest.param({}, False, {"site_ids": ["other-site"]}, id="not-requested"),
    ],
)
def test_channel_model_sync_skips_sites_outside_its_scope(
    client,
    admin_headers,
    monkeypatch,
    site_fields: dict[str, Any],
    is_site_disabled: bool,
    sync_request: dict[str, Any],
) -> None:
    site_id = _create_sync_site(
        client, admin_headers, _sync_site_payload(**site_fields)
    )
    if is_site_disabled:
        disable_response = client.put(
            f"/api/admin/sites/{site_id}/enabled",
            headers=admin_headers,
            json={"enabled": False},
        )
        assert disable_response.status_code == 200, disable_response.text

    async def fail_fetch(_channel: Any) -> list[str]:
        raise AssertionError("skipped sites must not trigger model discovery")

    _patch_upstream_models(monkeypatch, fail_fetch)

    result = _run_model_sync(client, admin_headers, **sync_request)

    assert result["items"] == []


def test_site_rejects_duplicate_models(
    client,
    admin_headers,
) -> None:
    payload = _sync_site_payload(models=[_model("gpt-4o")])
    payload["protocols"][0]["models"].append(_model("gpt-4o"))

    response = client.post("/api/admin/sites", headers=admin_headers, json=payload)

    assert_error(response, 400, "Duplicate model in protocol config")


def test_model_rule_survives_a_backup_round_trip(client, admin_headers) -> None:
    _create_sync_site(
        client,
        admin_headers,
        _sync_site_payload(patterns={"cred-a": "private.v1\n^gpt-4.*"}),
    )

    exported = client.get("/api/admin/backups/export", headers=admin_headers)
    assert exported.status_code == 200, exported.text
    bundle = exported.json()

    client.delete("/api/admin/sites", headers=admin_headers)
    imported = client.post(
        "/api/admin/backups/import",
        headers=admin_headers,
        files={"file": ("backup.json", json.dumps(bundle), "application/json")},
    )
    assert imported.status_code == 200, imported.text

    site = client.get("/api/admin/sites", headers=admin_headers).json()[0]
    patterns = {
        credential["id"]: credential["model_pattern"]
        for credential in site["credentials"]
    }
    assert patterns == {"cred-a": "private.v1\n^gpt-4.*", "cred-b": ""}


def test_sync_removes_group_members_when_a_rule_stops_matching(
    client,
    admin_headers,
    monkeypatch,
) -> None:
    payload = _sync_site_payload(patterns={"cred-a": "^gpt-.*", "cred-b": "^none$"})
    site_id = _create_sync_site(client, admin_headers, payload)

    async def fake_fetch(_channel: Any) -> list[str]:
        return ["gpt-4o"]

    _patch_upstream_models(monkeypatch, fake_fetch)
    _run_model_sync(client, admin_headers)
    assert [
        group["name"]
        for group in client.get("/api/admin/model-groups", headers=admin_headers).json()
    ] == ["gpt-4o"]

    payload["credentials"][0]["model_pattern"] = "^none$"
    saved = client.put(
        f"/api/admin/sites/{site_id}", headers=admin_headers, json=payload
    )
    assert saved.status_code == 200, saved.text
    _run_model_sync(client, admin_headers)

    assert _stored_models(client, admin_headers) == set()
    group = client.get("/api/admin/model-groups", headers=admin_headers).json()[0]
    assert (group["name"], group["items"]) == ("gpt-4o", [])


def test_credential_address_scopes_keep_sources_and_restrict_requests(
    client, admin_headers, monkeypatch, create_gateway_key
) -> None:
    from conftest import gateway_headers

    import app.gateway.service.proxy.proxy_upstream as proxy_upstream
    import app.gateway.service.tasks.model_discovery as discovery

    payload = {
        "name": "Scoped keys",
        "base_urls": [
            {"id": "main", "kind": "default", "url": "https://main.example/v1"},
            {"id": "claude", "kind": "anthropic", "url": "https://claude.example/v1"},
        ],
        "credentials": [
            {"id": "cred-a", "name": "A", "api_key": "test-a", "base_url_ids": None},
            {
                "id": "cred-b",
                "name": "B",
                "api_key": "test-b",
                "base_url_ids": ["claude", "claude"],
            },
        ],
        "protocols": [
            {"id": "pc-main", "base_url_id": "main", "models": []},
            {"id": "pc-claude", "base_url_id": "claude", "models": []},
        ],
    }
    calls: list[tuple[str, str]] = []

    def listing(request: httpx.Request) -> httpx.Response:
        key = (
            request.headers.get("authorization", "").removeprefix("Bearer ")
            or request.headers["x-api-key"]
        )
        calls.append((request.url.host, key))
        return httpx.Response(200, json={"data": [{"id": "scope-model"}]})

    upstream = httpx.AsyncClient(transport=httpx.MockTransport(listing))
    monkeypatch.setattr(discovery, "resolve_http_client", lambda _proxy: upstream)
    try:
        for config, address in zip(
            payload["protocols"], payload["base_urls"], strict=True
        ):
            allowed = [
                key
                for key in payload["credentials"]
                if key["base_url_ids"] is None or address["id"] in key["base_url_ids"]
            ]
            response = client.post(
                "/api/admin/site-model-discoveries",
                headers=admin_headers,
                json={
                    "base_url_id": address["id"],
                    "base_url": address["url"],
                    "endpoint_kind": address["kind"],
                    "credentials": allowed,
                    "credential_ids": [key["id"] for key in allowed],
                },
            )
            assert response.status_code == 200, response.text
            config["models"] = [
                {key: model[key] for key in ("credential_id", "model_name", "protocol")}
                for model in response.json()
            ]
        assert calls == [
            ("main.example", "test-a"),
            ("claude.example", "test-a"),
            ("claude.example", "test-b"),
        ]
        denied = client.post(
            "/api/admin/site-model-discoveries",
            headers=admin_headers,
            json={
                "base_url_id": "main",
                "base_url": payload["base_urls"][0]["url"],
                "credentials": [payload["credentials"][1]],
                "credential_ids": ["cred-b"],
            },
        )
        assert denied.status_code == 400
        assert len(calls) == 3
    finally:
        run_async(upstream.aclose())

    site_id = _create_sync_site(client, admin_headers, payload)
    site = client.get("/api/admin/sites", headers=admin_headers).json()[0]
    assert site["credentials"][1]["base_url_ids"] == ["claude"]
    assert {
        config["base_url_id"]: config["credential_ids"] for config in site["protocols"]
    } == {
        "main": ["cred-a"],
        "claude": ["cred-a", "cred-b"],
    }
    assert sum(len(config["models"]) for config in site["protocols"]) == 3
    group = client.get("/api/admin/model-groups", headers=admin_headers).json()[0]
    assert {item["credential_id"] for item in group["items"]} == {"cred-a", "cred-b"}
    assert (
        client.put(
            f"/api/admin/model-groups/{group['id']}",
            headers=admin_headers,
            json={"strategy": "round_robin"},
        ).status_code
        == 200
    )
    routed: list[tuple[str, str]] = []

    async def send(_client, request, *, stream, body_bytes):
        url = httpx.URL(request.url)
        routed.append((url.host, request.headers["x-api-key"]))
        return httpx.Response(
            200,
            request=httpx.Request("POST", url),
            json={
                "id": "msg-scope",
                "type": "message",
                "role": "assistant",
                "model": "scope-model",
                "content": [{"type": "text", "text": "ok"}],
                "stop_reason": "end_turn",
                "usage": {"input_tokens": 1, "output_tokens": 1},
            },
        )

    monkeypatch.setattr(proxy_upstream, "_send_upstream", send)
    headers = gateway_headers(create_gateway_key())
    for _ in range(4):
        response = client.post(
            "/v1/messages",
            headers=headers,
            json={
                "model": "scope-model",
                "messages": [{"role": "user", "content": "hi"}],
                "max_tokens": 16,
            },
        )
        assert response.status_code == 200, response.text
    assert routed.count(("claude.example", "test-a")) == 2
    assert routed.count(("claude.example", "test-b")) == 2

    bundle = client.get("/api/admin/backups/export", headers=admin_headers).json()
    response = client.post(
        "/api/admin/backups/import",
        headers=admin_headers,
        files={"file": ("scopes.json", json.dumps(bundle), "application/json")},
    )
    assert response.status_code == 200, response.text
    restored = client.get("/api/admin/sites", headers=admin_headers).json()[0]
    assert restored["credentials"] == site["credentials"]
    assert restored["protocols"] == site["protocols"]

    legacy = json.loads(json.dumps(bundle))
    legacy_site = legacy["sites"][0]
    for credential in legacy_site["credentials"]:
        credential.pop("base_url_ids")
        credential["base_url_id"] = "" if credential["id"] == "cred-a" else "claude"
    for config in legacy_site["protocols"]:
        if config["base_url_id"] == "claude":
            config["models"] = [
                model
                for model in config["models"]
                if model["credential_id"] == "cred-b"
            ]
    for group in legacy["groups"]:
        group["items"] = [
            item
            for item in group["items"]
            if not (
                item["credential_id"] == "cred-a"
                and item["channel_id"].startswith("pc-claude_")
            )
        ]
    response = client.post(
        "/api/admin/backups/import",
        headers=admin_headers,
        files={"file": ("legacy-scopes.json", json.dumps(legacy), "application/json")},
    )
    assert response.status_code == 200, response.text
    legacy_restored = client.get("/api/admin/sites", headers=admin_headers).json()[0]
    assert [
        (key["id"], key["base_url_ids"]) for key in legacy_restored["credentials"]
    ] == [
        ("cred-a", ["main"]),
        ("cred-b", ["claude"]),
    ]
    response = client.post(
        "/api/admin/backups/import",
        headers=admin_headers,
        files={"file": ("scopes.json", json.dumps(bundle), "application/json")},
    )
    assert response.status_code == 200, response.text

    payload["base_urls"] = payload["base_urls"][:1]
    payload["protocols"] = payload["protocols"][:1]
    payload["credentials"][1]["base_url_ids"] = []
    response = client.put(
        f"/api/admin/sites/{site_id}", headers=admin_headers, json=payload
    )
    assert response.status_code == 200, response.text
    assert [
        (key["id"], key["base_url_ids"]) for key in response.json()["credentials"]
    ] == [
        ("cred-a", None),
        ("cred-b", []),
    ]
    assert response.json()["protocols"][0]["credential_ids"] == ["cred-a"]
    group = client.get("/api/admin/model-groups", headers=admin_headers).json()[0]
    assert {item["credential_id"] for item in group["items"]} == {"cred-a"}


@pytest.mark.parametrize("use_catalog", [False, True])
def test_model_sync_keeps_address_catalogs_and_reuses_only_allowed_listing(
    client, admin_headers, monkeypatch, use_catalog
) -> None:
    import app.gateway.service.tasks.model_discovery as discovery

    payload = {
        "name": "Address catalogs",
        "base_urls": [
            {"id": "main", "kind": "default", "url": "https://main.example/v1"},
            {"id": "a", "kind": "anthropic", "url": "https://a.example/v1"},
            {"id": "b", "kind": "anthropic", "url": "https://b.example/v1"},
            {"id": "list", "kind": "models", "url": "https://list.example/catalog"},
        ],
        "credentials": [
            {
                "id": "cred-a",
                "name": "A",
                "api_key": "test-a",
                "base_url_ids": None if use_catalog else ["main", "a", "b"],
                "model_pattern": "*",
            },
            {
                "id": "cred-b",
                "name": "B",
                "api_key": "test-b",
                "base_url_ids": ["b"],
                "model_pattern": "*",
            },
        ],
        "protocols": [
            {"id": "pc-main", "base_url_id": "main", "models": []},
            {"id": "pc-a", "base_url_id": "a", "models": []},
            {"id": "pc-b", "base_url_id": "b", "models": []},
        ],
    }
    site_id = _create_sync_site(client, admin_headers, payload)
    failed = False
    seen: list[tuple[str, str, str]] = []

    def listing(request: httpx.Request) -> httpx.Response:
        key = (
            request.headers.get("authorization", "").removeprefix("Bearer ")
            or request.headers.get("x-api-key")
            or request.headers.get("x-goog-api-key")
        )
        seen.append((request.url.host, request.url.path, key))
        if failed and (
            request.url.host == "list.example" or request.url.host == "a.example"
        ):
            return httpx.Response(503, json={"error": {"message": "unavailable"}})
        if request.url.host == "list.example":
            return httpx.Response(
                200,
                json={
                    "data": [
                        {
                            "id": "multi",
                            "supported_endpoints": [
                                "/v1/chat/completions",
                                "/v1/messages",
                            ],
                        },
                        {
                            "id": "chat-only",
                            "supported_endpoints": ["/v1/chat/completions"],
                        },
                    ]
                },
            )
        return httpx.Response(
            200, json={"data": [{"id": request.url.host + ("-next" if failed else "")}]}
        )

    upstream = httpx.AsyncClient(transport=httpx.MockTransport(listing))
    monkeypatch.setattr(discovery, "resolve_http_client", lambda _proxy: upstream)
    try:
        run = _run_model_sync(client, admin_headers, site_ids=[site_id])
        assert all(item["status"] == "updated" for item in run["items"])
        first = client.get("/api/admin/sites", headers=admin_headers).json()[0]
        records = {
            config["base_url_id"]: {
                (model["credential_id"], model["model_name"], model["protocol"])
                for model in config["models"]
            }
            for config in first["protocols"]
        }
        if use_catalog:
            assert seen.count(("list.example", "/catalog", "test-a")) == 1
            assert ("cred-a", "chat-only", "anthropic") not in records["a"]
            assert records["a"] == {("cred-a", "multi", "anthropic")}
            assert records["main"] == {
                ("cred-a", "multi", "openai_chat"),
                ("cred-a", "multi", "anthropic"),
                ("cred-a", "chat-only", "openai_chat"),
            }
        else:
            assert {host for host, _, _ in seen} == {
                "main.example",
                "a.example",
                "b.example",
            }
            assert records["a"] == {("cred-a", "a.example", "anthropic")}
            assert records["b"] == {
                ("cred-a", "b.example", "anthropic"),
                ("cred-b", "b.example", "anthropic"),
            }
        assert ("list.example", "/catalog", "test-b") not in seen

        failed = True
        seen.clear()
        run = _run_model_sync(client, admin_headers, site_ids=[site_id])
        assert any(item["status"] == "failed" for item in run["items"])
        second = client.get("/api/admin/sites", headers=admin_headers).json()[0]
        after = {config["base_url_id"]: config for config in second["protocols"]}
        before = {config["base_url_id"]: config for config in first["protocols"]}
        assert after["a"]["models"] == before["a"]["models"]
        if use_catalog:
            assert after["main"]["models"] == before["main"]["models"]
            assert {
                model["model_name"]
                for model in after["b"]["models"]
                if model["credential_id"] == "cred-a"
            } == {"multi"}
            assert sum(host == "list.example" for host, _, _ in seen) == 3
        assert {
            model["model_name"]
            for model in after["b"]["models"]
            if model["credential_id"] == "cred-b"
        } == {"b.example-next"}
    finally:
        run_async(upstream.aclose())
