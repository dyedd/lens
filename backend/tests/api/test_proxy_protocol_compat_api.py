from __future__ import annotations

import json
from typing import Any

import httpx
import pytest
from conftest import gateway_headers, run_async, valid_site_payload

from app.core.runtime_channel_ids import compose_runtime_channel_id
from app.models.protocols import ProtocolKind
from app.models.settings import SettingItem
from app.persistence.settings_keys import SETTING_RELAY_LOG_BODY_ENABLED


def _chat_group_item(model_name: str) -> dict[str, Any]:
    return {
        "channel_id": compose_runtime_channel_id("pc-1", ProtocolKind.OPENAI_CHAT),
        "credential_id": "cred-1",
        "model_name": model_name,
        "enabled": True,
    }


def _anthropic_group_item(model_name: str) -> dict[str, Any]:
    return {
        "channel_id": compose_runtime_channel_id("pc-1", ProtocolKind.ANTHROPIC),
        "credential_id": "cred-1",
        "model_name": model_name,
        "enabled": True,
    }


def _stream_payloads(response_text: str) -> list[dict[str, Any]]:
    payloads: list[dict[str, Any]] = []
    for block in response_text.split("\n\n"):
        data_lines = [
            line[6:] for line in block.splitlines() if line.startswith("data: ")
        ]
        for data in data_lines:
            if data != "[DONE]":
                payload = json.loads(data)
                if isinstance(payload, dict):
                    payloads.append(payload)
    return payloads


def test_same_protocol_responses_request_preserves_body_shape(
    client,
    monkeypatch,
    create_site,
    create_model_group,
    create_gateway_key,
) -> None:
    import app.gateway.service.proxy_upstream as proxy_upstream

    captured_body: dict[str, Any] = {}

    async def fake_send_upstream(
        _client: httpx.AsyncClient,
        upstream: Any,
        *,
        stream: bool,
        body_bytes: bytes,
    ) -> httpx.Response:
        assert not stream
        captured_body.update(json.loads(body_bytes))
        return httpx.Response(
            500,
            json={"error": {"message": "stop after capture"}},
            request=httpx.Request("POST", upstream.url),
        )

    monkeypatch.setattr(proxy_upstream, "_send_upstream", fake_send_upstream)
    create_site(
        valid_site_payload(
            protocols=[ProtocolKind.OPENAI_RESPONSES.value],
            model_name="responses-upstream",
        )
    )
    create_model_group(
        name="responses-client",
        items=[
            {
                "channel_id": compose_runtime_channel_id(
                    "pc-1", ProtocolKind.OPENAI_RESPONSES
                ),
                "credential_id": "cred-1",
                "model_name": "responses-upstream",
                "enabled": True,
            }
        ],
    )
    body = {
        "model": "responses-client",
        "input": "  preserve this input exactly  ",
        "tools": [{"type": "function", "name": "lookup", "parameters": {}}],
        "tool_choice": "auto",
    }

    response = client.post(
        "/v1/responses",
        headers=gateway_headers(create_gateway_key()),
        json=body,
    )

    assert response.status_code == 502, response.text
    assert captured_body == {**body, "model": "responses-upstream"}


@pytest.mark.parametrize(
    ("client_protocol", "route"),
    [
        (ProtocolKind.ANTHROPIC, "/v1/messages"),
        (ProtocolKind.OPENAI_CHAT, "/v1/chat/completions"),
    ],
)
def test_glm_chat_requests_rewrite_reasoning_controls(
    client,
    monkeypatch,
    create_site,
    create_model_group,
    create_gateway_key,
    client_protocol: ProtocolKind,
    route: str,
) -> None:
    import app.gateway.service.proxy_upstream as proxy_upstream

    captured_body: dict[str, Any] = {}

    async def fake_send_upstream(
        _client: httpx.AsyncClient,
        upstream: Any,
        *,
        stream: bool,
        body_bytes: bytes,
    ) -> httpx.Response:
        assert not stream
        captured_body.update(json.loads(body_bytes))
        return httpx.Response(
            500,
            json={"error": {"message": "stop after capture"}},
            request=httpx.Request("POST", upstream.url),
        )

    monkeypatch.setattr(proxy_upstream, "_send_upstream", fake_send_upstream)
    create_site(
        valid_site_payload(
            protocols=[ProtocolKind.OPENAI_CHAT.value],
            model_name="z-ai/glm-5.2",
        )
    )
    create_model_group(
        name="glm-client",
        items=[_chat_group_item("z-ai/glm-5.2")],
    )
    key = create_gateway_key()

    response = client.post(
        route,
        headers=gateway_headers(key),
        json={
            "model": "glm-client",
            "max_tokens": 32000,
            "thinking": {"type": "enabled", "budget_tokens": 31999},
            "output_config": {"effort": "max"},
            "messages": [{"role": "user", "content": "hello"}],
        },
    )

    assert response.status_code == 502, response.text
    assert captured_body["model"] == "z-ai/glm-5.2"
    assert captured_body["max_tokens"] == 32000
    assert captured_body["thinking"] == {"type": "enabled"}
    assert captured_body["reasoning_effort"] == "max"
    assert "output_config" not in captured_body


