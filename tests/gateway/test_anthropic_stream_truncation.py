from __future__ import annotations

import json
from typing import Any

import pytest
from conftest import run_async
from fastapi import Response

from lens_api.gateway.service import stream_logging
from lens_api.gateway.service.runtime_types import (
    StreamCapture,
    UpstreamResult,
    _capture_stream_content,
    _RequestDeadline,
)
from lens_api.models import (
    ChannelConfig,
    GatewayApiKey,
    ProtocolKind,
    RequestLogLifecycleStatus,
)


def _truncated_anthropic_tool_stream() -> str:
    """An Anthropic tool-use stream cut in the middle of an input_json_delta frame."""
    events = [
        {
            "type": "message_start",
            "message": {
                "id": "msg_1",
                "type": "message",
                "role": "assistant",
                "model": "claude-upstream",
                "content": [],
                "usage": {"input_tokens": 11, "output_tokens": 0},
            },
        },
        {
            "type": "content_block_start",
            "index": 0,
            "content_block": {
                "type": "tool_use",
                "id": "toolu_1",
                "name": "Read",
                "input": {},
            },
        },
        {
            "type": "content_block_delta",
            "index": 0,
            "delta": {"type": "input_json_delta", "partial_json": '{"file_path": "'},
        },
    ]
    complete = "".join(f"data: {json.dumps(event)}\n\n" for event in events)
    # The stream stops here, inside the last frame's JSON payload.
    return (
        f'{complete}data: {{"type":"content_block_delta","index":0,'
        f'"delta":{{"type":"input_json_delta","partial_json":"/tmp'
    )


def _channel(protocol: ProtocolKind = ProtocolKind.ANTHROPIC) -> ChannelConfig:
    return ChannelConfig(
        id="ch-1",
        name="Upstream Site",
        protocol=protocol,
        base_url="https://upstream.example/v1",
        api_key="upstream-secret",
    )


def _gateway_key() -> GatewayApiKey:
    return GatewayApiKey(
        id="gk-1",
        api_key="sk-lens-test",
        created_at="2026-01-01T00:00:00Z",
        updated_at="2026-01-01T00:00:00Z",
    )


class _RouterSpy:
    def __init__(self) -> None:
        self.failures: list[str] = []
        self.successes: list[str] = []

    def record_failure(self, channel_id: str, message: str, **_kwargs: Any) -> None:
        self.failures.append(message)

    def record_success(self, channel_id: str, **_kwargs: Any) -> None:
        self.successes.append(channel_id)


def _run_stream_log(
    monkeypatch: pytest.MonkeyPatch,
    capture: StreamCapture,
    *,
    protocol: ProtocolKind = ProtocolKind.ANTHROPIC,
    channel_protocol: ProtocolKind | None = None,
) -> tuple[dict[str, Any], _RouterSpy]:
    recorded: dict[str, Any] = {}
    router = _RouterSpy()

    async def fake_update_request_log(request_log_id: int, **kwargs: Any) -> None:
        recorded.update(kwargs)

    async def fake_estimate_cost(*_args: Any, **_kwargs: Any) -> tuple[float, ...]:
        return (0.0, 0.0, 0.0)

    monkeypatch.setattr(stream_logging, "_update_request_log", fake_update_request_log)
    monkeypatch.setattr(stream_logging, "_safe_estimate_cost", fake_estimate_cost)
    monkeypatch.setattr(stream_logging.app_state, "router", router, raising=False)

    channel = _channel(channel_protocol or protocol)
    run_async(
        stream_logging._record_stream_request_log(
            request_log_id=1,
            protocol=protocol,
            requested_group_name="test-group",
            resolved_group_name="test-group",
            channel=channel,
            gateway_key=_gateway_key(),
            user_agent="pytest",
            started_at=0.0,
            result=UpstreamResult(
                response=Response(),
                status_code=200,
                is_stream=True,
                stream_capture=capture,
            ),
            attempts=[
                {
                    "channel_id": channel.id,
                    "channel_name": channel.name,
                    "credential_id": "cred-1",
                    "model_name": "upstream-model",
                    "status_code": 200,
                    "success": True,
                    "duration_ms": 12,
                }
            ],
        )
    )
    return recorded, router


def _capture_with_truncated_body(**overrides: Any) -> StreamCapture:
    capture = StreamCapture(
        capture_body=True,
        deadline=_RequestDeadline(0.0, 0.0, 0.0),
        **overrides,
    )
    capture.response_content_chunks.append(_truncated_anthropic_tool_stream())
    # What the transport already tracked per event before the stream was cut.
    capture.resolved_model = "claude-upstream"
    capture.input_tokens = 11
    return capture


