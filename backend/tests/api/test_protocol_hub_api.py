"""Cross-protocol coverage for pairs the unified-protocol hub newly enables.

Each test drives the gateway end to end, stubbing only the network edge, and
asserts both the upstream body the channel received and the client-visible
response.
"""

from __future__ import annotations

import json
from typing import Any

import httpx
from conftest import gateway_headers, valid_site_payload

from app.core.runtime_channel_ids import compose_runtime_channel_id
from app.models.protocols import ProtocolKind


def _single_upstream_group(
    create_site: Any,
    create_model_group: Any,
    *,
    upstream_protocol: ProtocolKind,
    group_name: str,
    model_name: str = "upstream-model",
) -> None:
    """Point a client group at a single upstream of the given protocol."""
    create_site(
        valid_site_payload(protocols=[upstream_protocol.value], model_name=model_name)
    )
    create_model_group(
        name=group_name,
        items=[
            {
                "channel_id": compose_runtime_channel_id("pc-1", upstream_protocol),
                "credential_id": "cred-1",
                "model_name": model_name,
                "enabled": True,
            }
        ],
    )


def _capture_json_upstream(
    monkeypatch: Any,
    captured: dict[str, Any],
    payload: dict[str, Any],
) -> None:
    import app.gateway.service.proxy_upstream as proxy_upstream

    async def fake_send_upstream(
        _client: httpx.AsyncClient,
        upstream: Any,
        *,
        stream: bool,
        body_bytes: bytes,
    ) -> httpx.Response:
        captured["url"] = upstream.url
        captured["stream"] = stream
        captured["body"] = json.loads(body_bytes)
        captured["headers"] = dict(upstream.headers)
        return httpx.Response(
            200,
            json=payload,
            headers={"content-type": "application/json"},
            request=httpx.Request("POST", upstream.url),
        )

    monkeypatch.setattr(proxy_upstream, "_send_upstream", fake_send_upstream)


def _capture_stream_upstream(
    monkeypatch: Any,
    captured: dict[str, Any],
    frames: list[dict[str, Any]],
) -> None:
    import app.gateway.service.proxy_upstream as proxy_upstream

    body = (
        "".join(f"data: {json.dumps(frame)}\n\n" for frame in frames)
        + "data: [DONE]\n\n"
    )

    async def fake_send_upstream(
        _client: httpx.AsyncClient,
        upstream: Any,
        *,
        stream: bool,
        body_bytes: bytes,
    ) -> httpx.Response:
        captured["url"] = upstream.url
        captured["stream"] = stream
        captured["body"] = json.loads(body_bytes)
        captured["headers"] = dict(upstream.headers)
        return httpx.Response(
            200,
            content=body.encode(),
            headers={"content-type": "text/event-stream"},
            request=httpx.Request("POST", upstream.url),
        )

    monkeypatch.setattr(proxy_upstream, "_send_upstream", fake_send_upstream)


def test_anthropic_passthrough_drops_foreign_reasoning_signature(
    client: Any,
    monkeypatch: Any,
    create_site: Any,
    create_model_group: Any,
    create_gateway_key: Any,
) -> None:
    """A Responses-issued reasoning envelope must not be replayed to Anthropic."""
    captured: dict[str, Any] = {}
    _capture_json_upstream(
        monkeypatch,
        captured,
        {
            "id": "msg_1",
            "type": "message",
            "role": "assistant",
            "model": "upstream-model",
            "content": [{"type": "text", "text": "ok"}],
            "stop_reason": "end_turn",
            "usage": {"input_tokens": 1, "output_tokens": 1},
        },
    )
    _single_upstream_group(
        create_site,
        create_model_group,
        upstream_protocol=ProtocolKind.ANTHROPIC,
        group_name="anthropic-passthrough",
    )

    response = client.post(
        "/v1/messages",
        headers=gateway_headers(create_gateway_key()),
        json={
            "model": "anthropic-passthrough",
            "max_tokens": 32,
            "messages": [
                {"role": "user", "content": "hello"},
                {
                    "role": "assistant",
                    "content": [
                        {
                            "type": "thinking",
                            "thinking": "prior thought",
                            "signature": "lens-responses-reasoning-v1:AAAA",
                        },
                        {"type": "text", "text": "prior answer"},
                    ],
                },
                {"role": "user", "content": "again"},
            ],
        },
    )

    assert response.status_code == 200, response.text
    forwarded = captured["body"]["messages"]
    blocks = [
        block
        for message in forwarded
        for block in (
            message.get("content") if isinstance(message.get("content"), list) else []
        )
        if isinstance(block, dict)
    ]
    assert not [
        block
        for block in blocks
        if block.get("type") in {"thinking", "redacted_thinking"}
        and str(block.get("signature") or block.get("data") or "").startswith(
            "lens-responses-reasoning-v1:"
        )
    ]