def test_openai_chat_stream_logs_kimi_sse_as_json(
    client,
    monkeypatch,
    app_state,
    create_site,
    create_model_group,
    create_gateway_key,
) -> None:
    import app.gateway.service.proxy_upstream as proxy_upstream
    import app.gateway.service.streaming.stream_logging as stream_logging

    stream_body = (
        ": keep-alive\n\n"
        'data: {"choices":[{"delta":{"content":"","reasoning":"用户","reasoning_details":[{"format":"unknown","index":0,"text":"用户","type":"reasoning.text"}],"role":"assistant","tool_calls":[{"function":{"arguments":"}"},"index":0}]},"finish_reason":null,"index":0}],"model":"kimi-k3","object":"chat.completion.chunk"}'
        "\n\n"
        'data: {"choices":[{"delta":{"content":"","reasoning":null,"role":"assistant"},"finish_reason":"tool_calls","index":0}],"model":"kimi-k3","object":"chat.completion.chunk"}'
        "\n\n"
        'data: {"choices":[{"delta":{"content":"","role":"assistant"},"finish_reason":"tool_calls","index":0}],"model":"kimi-k3","object":"chat.completion.chunk","usage":{"completion_tokens":346,"prompt_tokens":61105,"total_tokens":61451}}'
        "\n\n"
        "data: [DONE]\n\n"
    )

    async def fake_send_upstream(
        _client: httpx.AsyncClient,
        upstream: Any,
        *,
        stream: bool,
        body_bytes: bytes,
    ) -> httpx.Response:
        assert stream
        return httpx.Response(
            200,
            content=stream_body.encode(),
            headers={"content-type": "text/event-stream"},
            request=httpx.Request("POST", upstream.url),
        )

    monkeypatch.setattr(proxy_upstream, "_send_upstream", fake_send_upstream)
    monkeypatch.setattr(stream_logging, "app_state", app_state)
    run_async(
        app_state.settings_repo.upsert_settings(
            [SettingItem(key=SETTING_RELAY_LOG_BODY_ENABLED, value="true")]
        )
    )
    create_site(
        valid_site_payload(
            protocols=[ProtocolKind.OPENAI_CHAT.value],
            model_name="kimi-k3",
        )
    )
    create_model_group(
        name="kimi-k3",
        items=[_chat_group_item("kimi-k3")],
    )
    key = create_gateway_key()

    response = client.post(
        "/v1/chat/completions",
        headers=gateway_headers(key),
        json={"model": "kimi-k3", "messages": [], "stream": True},
    )

    assert response.status_code == 200, response.text
    assert response.text == stream_body
    request_log_item = run_async(
        app_state.request_log_store.list_request_log_page()
    ).items[0]
    request_log = run_async(
        app_state.request_log_store.get_request_log(request_log_item.id)
    )
    assert request_log.input_tokens == 61105
    assert request_log.output_tokens == 346
    assert request_log.total_tokens == 61451
    logged_chunks = json.loads(request_log.response_content or "null")
    assert isinstance(logged_chunks, list)
    assert logged_chunks[0]["choices"][0]["delta"]["reasoning"] == "用户"


