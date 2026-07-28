from __future__ import annotations

import json
from time import perf_counter
from typing import Any

import httpx
import pytest
from conftest import gateway_headers, run_async, valid_site_payload

from lens_api.core.runtime_channel_ids import compose_runtime_channel_id
from lens_api.gateway.service.runtime_types import StreamCapture, _RequestDeadline
from lens_api.gateway.service.stream_logging import _stream_log_lifecycle_status
from lens_api.gateway.service.stream_transport import _stream_upstream_iterator
from lens_api.gateway.service.usage import _describe_stream_capture_issue
from lens_api.models import ProtocolKind, RequestLogLifecycleStatus
from lens_api.persistence.shared import SETTING_RELAY_LOG_BODY_ENABLED, SettingItem


class _ControlledByteStream(httpx.AsyncByteStream):
    def __init__(self, *chunks: bytes, expect_early_close: bool = True) -> None:
        self.chunks = chunks
        self.expect_early_close = expect_early_close

    async def __aiter__(self):
        for chunk in self.chunks:
            yield chunk
        if self.expect_early_close:
            raise AssertionError("stream waited for upstream EOF")

    async def aclose(self) -> None:
        pass


async def _collect_upstream_stream(
    protocol: ProtocolKind, stream: httpx.AsyncByteStream
) -> tuple[bytes, StreamCapture]:
    response = httpx.Response(
        200,
        headers={"content-type": "text/event-stream"},
        request=httpx.Request("POST", "https://upstream.example/stream"),
        stream=stream,
    )
    capture = StreamCapture(
        capture_body=False,
        deadline=_RequestDeadline(perf_counter(), 30.0, 30.0),
    )
    try:
        content = b"".join(
            [
                chunk
                async for chunk in _stream_upstream_iterator(
                    response,
                    protocol,
                    capture,
                    perf_counter(),
                )
            ]
        )
        if stream.expect_early_close:
            assert response.is_closed is True
    finally:
        await response.aclose()
    return content, capture


@pytest.mark.parametrize(
    ("protocol", "content", "terminal_marker", "trailing_marker"),
    [
        (
            ProtocolKind.OPENAI_RESPONSES,
            (
                b"event: response.incomplete\n"
                b'data: {"type":"response.incomplete","response":{}}\n\n'
                b"event: response.output_text.delta\n"
                b'data: {"type":"response.output_text.delta","delta":"late"}\n\n'
            ),
            b"response.incomplete",
            b'"delta":"late"',
        ),
        (
            ProtocolKind.OPENAI_CHAT,
            (
                b'data: {"choices":[{"index":0,"finish_reason":"stop"}]}\n\n'
                b'data: {"choices":[],"usage":{"total_tokens":2}}\n\n'
                b"data: [DONE]\n\n"
                b'data: {"choices":[{"delta":{"content":"late"}}]}\n\n'
            ),
            b'"usage":{"total_tokens":2}',
            b'"content":"late"',
        ),
        (
            ProtocolKind.ANTHROPIC,
            (
                b"event: message_stop\n"
                b'data: {"type":"message_stop"}\n\n'
                b"event: content_block_delta\n"
                b'data: {"type":"content_block_delta","delta":{"text":"late"}}\n\n'
            ),
            b"message_stop",
            b'"text":"late"',
        ),
    ],
)
def test_protocol_terminal_events_stop_at_the_terminal_boundary(
    protocol: ProtocolKind,
    content: bytes,
    terminal_marker: bytes,
    trailing_marker: bytes,
) -> None:
    forwarded, _capture = run_async(
        _collect_upstream_stream(protocol, _ControlledByteStream(content))
    )

    assert terminal_marker in forwarded
    assert trailing_marker not in forwarded