def test_responses_passthrough_drops_reasoning_sealed_by_another_provider(
    client: Any,
    monkeypatch: Any,
    create_site: Any,
    create_model_group: Any,
    create_gateway_key: Any,
) -> None:
    """A blob sealed by one provider must not be replayed to another."""
    captured: dict[str, Any] = {}
    _capture_json_upstream(
        monkeypatch,
        captured,
        {
            "id": "resp_1",
            "object": "response",
            "status": "completed",
            "model": "upstream-model",
            "output": [
                {
                    "type": "message",
                    "id": "msg_1",
                    "role": "assistant",
                    "content": [{"type": "output_text", "text": "ok"}],
                }
            ],
            "usage": {"input_tokens": 1, "output_tokens": 1},
        },
    )
    _single_upstream_group(
        create_site,
        create_model_group,
        upstream_protocol=ProtocolKind.OPENAI_RESPONSES,
        group_name="responses-passthrough",
        model_name="claude-3-5-sonnet",
    )

    response = client.post(
        "/v1/responses",
        headers=gateway_headers(create_gateway_key()),
        json={
            "model": "responses-passthrough",
            "input": [
                {
                    "type": "reasoning",
                    "id": "rs_1",
                    "summary": [{"type": "summary_text", "text": "prior thought"}],
                    "encrypted_content": "gAAAA-openai-sealed",
                },
                {"type": "message", "role": "user", "content": "hi"},
            ],
        },
    )

    assert response.status_code == 200, response.text
    types = [item.get("type") for item in captured["body"]["input"]]
    assert "reasoning" not in types
    assert "message" in types


def test_chat_client_reaches_anthropic_upstream(
    client: Any,
    monkeypatch: Any,
    create_site: Any,
    create_model_group: Any,
    create_gateway_key: Any,
) -> None:
    captured: dict[str, Any] = {}
    _capture_json_upstream(
        monkeypatch,
        captured,
        {
            "id": "msg_1",
            "type": "message",
            "role": "assistant",
            "model": "upstream-model",
            "content": [{"type": "text", "text": "hi there"}],
            "stop_reason": "end_turn",
            "usage": {"input_tokens": 3, "output_tokens": 2},
        },
    )
    _single_upstream_group(
        create_site,
        create_model_group,
        upstream_protocol=ProtocolKind.ANTHROPIC,
        group_name="chat-to-anthropic",
    )

    response = client.post(
        "/v1/chat/completions",
        headers=gateway_headers(create_gateway_key()),
        json={
            "model": "chat-to-anthropic",
            "messages": [
                {"role": "system", "content": "be brief"},
                {"role": "user", "content": "hello"},
            ],
        },
    )

    assert response.status_code == 200, response.text
    assert captured["url"] == "https://upstream.example/v1/messages"
    assert captured["body"]["system"] == "be brief"
    assert captured["body"]["messages"] == [{"role": "user", "content": "hello"}]
    # Anthropic requires max_tokens on every request; the hub supplies a default.
    assert captured["body"]["max_tokens"] > 0
    assert response.json()["choices"][0]["message"]["content"] == "hi there"