def test_anthropic_stream_with_openai_semantic_usage_does_not_double_count_cache(
    client,
    monkeypatch,
    app_state,
    create_site,
    create_model_group,
    create_gateway_key,
) -> None:
    import app.gateway.service.proxy_upstream as proxy_upstream
    import app.gateway.service.streaming.stream_logging as stream_logging

    # GLM-style upstream: input_tokens follows OpenAI prompt semantics, where
    # cache is already included, and billing_usage.semantic marks that.
    stream_body = (
        'event: message_start\ndata: {"type":"message_start","message":{"type":"message","model":"glm-5.3-flash","usage":{"input_tokens":51630,"cache_creation_input_tokens":0,"cache_read_input_tokens":51456,"output_tokens":0,"billing_usage":{"source":"oai_chat","semantic":"openai","openai_usage":{"prompt_tokens":51630,"completion_tokens":384,"total_tokens":52014}}},"role":"assistant","id":"msg_glm","content":[]}}\n\n'
        'event: content_block_delta\ndata: {"type":"content_block_delta","index":0,"delta":{"type":"text_delta","text":"ok"}}\n\n'
        'event: message_delta\ndata: {"type":"message_delta","delta":{"stop_reason":"end_turn","stop_sequence":null},"usage":{"output_tokens":384}}\n\n'
        'event: message_stop\ndata: {"type":"message_stop"}\n\n'
    )

    async def fake_send_upstream(
        _client: httpx.AsyncClient,
        upstream: Any,
        *,
        stream: bool,
        body_bytes: bytes,
    ) -> httpx.Response:
        assert stream
        return httpx.Response(
            200,
            content=stream_body.encode(),
            headers={"content-type": "text/event-stream"},
            request=httpx.Request("POST", upstream.url),
        )

    monkeypatch.setattr(proxy_upstream, "_send_upstream", fake_send_upstream)
    monkeypatch.setattr(stream_logging, "app_state", app_state)
    create_site(
        valid_site_payload(
            protocols=[ProtocolKind.ANTHROPIC.value],
            model_name="glm-5.3-flash",
        )
    )
    create_model_group(
        name="glm-5.3-flash",
        items=[_anthropic_group_item("glm-5.3-flash")],
    )
    key = create_gateway_key()

    response = client.post(
        "/v1/messages",
        headers=gateway_headers(key),
        json={
            "model": "glm-5.3-flash",
            "messages": [],
            "max_tokens": 16,
            "stream": True,
        },
    )

    assert response.status_code == 200, response.text
    request_log_item = run_async(
        app_state.request_log_store.list_request_log_page()
    ).items[0]
    request_log = run_async(
        app_state.request_log_store.get_request_log(request_log_item.id)
    )
    assert request_log.input_tokens == 51630
    assert request_log.cache_read_input_tokens == 51456
    assert request_log.output_tokens == 384
    assert request_log.total_tokens == 52014


def test_openai_chat_stream_repairs_reused_tool_call_index(
    client,
    monkeypatch,
    create_site,
    create_model_group,
    create_gateway_key,
) -> None:
    import app.gateway.service.proxy_upstream as proxy_upstream

    upstream_payloads = [
        {
            "id": "chatcmpl-tools",
            "object": "chat.completion.chunk",
            "model": "gemini-3.1-pro",
            "choices": [
                {
                    "index": 0,
                    "delta": {
                        "tool_calls": [
                            {
                                "index": 0,
                                "id": "toolu-first",
                                "type": "function",
                                "function": {"name": "glob", "arguments": ""},
                            }
                        ]
                    },
                    "finish_reason": None,
                }
            ],
        },
        {
            "id": "chatcmpl-tools",
            "object": "chat.completion.chunk",
            "model": "gemini-3.1-pro",
            "choices": [
                {
                    "index": 0,
                    "delta": {
                        "tool_calls": [
                            {
                                "index": 0,
                                "function": {
                                    "name": "",
                                    "arguments": '{"path":"","pattern":"**/*"}',
                                },
                            }
                        ]
                    },
                    "finish_reason": None,
                }
            ],
        },
        {
            "id": "chatcmpl-tools",
            "object": "chat.completion.chunk",
            "model": "gemini-3.1-pro",
            "choices": [
                {
                    "index": 0,
                    "delta": {
                        "tool_calls": [
                            {
                                "index": 0,
                                "function": {
                                    "name": "",
                                    "arguments": '{"path":"content/wiki","pattern":""}',
                                },
                            }
                        ]
                    },
                    "finish_reason": None,
                }
            ],
        },
        {
            "id": "chatcmpl-tools",
            "object": "chat.completion.chunk",
            "model": "gemini-3.1-pro",
            "choices": [
                {
                    "index": 0,
                    "delta": {},
                    "finish_reason": "tool_calls",
                }
            ],
        },
    ]
    stream_body = (
        "".join(
            f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"
            for payload in upstream_payloads
        )
        + "data: [DONE]\n\n"
    )

    async def fake_send_upstream(
        _client: httpx.AsyncClient,
        upstream: Any,
        *,
        stream: bool,
        body_bytes: bytes,
    ) -> httpx.Response:
        assert stream
        return httpx.Response(
            200,
            content=stream_body.encode(),
            headers={"content-type": "text/event-stream"},
            request=httpx.Request("POST", upstream.url),
        )

    monkeypatch.setattr(proxy_upstream, "_send_upstream", fake_send_upstream)
    create_site(
        valid_site_payload(
            protocols=[ProtocolKind.OPENAI_CHAT.value],
            model_name="gemini-3.1-pro",
        )
    )
    create_model_group(
        name="gemini-3.1-pro",
        items=[_chat_group_item("gemini-3.1-pro")],
    )

    response = client.post(
        "/v1/chat/completions",
        headers=gateway_headers(create_gateway_key()),
        json={
            "model": "gemini-3.1-pro",
            "messages": [{"role": "user", "content": "call glob twice"}],
            "stream": True,
        },
    )

    assert response.status_code == 200, response.text
    chunks = _stream_payloads(response.text)
    tool_deltas = [
        tool_call
        for chunk in chunks
        for choice in chunk["choices"]
        for tool_call in choice["delta"].get("tool_calls", [])
    ]
    assert [tool_call["index"] for tool_call in tool_deltas] == [0, 0, 1]
    assert tool_deltas[0]["id"] == "toolu-first"
    assert tool_deltas[2]["id"].startswith("call_")
    assert json.loads(tool_deltas[1]["function"]["arguments"]) == {
        "path": "",
        "pattern": "**/*",
    }
    assert json.loads(tool_deltas[2]["function"]["arguments"]) == {
        "path": "content/wiki",
        "pattern": "",
    }