def test_terminal_boundary_preserves_split_utf8_and_crlf_bytes() -> None:
    expected = (
        'event: response.output_text.delta\r\ndata: {"type":'
        '"response.output_text.delta","delta":"中文"}\r\n\r\n'
        'event: response.completed\r\ndata: {"type":'
        '"response.completed","response":{}}\r\n\r\n'
    ).encode()
    trailing = (
        b"event: response.output_text.delta\r\n"
        b'data: {"type":"response.output_text.delta","delta":"late"}\r\n\r\n'
    )
    split_at = expected.index("中".encode()) + 1

    forwarded, _capture = run_async(
        _collect_upstream_stream(
            ProtocolKind.OPENAI_RESPONSES,
            _ControlledByteStream(expected[:split_at], expected[split_at:] + trailing),
        )
    )

    assert forwarded.endswith(b"\r\n\r\n")
    assert b'"delta":"late"' not in forwarded
    assert forwarded.decode() == (
        'event: response.output_text.delta\r\ndata: {"type":'
        '"response.output_text.delta","delta":"中文"}\r\n\r\n'
        'event: response.completed\r\ndata: {"type":'
        '"response.completed","response":{}}\r\n\r\n'
    )


def test_gemini_finish_reason_preserves_later_usage_metadata() -> None:
    content = (
        b'{"candidates":[{"index":0,"finishReason":"STOP"}]}\n'
        b'{"usageMetadata":{"promptTokenCount":3,'
        b'"candidatesTokenCount":2,"totalTokenCount":5}}\n'
    )

    forwarded, capture = run_async(
        _collect_upstream_stream(
            ProtocolKind.GEMINI,
            _ControlledByteStream(content, expect_early_close=False),
        )
    )

    assert b'"usageMetadata"' in forwarded
    assert capture.input_tokens == 3
    assert capture.output_tokens == 2
    assert capture.total_tokens == 5


@pytest.mark.parametrize(
    ("protocol", "content"),
    [
        (
            ProtocolKind.OPENAI_CHAT,
            b'data: {"choices":[{"delta":{"content":"hello"}}]}\n\n',
        ),
        (
            ProtocolKind.OPENAI_RESPONSES,
            b'data: {"type":"response.output_text.delta","delta":"hello"}\n\n',
        ),
        (
            ProtocolKind.ANTHROPIC,
            b'data: {"type":"content_block_delta","delta":{"text":"hello"}}\n\n',
        ),
        (
            ProtocolKind.GEMINI,
            b'{"candidates":[{"content":{"parts":[{"text":"hello"}]}}]}\n',
        ),
        (ProtocolKind.OPENAI_RESPONSES, b""),
    ],
)
def test_same_protocol_clean_eof_succeeds_without_terminal_or_output(
    protocol: ProtocolKind,
    content: bytes,
) -> None:
    forwarded, capture = run_async(
        _collect_upstream_stream(
            protocol,
            _ControlledByteStream(content, expect_early_close=False),
        )
    )

    capture_issue = _describe_stream_capture_issue(capture)

    assert forwarded == content
    assert capture_issue is None
    assert (
        _stream_log_lifecycle_status(capture, capture_issue)
        == RequestLogLifecycleStatus.SUCCEEDED
    )


@pytest.mark.parametrize(
    ("protocol", "content", "error_marker"),
    [
        (
            ProtocolKind.OPENAI_CHAT,
            (
                b'data: {"error":{"message":"upstream failed"}}\n\n'
                b'data: {"choices":[{"delta":{"content":"late"}}]}\n\n'
            ),
            b'"error":{"message":"upstream failed"}',
        ),
        (
            ProtocolKind.OPENAI_RESPONSES,
            (
                b'event: response.failed\ndata: {"type":"response.failed",'
                b'"response":{"error":{"message":"upstream failed"}}}\n\n'
                b'data: {"type":"response.output_text.delta","delta":"late"}\n\n'
            ),
            b"response.failed",
        ),
        (
            ProtocolKind.ANTHROPIC,
            (
                b'event: error\ndata: {"type":"error",'
                b'"error":{"message":"upstream failed"}}\n\n'
                b'data: {"type":"content_block_delta","delta":{"text":"late"}}\n\n'
            ),
            b'"type":"error"',
        ),
        (
            ProtocolKind.GEMINI,
            (
                b'{"error":{"message":"upstream failed"}}\n'
                b'{"candidates":[{"content":{"parts":[{"text":"late"}]}}]}\n'
            ),
            b'"error":{"message":"upstream failed"}',
        ),
    ],
)
def test_same_protocol_explicit_stream_error_is_a_real_failure(
    protocol: ProtocolKind,
    content: bytes,
    error_marker: bytes,
) -> None:
    forwarded, capture = run_async(
        _collect_upstream_stream(protocol, _ControlledByteStream(content))
    )

    capture_issue = _describe_stream_capture_issue(capture)

    assert error_marker in forwarded
    assert b"late" not in forwarded
    assert capture_issue == f"{protocol.value} stream failed: upstream failed"
    assert capture.error_status_code == 502
    assert (
        _stream_log_lifecycle_status(capture, capture_issue)
        == RequestLogLifecycleStatus.FAILED
    )