def test_chat_client_streams_from_anthropic_upstream(
    client: Any,
    monkeypatch: Any,
    create_site: Any,
    create_model_group: Any,
    create_gateway_key: Any,
) -> None:
    captured: dict[str, Any] = {}
    _capture_stream_upstream(
        monkeypatch,
        captured,
        [
            {
                "type": "message_start",
                "message": {
                    "id": "msg_1",
                    "model": "upstream-model",
                    "usage": {"input_tokens": 3, "output_tokens": 0},
                },
            },
            {
                "type": "content_block_start",
                "index": 0,
                "content_block": {"type": "text", "text": ""},
            },
            {
                "type": "content_block_delta",
                "index": 0,
                "delta": {"type": "text_delta", "text": "hi"},
            },
            {"type": "content_block_stop", "index": 0},
            {
                "type": "message_delta",
                "delta": {"stop_reason": "end_turn"},
                "usage": {"output_tokens": 2},
            },
            {"type": "message_stop"},
        ],
    )
    _single_upstream_group(
        create_site,
        create_model_group,
        upstream_protocol=ProtocolKind.ANTHROPIC,
        group_name="chat-stream-anthropic",
    )

    response = client.post(
        "/v1/chat/completions",
        headers=gateway_headers(create_gateway_key()),
        json={
            "model": "chat-stream-anthropic",
            "messages": [{"role": "user", "content": "hello"}],
            "stream": True,
            "stream_options": {"include_usage": True},
        },
    )

    assert response.status_code == 200, response.text
    assert captured["stream"] is True
    assert '"content": "hi"' in response.text
    assert '"finish_reason": "stop"' in response.text
    assert '"usage":' in response.text


def test_responses_client_reaches_anthropic_upstream(
    client: Any,
    monkeypatch: Any,
    create_site: Any,
    create_model_group: Any,
    create_gateway_key: Any,
) -> None:
    captured: dict[str, Any] = {}
    _capture_json_upstream(
        monkeypatch,
        captured,
        {
            "id": "msg_1",
            "type": "message",
            "role": "assistant",
            "model": "upstream-model",
            "content": [{"type": "text", "text": "hi there"}],
            "stop_reason": "end_turn",
            "usage": {"input_tokens": 3, "output_tokens": 2},
        },
    )
    _single_upstream_group(
        create_site,
        create_model_group,
        upstream_protocol=ProtocolKind.ANTHROPIC,
        group_name="responses-to-anthropic",
    )

    response = client.post(
        "/v1/responses",
        headers=gateway_headers(create_gateway_key()),
        json={
            "model": "responses-to-anthropic",
            "input": [
                {"role": "system", "content": "be brief"},
                {"role": "user", "content": "hello"},
            ],
        },
    )

    assert response.status_code == 200, response.text
    assert captured["url"] == "https://upstream.example/v1/messages"
    assert captured["body"]["system"] == "be brief"
    assert captured["body"]["messages"] == [{"role": "user", "content": "hello"}]
    body = response.json()
    assert body["status"] == "completed"
    assert body["output"][0]["content"][0]["text"] == "hi there"


def test_gemini_client_reaches_chat_upstream(
    client: Any,
    monkeypatch: Any,
    create_site: Any,
    create_model_group: Any,
    create_gateway_key: Any,
) -> None:
    captured: dict[str, Any] = {}
    _capture_json_upstream(
        monkeypatch,
        captured,
        {
            "id": "chatcmpl-1",
            "object": "chat.completion",
            "model": "upstream-model",
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": "hi there"},
                    "finish_reason": "stop",
                }
            ],
            "usage": {"prompt_tokens": 3, "completion_tokens": 2, "total_tokens": 5},
        },
    )
    _single_upstream_group(
        create_site,
        create_model_group,
        upstream_protocol=ProtocolKind.OPENAI_CHAT,
        group_name="gemini-to-chat",
    )

    response = client.post(
        "/v1beta/interactions",
        headers=gateway_headers(create_gateway_key()),
        json={
            "model": "gemini-to-chat",
            "input": [
                {
                    "type": "user_input",
                    "content": [{"type": "text", "text": "hello"}],
                }
            ],
        },
    )

    assert response.status_code == 200, response.text
    assert captured["url"] == "https://upstream.example/v1/chat/completions"
    assert captured["body"]["messages"] == [{"role": "user", "content": "hello"}]
    step = response.json()["steps"][0]
    assert step["content"] == [{"type": "text", "text": "hi there"}]