def test_openai_chat_stream_preserves_split_tool_call_arguments(
    client,
    monkeypatch,
    create_site,
    create_model_group,
    create_gateway_key,
) -> None:
    import app.gateway.service.proxy_upstream as proxy_upstream

    upstream_payloads = [
        {
            "id": "chatcmpl-split",
            "object": "chat.completion.chunk",
            "model": "tool-model",
            "choices": [
                {
                    "index": 0,
                    "delta": {
                        "tool_calls": [
                            {
                                "index": 0,
                                "id": "toolu-split",
                                "type": "function",
                                "function": {"name": "glob", "arguments": ""},
                            }
                        ]
                    },
                    "finish_reason": None,
                }
            ],
        },
        {
            "id": "chatcmpl-split",
            "object": "chat.completion.chunk",
            "model": "tool-model",
            "choices": [
                {
                    "index": 0,
                    "delta": {
                        "tool_calls": [
                            {
                                "index": 0,
                                "function": {"arguments": '{"path":"con'},
                            }
                        ]
                    },
                    "finish_reason": None,
                }
            ],
        },
        {
            "id": "chatcmpl-split",
            "object": "chat.completion.chunk",
            "model": "tool-model",
            "choices": [
                {
                    "index": 0,
                    "delta": {
                        "tool_calls": [
                            {
                                "index": 0,
                                "function": {"arguments": 'tent/wiki"}'},
                            }
                        ]
                    },
                    "finish_reason": None,
                }
            ],
        },
        {
            "id": "chatcmpl-split",
            "object": "chat.completion.chunk",
            "model": "tool-model",
            "choices": [
                {
                    "index": 0,
                    "delta": {},
                    "finish_reason": "tool_calls",
                }
            ],
        },
    ]
    stream_body = (
        "".join(f"data: {json.dumps(payload)}\n\n" for payload in upstream_payloads)
        + "data: [DONE]\n\n"
    )

    async def fake_send_upstream(
        _client: httpx.AsyncClient,
        upstream: Any,
        *,
        stream: bool,
        body_bytes: bytes,
    ) -> httpx.Response:
        assert stream
        return httpx.Response(
            200,
            content=stream_body.encode(),
            headers={"content-type": "text/event-stream"},
            request=httpx.Request("POST", upstream.url),
        )

    monkeypatch.setattr(proxy_upstream, "_send_upstream", fake_send_upstream)
    create_site(
        valid_site_payload(
            protocols=[ProtocolKind.OPENAI_CHAT.value],
            model_name="tool-model",
        )
    )
    create_model_group(
        name="tool-model",
        items=[_chat_group_item("tool-model")],
    )

    response = client.post(
        "/v1/chat/completions",
        headers=gateway_headers(create_gateway_key()),
        json={"model": "tool-model", "messages": [], "stream": True},
    )

    assert response.status_code == 200, response.text
    chunks = _stream_payloads(response.text)
    tool_deltas = [
        tool_call
        for chunk in chunks
        for choice in chunk["choices"]
        for tool_call in choice["delta"].get("tool_calls", [])
    ]
    assert [tool_call["index"] for tool_call in tool_deltas] == [0, 0, 0]
    assert "id" not in tool_deltas[1]
    assert "id" not in tool_deltas[2]


