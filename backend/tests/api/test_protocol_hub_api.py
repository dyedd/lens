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
            "messages": [{"role": "user", "content": "hello"}],
        },
    )

    assert response.status_code == 200, response.text
    assert captured["url"] == "https://upstream.example/v1/messages"
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
        json={"model": "responses-to-anthropic", "input": "hello"},
    )

    assert response.status_code == 200, response.text
    assert captured["url"] == "https://upstream.example/v1/messages"
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
        "/v1beta/models/gemini-to-chat:generateContent",
        headers=gateway_headers(create_gateway_key()),
        json={"contents": [{"role": "user", "parts": [{"text": "hello"}]}]},
    )

    assert response.status_code == 200, response.text
    assert captured["url"] == "https://upstream.example/v1/chat/completions"
    assert captured["body"]["messages"] == [{"role": "user", "content": "hello"}]
    candidate = response.json()["candidates"][0]
    assert candidate["content"]["parts"] == [{"text": "hi there"}]
    assert candidate["finishReason"] == "STOP"


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
                "responseId": "g1",
                "candidates": [
                    {
                        "content": {"role": "model", "parts": [{"text": "hi"}]},
                        "finishReason": "STOP",
                    }
                ],
                "usageMetadata": {"promptTokenCount": 3, "candidatesTokenCount": 2},
            }
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
    assert captured["url"] == (
        "https://upstream.example/v1beta/models/upstream-model:streamGenerateContent"
        "?key=upstream-secret&alt=sse"
    )
    assert captured["body"]["contents"] == [
        {"role": "user", "parts": [{"text": "hello"}]}
    ]
    assert '"content": "hi"' in response.text