def test_chat_client_reaches_gemini_interactions_upstream(
    client: Any,
    monkeypatch: Any,
    create_site: Any,
    create_model_group: Any,
    create_gateway_key: Any,
) -> None:
    captured: dict[str, Any] = {}
    _capture_json_upstream(
        monkeypatch,
        captured,
        {
            "id": "interaction_1",
            "object": "interaction",
            "model": "upstream-model",
            "status": "completed",
            "steps": [
                {
                    "type": "model_output",
                    "content": [{"type": "text", "text": "hi there"}],
                }
            ],
            "usage": {
                "total_input_tokens": 3,
                "total_output_tokens": 2,
                "total_tokens": 5,
            },
        },
    )
    _single_upstream_group(
        create_site,
        create_model_group,
        upstream_protocol=ProtocolKind.GEMINI,
        group_name="chat-to-gemini",
    )

    response = client.post(
        "/v1/chat/completions",
        headers=gateway_headers(create_gateway_key()),
        json={
            "model": "chat-to-gemini",
            "messages": [
                {"role": "system", "content": "be brief"},
                {"role": "user", "content": "hello"},
            ],
        },
    )

    assert response.status_code == 200, response.text
    assert captured["url"] == "https://upstream.example/v1beta/interactions"
    assert captured["headers"]["x-goog-api-key"] == "upstream-secret"
    assert captured["body"]["model"] == "upstream-model"
    assert captured["body"]["store"] is False
    assert captured["body"]["system_instruction"] == "be brief"
    assert captured["body"]["input"] == [
        {
            "type": "user_input",
            "content": [{"type": "text", "text": "hello"}],
        }
    ]
    assert response.json()["choices"][0]["message"]["content"] == "hi there"


def test_gemini_client_reaches_interactions_upstream(
    client: Any,
    monkeypatch: Any,
    create_site: Any,
    create_model_group: Any,
    create_gateway_key: Any,
) -> None:
    captured: dict[str, Any] = {}
    _capture_json_upstream(
        monkeypatch,
        captured,
        {
            "id": "interaction_1",
            "object": "interaction",
            "model": "upstream-model",
            "status": "completed",
            "steps": [
                {
                    "type": "model_output",
                    "content": [{"type": "text", "text": "hi there"}],
                }
            ],
            "usage": {"total_input_tokens": 3, "total_output_tokens": 2},
        },
    )
    _single_upstream_group(
        create_site,
        create_model_group,
        upstream_protocol=ProtocolKind.GEMINI,
        group_name="gemini-to-gemini",
    )

    response = client.post(
        "/v1beta/interactions",
        headers=gateway_headers(create_gateway_key()),
        json={
            "model": "gemini-to-gemini",
            "input": [
                {
                    "type": "user_input",
                    "content": [{"type": "text", "text": "hello"}],
                }
            ],
        },
    )

    assert response.status_code == 200, response.text
    assert captured["url"] == "https://upstream.example/v1beta/interactions"
    assert captured["body"]["input"] == [
        {
            "type": "user_input",
            "content": [{"type": "text", "text": "hello"}],
        }
    ]
    step = response.json()["steps"][0]
    assert step["content"] == [{"type": "text", "text": "hi there"}]


def test_gemini_client_streams_from_interactions_upstream(
    client: Any,
    monkeypatch: Any,
    create_site: Any,
    create_model_group: Any,
    create_gateway_key: Any,
) -> None:
    captured: dict[str, Any] = {}
    _capture_stream_upstream(
        monkeypatch,
        captured,
        [
            {
                "event_type": "interaction.created",
                "interaction": {
                    "id": "g1",
                    "object": "interaction",
                    "model": "upstream-model",
                    "status": "in_progress",
                },
            },
            {
                "event_type": "step.start",
                "index": 0,
                "step": {"type": "model_output"},
            },
            {
                "event_type": "step.delta",
                "index": 0,
                "delta": {"type": "text", "text": "hi"},
            },
            {"event_type": "step.stop", "index": 0},
            {
                "event_type": "interaction.completed",
                "interaction": {
                    "id": "g1",
                    "object": "interaction",
                    "model": "upstream-model",
                    "status": "completed",
                },
            },
        ],
    )
    _single_upstream_group(
        create_site,
        create_model_group,
        upstream_protocol=ProtocolKind.GEMINI,
        group_name="gemini-stream-to-gemini",
    )

    response = client.post(
        "/v1beta/interactions",
        headers=gateway_headers(create_gateway_key()),
        json={
            "model": "gemini-stream-to-gemini",
            "stream": True,
            "input": [
                {
                    "type": "user_input",
                    "content": [{"type": "text", "text": "hello"}],
                }
            ],
        },
    )

    assert response.status_code == 200, response.text
    assert captured["url"] == "https://upstream.example/v1beta/interactions"
    assert captured["body"]["stream"] is True
    assert '"text": "hi"' in response.text