def test_client_cancel_mid_tool_call_is_not_an_upstream_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    capture = _capture_with_truncated_body(is_client_disconnected=True)

    recorded, router = _run_stream_log(monkeypatch, capture)

    assert capture.parse_errors == []
    assert recorded["lifecycle_status"] == RequestLogLifecycleStatus.CANCELLED
    assert recorded["error_message"] is None
    assert router.failures == []
    assert router.successes == []
    assert recorded["attempts"][-1]["success"] is True
    # Usage tracked incrementally while streaming survives the cancel.
    assert recorded["input_tokens"] == 11
    assert recorded["upstream_model_name"] == "claude-upstream"
    # The raw body is still logged, just not re-parsed as a whole document.
    assert recorded["response_content"] == _truncated_anthropic_tool_stream()


def test_upstream_cut_mid_tool_call_still_fails_the_route(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    capture = _capture_with_truncated_body(is_client_stream_completed=True)

    recorded, router = _run_stream_log(monkeypatch, capture)

    assert recorded["lifecycle_status"] == RequestLogLifecycleStatus.FAILED
    assert "invalid SSE JSON" in recorded["error_message"]
    assert "Invalid Anthropic tool input JSON" in recorded["error_message"]
    assert len(router.failures) == 1


_TRUNCATED_BODIES: dict[ProtocolKind, str] = {
    ProtocolKind.ANTHROPIC: _truncated_anthropic_tool_stream(),
    ProtocolKind.OPENAI_CHAT: (
        'data: {"id":"c1","model":"m","choices":[{"index":0,'
        '"delta":{"content":"hi"}}]}\n\n'
        'data: {"id":"c1","model":"m","choices":[{"index":0,"delta":{"content'
    ),
    ProtocolKind.OPENAI_RESPONSES: (
        'data: {"type":"response.created","response":{"id":"r1","model":"m"}}\n\n'
        'data: {"type":"response.output_text.delta","delta":"hi'
    ),
    ProtocolKind.GEMINI: (
        'data: {"candidates":[{"content":{"parts":[{"text":"hi"}]}}]}\n\n'
        'data: {"candidates":[{"content":{"parts":[{"text'
    ),
}


@pytest.mark.parametrize("protocol", sorted(_TRUNCATED_BODIES, key=lambda p: p.value))
def test_client_cancel_is_never_a_route_failure_for_any_protocol(
    monkeypatch: pytest.MonkeyPatch, protocol: ProtocolKind
) -> None:
    capture = StreamCapture(
        capture_body=True,
        deadline=_RequestDeadline(0.0, 0.0, 0.0),
        is_client_disconnected=True,
    )
    capture.response_content_chunks.append(_TRUNCATED_BODIES[protocol])

    recorded, router = _run_stream_log(monkeypatch, capture, protocol=protocol)

    assert capture.parse_errors == []
    assert recorded["lifecycle_status"] == RequestLogLifecycleStatus.CANCELLED
    assert recorded["error_message"] is None
    assert router.failures == []
    assert router.successes == []


def test_client_cancel_during_conversion_is_not_a_route_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Converted streams mirror a second body; a cancel truncates that one too."""
    capture = StreamCapture(
        capture_body=True,
        deadline=_RequestDeadline(0.0, 0.0, 0.0),
        is_client_disconnected=True,
    )
    capture.response_content_chunks.append(_TRUNCATED_BODIES[ProtocolKind.OPENAI_CHAT])
    capture.client_response_content_chunks.append(
        _TRUNCATED_BODIES[ProtocolKind.ANTHROPIC]
    )

    recorded, router = _run_stream_log(
        monkeypatch,
        capture,
        protocol=ProtocolKind.ANTHROPIC,
        channel_protocol=ProtocolKind.OPENAI_CHAT,
    )

    assert capture.parse_errors == []
    assert recorded["lifecycle_status"] == RequestLogLifecycleStatus.CANCELLED
    assert recorded["error_message"] is None
    assert router.failures == []


def test_multi_byte_characters_survive_chunk_boundaries() -> None:
    """UTF-8 codepoints split across chunk boundaries must not become mojibake."""
    capture = StreamCapture(capture_body=True, deadline=_RequestDeadline(0.0, 0.0, 0.0))
    # '用户你好' is 12 bytes; split after byte 5, which lands inside '户'.
    text_bytes = "用户你好".encode("utf-8")
    for part in (text_bytes[:5], text_bytes[5:]):
        _capture_stream_content(capture, capture.content_decoder.decode(part))

    logged = "".join(capture.response_content_chunks)
    assert logged == "用户你好"
    assert "�" not in logged