@pytest.mark.parametrize("capture_field", ["errors", "parse_errors"])
def test_stream_lifecycle_keeps_confirmed_stream_errors(
    capture_field: str,
) -> None:
    capture = StreamCapture(
        capture_body=False,
        deadline=_RequestDeadline(perf_counter(), 30.0, 30.0),
    )
    getattr(capture, capture_field).append("confirmed stream error")

    capture_issue = _describe_stream_capture_issue(capture)

    assert capture_issue == "confirmed stream error"
    assert (
        _stream_log_lifecycle_status(capture, capture_issue)
        == RequestLogLifecycleStatus.FAILED
    )


def test_stream_lifecycle_distinguishes_client_cancel_from_completed_stream() -> None:
    capture = StreamCapture(
        capture_body=False,
        deadline=_RequestDeadline(perf_counter(), 30.0, 30.0),
        is_client_disconnected=True,
    )

    assert (
        _stream_log_lifecycle_status(capture, None)
        == RequestLogLifecycleStatus.CANCELLED
    )

    capture.protocol_completed = True

    assert (
        _stream_log_lifecycle_status(capture, None)
        == RequestLogLifecycleStatus.SUCCEEDED
    )


def test_chat_proxy_uses_responses_channel_and_converts_response(
    client,
    monkeypatch,
    app_state,
    create_site,
    create_model_group,
    create_gateway_key,
) -> None:
    from lens_api.gateway.service import proxy_upstream

    captured_request: dict[str, Any] = {}

    async def fake_estimate_cost(
        *_args: Any, **_kwargs: Any
    ) -> tuple[float, float, float]:
        return (0.0, 0.0, 0.0)

    async def fake_send_upstream(
        _client: httpx.AsyncClient,
        upstream: Any,
        *,
        stream: bool,
        body_bytes: bytes,
    ) -> httpx.Response:
        assert not stream
        captured_request["url"] = str(upstream.url)
        captured_request["body"] = json.loads(body_bytes)
        return httpx.Response(
            200,
            json={
                "id": "resp_1",
                "object": "response",
                "created_at": 123,
                "status": "completed",
                "model": "responses-model",
                "output": [
                    {
                        "type": "message",
                        "role": "assistant",
                        "content": [{"type": "output_text", "text": "Hello"}],
                    }
                ],
                "usage": {
                    "input_tokens": 3,
                    "output_tokens": 1,
                    "total_tokens": 4,
                },
            },
            request=httpx.Request("POST", upstream.url),
        )

    monkeypatch.setattr(proxy_upstream, "_send_upstream", fake_send_upstream)
    monkeypatch.setattr(
        app_state.model_price_repo, "estimate_model_cost", fake_estimate_cost
    )
    create_site(
        valid_site_payload(
            protocols=[ProtocolKind.OPENAI_RESPONSES.value],
            model_name="responses-model",
        )
    )
    create_model_group(
        name="chat-model",
        protocols=[ProtocolKind.OPENAI_CHAT.value],
        items=[
            {
                "channel_id": compose_runtime_channel_id(
                    "pc-1", ProtocolKind.OPENAI_RESPONSES
                ),
                "credential_id": "cred-1",
                "model_name": "responses-model",
                "enabled": True,
            }
        ],
    )
    key = create_gateway_key()

    response = client.post(
        "/v1/chat/completions",
        headers=gateway_headers(key),
        json={
            "model": "chat-model",
            "messages": [{"role": "user", "content": "Hello"}],
            "n": 4,
        },
    )

    assert response.status_code == 200, response.text
    assert captured_request == {
        "url": "https://upstream.example/v1/responses",
        "body": {
            "model": "responses-model",
            "input": [{"role": "user", "content": "Hello"}],
        },
    }
    payload = response.json()
    assert payload["object"] == "chat.completion"
    assert payload["choices"][0]["message"]["content"] == "Hello"
    assert payload["usage"] == {
        "prompt_tokens": 3,
        "completion_tokens": 1,
        "total_tokens": 4,
    }