def test_chat_client_streams_from_gemini_upstream(
    client: Any,
    monkeypatch: Any,
    create_site: Any,
    create_model_group: Any,
    create_gateway_key: Any,
) -> None:
    captured: dict[str, Any] = {}
    _capture_stream_upstream(
        monkeypatch,
        captured,
        [
            {
                "event_type": "interaction.created",
                "interaction": {
                    "id": "g1",
                    "object": "interaction",
                    "model": "upstream-model",
                    "status": "in_progress",
                },
            },
            {
                "event_type": "step.start",
                "index": 0,
                "step": {"type": "model_output"},
            },
            {
                "event_type": "step.delta",
                "index": 0,
                "delta": {"type": "text", "text": "hi"},
            },
            {"event_type": "step.stop", "index": 0},
            {
                "event_type": "interaction.completed",
                "interaction": {
                    "id": "g1",
                    "object": "interaction",
                    "model": "upstream-model",
                    "status": "completed",
                    "usage": {
                        "total_input_tokens": 3,
                        "total_output_tokens": 2,
                        "total_tokens": 5,
                    },
                },
            },
        ],
    )
    _single_upstream_group(
        create_site,
        create_model_group,
        upstream_protocol=ProtocolKind.GEMINI,
        group_name="chat-from-gemini",
    )

    response = client.post(
        "/v1/chat/completions",
        headers=gateway_headers(create_gateway_key()),
        json={
            "model": "chat-from-gemini",
            "messages": [{"role": "user", "content": "hello"}],
            "stream": True,
        },
    )

    assert response.status_code == 200, response.text
    assert captured["url"] == "https://upstream.example/v1beta/interactions"
    assert captured["headers"]["x-goog-api-key"] == "upstream-secret"
    assert captured["body"]["model"] == "upstream-model"
    assert captured["body"]["stream"] is True
    assert captured["body"]["input"] == [
        {
            "type": "user_input",
            "content": [{"type": "text", "text": "hello"}],
        }
    ]
    assert '"content": "hi"' in response.text


def test_responses_client_streams_tool_call_without_arguments(
    client: Any,
    monkeypatch: Any,
    create_site: Any,
    create_model_group: Any,
    create_gateway_key: Any,
) -> None:
    captured: dict[str, Any] = {}
    _capture_stream_upstream(
        monkeypatch,
        captured,
        [
            {
                "type": "message_start",
                "message": {
                    "id": "msg_1",
                    "model": "upstream-model",
                    "usage": {"input_tokens": 3, "output_tokens": 0},
                },
            },
            {
                "type": "content_block_start",
                "index": 0,
                "content_block": {
                    "type": "tool_use",
                    "id": "call_noargs",
                    "name": "get_time",
                    "input": {},
                },
            },
            {"type": "content_block_stop", "index": 0},
            {
                "type": "message_delta",
                "delta": {"stop_reason": "tool_use"},
                "usage": {"output_tokens": 2},
            },
            {"type": "message_stop"},
        ],
    )
    _single_upstream_group(
        create_site,
        create_model_group,
        upstream_protocol=ProtocolKind.ANTHROPIC,
        group_name="responses-tool-noargs",
    )

    response = client.post(
        "/v1/responses",
        headers=gateway_headers(create_gateway_key()),
        json={
            "model": "responses-tool-noargs",
            "input": [{"role": "user", "content": "what time is it"}],
            "stream": True,
        },
    )

    assert response.status_code == 200, response.text
    assert "response.completed" in response.text
    assert '"type": "function_call"' in response.text
    assert '"name": "get_time"' in response.text
    assert '"arguments": "{}"' in response.text