@pytest.mark.parametrize(
    ("route", "client_protocol"),
    [
        ("/v1/messages", ProtocolKind.ANTHROPIC),
        ("/v1/responses", ProtocolKind.OPENAI_RESPONSES),
    ],
)
def test_chat_upstream_repeated_tool_index_converts_to_separate_calls(
    client,
    monkeypatch,
    create_site,
    create_model_group,
    create_gateway_key,
    route: str,
    client_protocol: ProtocolKind,
) -> None:
    import app.gateway.service.proxy_upstream as proxy_upstream

    upstream_payloads = [
        {
            "id": "chatcmpl-cross-protocol",
            "model": "tool-model",
            "choices": [
                {
                    "index": 0,
                    "delta": {
                        "tool_calls": [
                            {
                                "index": 0,
                                "id": "toolu-first",
                                "type": "function",
                                "function": {"name": "glob", "arguments": ""},
                            }
                        ]
                    },
                    "finish_reason": None,
                }
            ],
        },
        {
            "id": "chatcmpl-cross-protocol",
            "model": "tool-model",
            "choices": [
                {
                    "index": 0,
                    "delta": {
                        "tool_calls": [
                            {
                                "index": 0,
                                "function": {
                                    "arguments": '{"path":"","pattern":"**/*"}',
                                },
                            }
                        ]
                    },
                    "finish_reason": None,
                }
            ],
        },
        {
            "id": "chatcmpl-cross-protocol",
            "model": "tool-model",
            "choices": [
                {
                    "index": 0,
                    "delta": {
                        "tool_calls": [
                            {
                                "index": 0,
                                "function": {
                                    "arguments": '{"path":"content/wiki","pattern":""}',
                                },
                            }
                        ]
                    },
                    "finish_reason": "tool_calls",
                }
            ],
        },
    ]
    stream_body = (
        "".join(f"data: {json.dumps(payload)}\n\n" for payload in upstream_payloads)
        + "data: [DONE]\n\n"
    )

    async def fake_send_upstream(
        _client: httpx.AsyncClient,
        upstream: Any,
        *,
        stream: bool,
        body_bytes: bytes,
    ) -> httpx.Response:
        assert stream
        return httpx.Response(
            200,
            content=stream_body.encode(),
            headers={"content-type": "text/event-stream"},
            request=httpx.Request("POST", upstream.url),
        )

    monkeypatch.setattr(proxy_upstream, "_send_upstream", fake_send_upstream)
    create_site(
        valid_site_payload(
            protocols=[ProtocolKind.OPENAI_CHAT.value],
            model_name="tool-model",
        )
    )
    model_name = f"chat-upstream-{client_protocol.value}"
    create_model_group(name=model_name, items=[_chat_group_item("tool-model")])

    request_body = {
        "model": model_name,
        "stream": True,
        "messages": [{"role": "user", "content": "call glob twice"}],
    }
    if client_protocol == ProtocolKind.OPENAI_RESPONSES:
        request_body = {"model": model_name, "stream": True, "input": "call glob twice"}
    else:
        request_body["max_tokens"] = 64

    response = client.post(
        route,
        headers=gateway_headers(create_gateway_key()),
        json=request_body,
    )

    assert response.status_code == 200, response.text
    payloads = _stream_payloads(response.text)
    if client_protocol == ProtocolKind.ANTHROPIC:
        starts = [
            payload["content_block"]
            for payload in payloads
            if payload.get("type") == "content_block_start"
            and payload.get("content_block", {}).get("type") == "tool_use"
        ]
        assert len(starts) == 2
        assert starts[0]["id"] == "toolu-first"
        assert starts[1]["id"].startswith("call_")
        deltas = [
            payload["delta"]["partial_json"]
            for payload in payloads
            if payload.get("type") == "content_block_delta"
            and payload.get("delta", {}).get("type") == "input_json_delta"
        ]
        assert [json.loads(delta) for delta in deltas] == [
            {"path": "", "pattern": "**/*"},
            {"path": "content/wiki", "pattern": ""},
        ]
    else:
        added = [
            payload["item"]
            for payload in payloads
            if payload.get("type") == "response.output_item.added"
            and payload.get("item", {}).get("type") == "function_call"
        ]
        assert len(added) == 2
        assert added[0]["call_id"] == "toolu-first"
        assert added[1]["call_id"].startswith("call_")
        terminal = next(
            payload
            for payload in payloads
            if payload.get("type") == "response.completed"
        )
        output = [
            item
            for item in terminal["response"]["output"]
            if item.get("type") == "function_call"
        ]
        assert [json.loads(item["arguments"]) for item in output] == [
            {"path": "", "pattern": "**/*"},
            {"path": "content/wiki", "pattern": ""},
        ]