def test_streaming_chat_proxy_converts_responses_stream_and_logs_upstream_usage(
    client,
    monkeypatch,
    app_state,
    create_site,
    create_model_group,
    create_gateway_key,
) -> None:
    from lens_api.gateway.service import proxy_upstream, stream_logging

    captured_request: dict[str, Any] = {}

    async def fake_estimate_cost(
        *_args: Any, **_kwargs: Any
    ) -> tuple[float, float, float]:
        return (0.0, 0.0, 0.0)

    async def fake_send_upstream(
        _client: httpx.AsyncClient,
        upstream: Any,
        *,
        stream: bool,
        body_bytes: bytes,
    ) -> httpx.Response:
        assert stream
        captured_request["url"] = str(upstream.url)
        captured_request["body"] = json.loads(body_bytes)
        frames = [
            {
                "type": "response.created",
                "response": {
                    "id": "resp_stream",
                    "created_at": 123,
                    "model": "responses-model",
                },
            },
            {"type": "response.output_text.delta", "delta": "Hello"},
            {
                "type": "response.completed",
                "response": {
                    "id": "resp_stream",
                    "created_at": 123,
                    "status": "completed",
                    "model": "responses-model",
                    "output": [
                        {
                            "type": "message",
                            "role": "assistant",
                            "content": [{"type": "output_text", "text": "Hello"}],
                        }
                    ],
                    "usage": {
                        "input_tokens": 5,
                        "output_tokens": 2,
                        "total_tokens": 7,
                    },
                },
            },
        ]
        content = "".join(
            f"event: {frame['type']}\ndata: {json.dumps(frame)}\n\n" for frame in frames
        ).encode()
        return httpx.Response(
            200,
            content=content,
            headers={"content-type": "text/event-stream"},
            request=httpx.Request("POST", upstream.url),
        )

    monkeypatch.setattr(proxy_upstream, "_send_upstream", fake_send_upstream)
    monkeypatch.setattr(proxy_upstream, "_safe_estimate_cost", fake_estimate_cost)
    monkeypatch.setattr(stream_logging, "_safe_estimate_cost", fake_estimate_cost)
    monkeypatch.setattr(stream_logging, "app_state", app_state)
    run_async(
        app_state.settings_repo.upsert_settings(
            [SettingItem(key=SETTING_RELAY_LOG_BODY_ENABLED, value="true")]
        )
    )
    create_site(
        valid_site_payload(
            protocols=[ProtocolKind.OPENAI_RESPONSES.value],
            model_name="responses-model",
        )
    )
    create_model_group(
        name="chat-model",
        protocols=[ProtocolKind.OPENAI_CHAT.value],
        items=[
            {
                "channel_id": compose_runtime_channel_id(
                    "pc-1", ProtocolKind.OPENAI_RESPONSES
                ),
                "credential_id": "cred-1",
                "model_name": "responses-model",
                "enabled": True,
            }
        ],
    )
    key = create_gateway_key()

    response = client.post(
        "/v1/chat/completions",
        headers=gateway_headers(key),
        json={
            "model": "chat-model",
            "messages": [{"role": "user", "content": "Hello"}],
            "stream": True,
            "stream_options": {"include_usage": True},
            "n": 4,
        },
    )

    assert response.status_code == 200, response.text
    assert captured_request == {
        "url": "https://upstream.example/v1/responses",
        "body": {
            "model": "responses-model",
            "input": [{"role": "user", "content": "Hello"}],
            "stream": True,
        },
    }
    assert '"finish_reason": "stop"' in response.text
    assert '"choices": [], "usage"' in response.text
    assert response.text.endswith("data: [DONE]\n\n")

    request_log_item = run_async(
        app_state.request_log_store.list_request_log_page()
    ).items[0]
    request_log = run_async(
        app_state.request_log_store.get_request_log(request_log_item.id)
    )
    assert request_log.success is True
    assert request_log.status_code == 200
    assert request_log.input_tokens == 5
    assert request_log.output_tokens == 2
    assert request_log.total_tokens == 7
    assert json.loads(request_log.request_content or "null") == captured_request["body"]
    assert '"object": "chat.completion.chunk"' in (request_log.response_content or "")
    assert '"content": "Hello"' in (request_log.response_content or "")
    assert "response.output_text.delta" not in (request_log.response_content or "")