def test_responses_client_streams_reasoning_and_cache_usage(
    client: Any,
    monkeypatch: Any,
    create_site: Any,
    create_model_group: Any,
    create_gateway_key: Any,
) -> None:
    captured: dict[str, Any] = {}
    _capture_stream_upstream(
        monkeypatch,
        captured,
        [
            {
                "type": "message_start",
                "message": {
                    "id": "msg_1",
                    "model": "upstream-model",
                    "usage": {
                        "input_tokens": 10,
                        "output_tokens": 0,
                        "cache_read_input_tokens": 4,
                        "cache_creation_input_tokens": 2,
                    },
                },
            },
            {
                "type": "content_block_start",
                "index": 0,
                "content_block": {"type": "thinking", "thinking": ""},
            },
            {
                "type": "content_block_delta",
                "index": 0,
                "delta": {"type": "thinking_delta", "thinking": "step one"},
            },
            {"type": "content_block_stop", "index": 0},
            {
                "type": "content_block_start",
                "index": 1,
                "content_block": {"type": "text", "text": ""},
            },
            {
                "type": "content_block_delta",
                "index": 1,
                "delta": {"type": "text_delta", "text": "answer"},
            },
            {"type": "content_block_stop", "index": 1},
            {
                "type": "message_delta",
                "delta": {"stop_reason": "end_turn"},
                "usage": {"output_tokens": 3},
            },
            {"type": "message_stop"},
        ],
    )
    _single_upstream_group(
        create_site,
        create_model_group,
        upstream_protocol=ProtocolKind.ANTHROPIC,
        group_name="responses-reasoning",
    )

    response = client.post(
        "/v1/responses",
        headers=gateway_headers(create_gateway_key()),
        json={
            "model": "responses-reasoning",
            "input": [{"role": "user", "content": "hello"}],
            "stream": True,
        },
    )

    assert response.status_code == 200, response.text
    assert '"type": "response.reasoning_summary_text.delta"' in response.text
    assert '"delta": "step one"' in response.text
    completed = [
        line
        for line in response.text.splitlines()
        if line.startswith("data: ") and "response.completed" in line
    ]
    body = json.loads(completed[-1].removeprefix("data: "))
    assert [item["type"] for item in body["response"]["output"]] == [
        "reasoning",
        "message",
    ]
    assert body["response"]["output"][0]["summary"] == [
        {"type": "summary_text", "text": "step one"}
    ]
    assert body["response"]["usage"]["input_tokens_details"]["cached_tokens"] == 4
    assert body["response"]["usage"]["input_tokens_details"]["cache_write_tokens"] == 2


def test_anthropic_upstream_error_event_fails_the_request(
    client: Any,
    admin_headers: Any,
    monkeypatch: Any,
    create_site: Any,
    create_model_group: Any,
    create_gateway_key: Any,
) -> None:
    captured: dict[str, Any] = {}
    _capture_stream_upstream(
        monkeypatch,
        captured,
        [
            {
                "type": "message_start",
                "message": {
                    "id": "msg_1",
                    "model": "upstream-model",
                    "usage": {"input_tokens": 3, "output_tokens": 0},
                },
            },
            {
                "type": "content_block_start",
                "index": 0,
                "content_block": {"type": "text", "text": ""},
            },
            {
                "type": "content_block_delta",
                "index": 0,
                "delta": {"type": "text_delta", "text": "par"},
            },
            {
                "type": "error",
                "error": {"type": "overloaded_error", "message": "Overloaded"},
            },
        ],
    )
    _single_upstream_group(
        create_site,
        create_model_group,
        upstream_protocol=ProtocolKind.ANTHROPIC,
        group_name="anthropic-error-stream",
    )

    response = client.post(
        "/v1/chat/completions",
        headers=gateway_headers(create_gateway_key()),
        json={
            "model": "anthropic-error-stream",
            "messages": [{"role": "user", "content": "hello"}],
            "stream": True,
        },
    )

    page = client.get("/api/admin/request-logs/page", headers=admin_headers)

    assert page.status_code == 200
    entry = page.json()["items"][0]

    assert entry["success"] is False
    assert "Overloaded" in (entry["error_message"] or "")
    # The response already started, so the failure must travel in band.
    assert '"error":' in response.text
    assert "Overloaded" in response.text
    assert "[DONE]" not in response.text
    assert '"finish_reason": "stop"' not in response.text


# Remaining pairs: every client protocol must reach every other upstream
# protocol with the same tool and text semantics.


def test_anthropic_client_reaches_chat_upstream(
    client: Any,
    monkeypatch: Any,
    create_site: Any,
    create_model_group: Any,
    create_gateway_key: Any,
) -> None:
    """Anthropic tools and system text reach a Chat upstream."""
    captured: dict[str, Any] = {}
    _capture_json_upstream(
        monkeypatch,
        captured,
        {
            "id": "chatcmpl-1",
            "object": "chat.completion",
            "model": "upstream-model",
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": "ok"},
                    "finish_reason": "stop",
                }
            ],
            "usage": {"prompt_tokens": 1, "completion_tokens": 1},
        },
    )
    _single_upstream_group(
        create_site,
        create_model_group,
        upstream_protocol=ProtocolKind.OPENAI_CHAT,
        group_name="anthropic-to-chat",
    )

    response = client.post(
        "/v1/messages",
        headers=gateway_headers(create_gateway_key()),
        json={
            "model": "anthropic-to-chat",
            "max_tokens": 32,
            "system": "be brief",
            "messages": [{"role": "user", "content": "hello"}],
            "tools": [
                {"name": "lookup", "input_schema": {"type": "object", "properties": {}}}
            ],
            "tool_choice": {"type": "auto", "disable_parallel_tool_use": True},
        },
    )

    assert response.status_code == 200, response.text
    body = captured["body"]
    assert body["messages"][0] == {"role": "system", "content": "be brief"}
    assert body["tools"][0]["function"]["name"] == "lookup"
    assert body["parallel_tool_calls"] is False


def test_anthropic_client_reaches_responses_upstream(
    client: Any,
    monkeypatch: Any,
    create_site: Any,
    create_model_group: Any,
    create_gateway_key: Any,
) -> None:
    """Anthropic history becomes Responses input items, with store disabled."""
    captured: dict[str, Any] = {}
    _capture_json_upstream(
        monkeypatch,
        captured,
        {
            "id": "resp_1",
            "object": "response",
            "status": "completed",
            "model": "upstream-model",
            "output": [
                {
                    "type": "message",
                    "id": "msg_1",
                    "role": "assistant",
                    "content": [{"type": "output_text", "text": "ok"}],
                }
            ],
            "usage": {"input_tokens": 1, "output_tokens": 1},
        },
    )
    _single_upstream_group(
        create_site,
        create_model_group,
        upstream_protocol=ProtocolKind.OPENAI_RESPONSES,
        group_name="anthropic-to-responses",
    )

    response = client.post(
        "/v1/messages",
        headers=gateway_headers(create_gateway_key()),
        json={
            "model": "anthropic-to-responses",
            "max_tokens": 32,
            "system": "be brief",
            "messages": [{"role": "user", "content": "hello"}],
        },
    )

    assert response.status_code == 200, response.text
    body = captured["body"]
    assert body["store"] is False
    assert body["input"][0] == {"role": "system", "content": "be brief"}
    assert body["input"][1] == {"role": "user", "content": "hello"}


def test_anthropic_client_reaches_gemini_upstream(
    client: Any,
    monkeypatch: Any,
    create_site: Any,
    create_model_group: Any,
    create_gateway_key: Any,
) -> None:
    """Anthropic text and instructions reach a Gemini Interactions upstream."""
    captured: dict[str, Any] = {}
    _capture_json_upstream(
        monkeypatch,
        captured,
        {
            "id": "interaction_1",
            "object": "interaction",
            "model": "upstream-model",
            "status": "completed",
            "steps": [
                {"type": "model_output", "content": [{"type": "text", "text": "ok"}]}
            ],
            "usage": {"input_tokens": 1, "output_tokens": 1},
        },
    )
    _single_upstream_group(
        create_site,
        create_model_group,
        upstream_protocol=ProtocolKind.GEMINI,
        group_name="anthropic-to-gemini",
    )

    response = client.post(
        "/v1/messages",
        headers=gateway_headers(create_gateway_key()),
        json={
            "model": "anthropic-to-gemini",
            "max_tokens": 32,
            "system": "be brief",
            "messages": [{"role": "user", "content": "hello"}],
        },
    )

    assert response.status_code == 200, response.text
    body = captured["body"]
    assert body["system_instruction"] == "be brief"
    assert body["input"][0]["type"] == "user_input"


def test_responses_client_reaches_gemini_upstream(
    client: Any,
    monkeypatch: Any,
    create_site: Any,
    create_model_group: Any,
    create_gateway_key: Any,
) -> None:
    """Responses instructions and function tools reach a Gemini upstream."""
    captured: dict[str, Any] = {}
    _capture_json_upstream(
        monkeypatch,
        captured,
        {
            "id": "interaction_2",
            "object": "interaction",
            "model": "upstream-model",
            "status": "completed",
            "steps": [
                {"type": "model_output", "content": [{"type": "text", "text": "ok"}]}
            ],
            "usage": {"input_tokens": 1, "output_tokens": 1},
        },
    )
    _single_upstream_group(
        create_site,
        create_model_group,
        upstream_protocol=ProtocolKind.GEMINI,
        group_name="responses-to-gemini",
    )

    response = client.post(
        "/v1/responses",
        headers=gateway_headers(create_gateway_key()),
        json={
            "model": "responses-to-gemini",
            "instructions": "be brief",
            "input": "hello",
            "tools": [{"type": "function", "name": "lookup", "parameters": {}}],
        },
    )

    assert response.status_code == 200, response.text
    body = captured["body"]
    assert body["system_instruction"] == "be brief"
    assert body["tools"][0]["name"] == "lookup"


def test_gemini_client_reaches_responses_upstream(
    client: Any,
    monkeypatch: Any,
    create_site: Any,
    create_model_group: Any,
    create_gateway_key: Any,
) -> None:
    """Gemini instructions and function tools reach a Responses upstream."""
    captured: dict[str, Any] = {}
    _capture_json_upstream(
        monkeypatch,
        captured,
        {
            "id": "resp_2",
            "object": "response",
            "status": "completed",
            "model": "upstream-model",
            "output": [
                {
                    "type": "message",
                    "id": "msg_2",
                    "role": "assistant",
                    "content": [{"type": "output_text", "text": "ok"}],
                }
            ],
            "usage": {"input_tokens": 1, "output_tokens": 1},
        },
    )
    _single_upstream_group(
        create_site,
        create_model_group,
        upstream_protocol=ProtocolKind.OPENAI_RESPONSES,
        group_name="gemini-to-responses",
    )

    response = client.post(
        "/v1beta/interactions",
        headers=gateway_headers(create_gateway_key()),
        json={
            "model": "gemini-to-responses",
            "system_instruction": "be brief",
            "input": [{"type": "text", "text": "hello"}],
            "tools": [{"type": "function", "name": "lookup", "parameters": {}}],
        },
    )

    assert response.status_code == 200, response.text
    body = captured["body"]
    assert body["input"][0] == {"role": "system", "content": "be brief"}
    assert body["tools"][0]["name"] == "lookup"
    assert body["tools"][0]["type"] == "function"


def test_gemini_client_reaches_anthropic_upstream(
    client: Any,
    monkeypatch: Any,
    create_site: Any,
    create_model_group: Any,
    create_gateway_key: Any,
) -> None:
    """Gemini instructions and function tools reach an Anthropic upstream."""
    captured: dict[str, Any] = {}
    _capture_json_upstream(
        monkeypatch,
        captured,
        {
            "id": "msg_2",
            "type": "message",
            "role": "assistant",
            "model": "upstream-model",
            "content": [{"type": "text", "text": "ok"}],
            "stop_reason": "end_turn",
            "usage": {"input_tokens": 1, "output_tokens": 1},
        },
    )
    _single_upstream_group(
        create_site,
        create_model_group,
        upstream_protocol=ProtocolKind.ANTHROPIC,
        group_name="gemini-to-anthropic",
    )

    response = client.post(
        "/v1beta/interactions",
        headers=gateway_headers(create_gateway_key()),
        json={
            "model": "gemini-to-anthropic",
            "system_instruction": "be brief",
            "input": [{"type": "text", "text": "hello"}],
            "tools": [{"type": "function", "name": "lookup", "parameters": {}}],
        },
    )

    assert response.status_code == 200, response.text
    body = captured["body"]
    assert body["system"] == "be brief"
    assert body["tools"][0]["name"] == "lookup"
    assert body["tools"][0]["input_schema"] == {
        "type": "object",
        "properties": {},
    }
