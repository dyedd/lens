from __future__ import annotations

import json
from collections.abc import AsyncIterator

import pytest
from conftest import run_async
from lens_api.core.protocol_reachability import build_protocol_conversion_matrix
from lens_api.gateway.converters import (
    convert_request,
    convert_response,
    convert_stream_iterator,
)
from lens_api.gateway.service.runtime_types import StreamCapture, _RequestDeadline
from lens_api.gateway.service.stream_detection import _record_stream_completion
from lens_api.gateway.service.usage import _describe_stream_capture_issue
from lens_api.gateway.service.usage import _extract_stream_usage
from lens_api.models import ProtocolKind


def test_responses_channel_can_serve_chat_clients() -> None:
    matrix = build_protocol_conversion_matrix()

    assert ProtocolKind.OPENAI_CHAT.value in matrix[ProtocolKind.OPENAI_RESPONSES.value]


def test_chat_request_converts_supported_fields_and_drops_the_rest() -> None:
    converted = convert_request(
        ProtocolKind.OPENAI_CHAT,
        ProtocolKind.OPENAI_RESPONSES,
        {
            "model": "client-model",
            "messages": [
                {"role": "system", "content": "Be concise."},
                {"role": "user", "content": "Look it up."},
                {
                    "role": "assistant",
                    "content": "I will check.",
                    "tool_calls": [
                        {
                            "id": "call_1",
                            "type": "function",
                            "function": {
                                "name": "lookup",
                                "arguments": '{"query":"lens"}',
                            },
                        }
                    ],
                },
                {"role": "tool", "tool_call_id": "call_1", "content": "found"},
            ],
            "tools": [
                {
                    "type": "function",
                    "function": {
                        "name": "lookup",
                        "description": "Search the index",
                        "parameters": {"type": "object"},
                        "strict": True,
                        "provider_only": "drop-me",
                    },
                }
            ],
            "tool_choice": {"type": "function", "function": {"name": "lookup"}},
            "max_completion_tokens": 256,
            "reasoning_effort": "high",
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": "result",
                    "strict": True,
                    "schema": {"type": "object"},
                },
            },
            "temperature": 0.2,
            "stream": True,
            "stream_options": {"include_usage": True},
            "n": 3,
            "stop": ["END"],
            "provider_only": "drop-me",
        },
        "upstream-model",
    )

    assert converted == {
        "model": "upstream-model",
        "input": [
            {"role": "system", "content": "Be concise."},
            {"role": "user", "content": "Look it up."},
            {"role": "assistant", "content": "I will check."},
            {
                "type": "function_call",
                "call_id": "call_1",
                "name": "lookup",
                "arguments": '{"query":"lens"}',
            },
            {
                "type": "function_call_output",
                "call_id": "call_1",
                "output": "found",
            },
        ],
        "tools": [
            {
                "type": "function",
                "name": "lookup",
                "description": "Search the index",
                "parameters": {"type": "object"},
                "strict": True,
            }
        ],
        "tool_choice": {"type": "function", "name": "lookup"},
        "max_output_tokens": 256,
        "reasoning": {"effort": "high"},
        "text": {
            "format": {
                "type": "json_schema",
                "name": "result",
                "strict": True,
                "schema": {"type": "object"},
            }
        },
        "temperature": 0.2,
        "stream": True,
    }


@pytest.mark.parametrize(
    ("body", "message"),
    [
        (
            {"messages": [{"content": "missing role"}]},
            "string role",
        ),
        (
            {
                "messages": [
                    {
                        "role": "assistant",
                        "tool_calls": [
                            {
                                "type": "function",
                                "function": {"name": "lookup", "arguments": "{}"},
                            }
                        ],
                    }
                ]
            },
            "contain id",
        ),
        (
            {"messages": [], "tools": {"type": "function"}},
            "tools must be an array",
        ),
    ],
)
def test_chat_request_rejects_malformed_required_structures(
    body: dict[str, object], message: str
) -> None:
    with pytest.raises(ValueError, match=message):
        convert_request(
            ProtocolKind.OPENAI_CHAT,
            ProtocolKind.OPENAI_RESPONSES,
            body,
        )


def test_responses_response_converts_text_tools_usage_and_finish_reason() -> None:
    converted = json.loads(
        convert_response(
            ProtocolKind.OPENAI_CHAT,
            ProtocolKind.OPENAI_RESPONSES,
            json.dumps(
                {
                    "id": "resp_1",
                    "object": "response",
                    "created_at": 123,
                    "status": "completed",
                    "model": "gpt-test",
                    "output": [
                        {
                            "type": "message",
                            "role": "assistant",
                            "content": [{"type": "output_text", "text": "Checking."}],
                        },
                        {
                            "type": "function_call",
                            "call_id": "call_1",
                            "name": "lookup",
                            "arguments": '{"query":"lens"}',
                        },
                    ],
                    "usage": {
                        "input_tokens": 10,
                        "input_tokens_details": {"cached_tokens": 4},
                        "output_tokens": 6,
                        "output_tokens_details": {"reasoning_tokens": 2},
                        "total_tokens": 16,
                    },
                }
            ).encode(),
            "fallback-model",
        )
    )

    assert converted == {
        "id": "resp_1",
        "object": "chat.completion",
        "created": 123,
        "model": "gpt-test",
        "choices": [
            {
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": "Checking.",
                    "tool_calls": [
                        {
                            "id": "call_1",
                            "type": "function",
                            "function": {
                                "name": "lookup",
                                "arguments": '{"query":"lens"}',
                            },
                        }
                    ],
                },
                "logprobs": None,
                "finish_reason": "tool_calls",
            }
        ],
        "usage": {
            "prompt_tokens": 10,
            "completion_tokens": 6,
            "total_tokens": 16,
            "prompt_tokens_details": {"cached_tokens": 4},
            "completion_tokens_details": {"reasoning_tokens": 2},
        },
    }


def test_incomplete_response_keeps_refusal_and_uses_length_finish_reason() -> None:
    converted = json.loads(
        convert_response(
            ProtocolKind.OPENAI_CHAT,
            ProtocolKind.OPENAI_RESPONSES,
            json.dumps(
                {
                    "id": "resp_incomplete",
                    "created_at": 123,
                    "status": "incomplete",
                    "incomplete_details": {"reason": "max_output_tokens"},
                    "model": "gpt-test",
                    "output": [
                        {
                            "type": "message",
                            "content": [
                                {"type": "refusal", "refusal": "Cannot comply."}
                            ],
                        },
                        {
                            "type": "function_call",
                            "call_id": "call_1",
                            "name": "lookup",
                            "arguments": "{}",
                        },
                    ],
                    "usage": {"input_tokens": 4, "output_tokens": 2},
                }
            ).encode(),
            "fallback-model",
        )
    )

    choice = converted["choices"][0]
    assert choice["finish_reason"] == "length"
    assert choice["message"]["refusal"] == "Cannot comply."
    assert converted["usage"]["total_tokens"] == 6


async def _responses_stream() -> AsyncIterator[bytes]:
    frames = [
        {
            "type": "response.created",
            "response": {
                "id": "resp_1",
                "created_at": 123,
                "model": "gpt-test",
            },
        },
        {"type": "response.output_text.delta", "delta": "Hello"},
        {
            "type": "response.output_item.added",
            "output_index": 1,
            "item": {
                "type": "function_call",
                "call_id": "call_1",
                "name": "lookup",
            },
        },
        {
            "type": "response.function_call_arguments.delta",
            "output_index": 1,
            "delta": '{"query":"lens"}',
        },
        {
            "type": "response.completed",
            "response": {
                "id": "resp_1",
                "created_at": 123,
                "model": "gpt-test",
                "status": "completed",
                "output": [{"type": "function_call"}],
                "usage": {
                    "input_tokens": 10,
                    "output_tokens": 6,
                    "total_tokens": 16,
                },
            },
        },
    ]
    payload = "".join(
        f"event: {item['type']}\ndata: {json.dumps(item)}\n\n" for item in frames
    )
    split = len(payload) // 2
    yield payload[:split].encode()
    yield payload[split:].encode()


def test_responses_stream_converts_text_tools_usage_and_completion() -> None:
    async def collect() -> list[bytes]:
        return [
            chunk
            async for chunk in convert_stream_iterator(
                ProtocolKind.OPENAI_CHAT,
                ProtocolKind.OPENAI_RESPONSES,
                _responses_stream(),
                "fallback-model",
                include_usage=True,
            )
        ]

    chunks = run_async(collect())
    raw = b"".join(chunks).decode()
    payloads = [
        json.loads(line.removeprefix("data: "))
        for line in raw.splitlines()
        if line.startswith("data: {")
    ]

    assert payloads[0]["choices"][0]["delta"] == {
        "role": "assistant",
        "content": "",
    }
    assert payloads[1]["choices"][0]["delta"] == {"content": "Hello"}
    assert payloads[2]["choices"][0]["delta"]["tool_calls"] == [
        {
            "index": 0,
            "id": "call_1",
            "type": "function",
            "function": {"name": "lookup", "arguments": ""},
        }
    ]
    assert payloads[3]["choices"][0]["delta"]["tool_calls"] == [
        {
            "index": 0,
            "function": {"arguments": '{"query":"lens"}'},
        }
    ]
    assert payloads[4]["choices"][0]["finish_reason"] == "tool_calls"
    assert payloads[5] == {
        "id": "resp_1",
        "object": "chat.completion.chunk",
        "created": 123,
        "model": "gpt-test",
        "choices": [],
        "usage": {
            "prompt_tokens": 10,
            "completion_tokens": 6,
            "total_tokens": 16,
        },
    }
    assert raw.endswith("data: [DONE]\n\n")


def test_responses_stream_omits_usage_when_client_did_not_request_it() -> None:
    async def collect() -> str:
        chunks = [
            chunk
            async for chunk in convert_stream_iterator(
                ProtocolKind.OPENAI_CHAT,
                ProtocolKind.OPENAI_RESPONSES,
                _responses_stream(),
                "fallback-model",
            )
        ]
        return b"".join(chunks).decode()

    payloads = [
        json.loads(line.removeprefix("data: "))
        for line in run_async(collect()).splitlines()
        if line.startswith("data: {")
    ]

    assert all(payload["choices"] for payload in payloads)
    assert all("usage" not in payload for payload in payloads)


async def _responses_frames(frames: list[dict[str, object]]) -> AsyncIterator[bytes]:
    payload = "".join(
        f"event: {frame['type']}\ndata: {json.dumps(frame)}\n\n" for frame in frames
    )
    yield payload.encode()


def test_responses_stream_keeps_parallel_tool_indices_when_deltas_interleave() -> None:
    frames: list[dict[str, object]] = [
        {
            "type": "response.created",
            "response": {"id": "resp_1", "created_at": 123, "model": "gpt-test"},
        },
        {
            "type": "response.output_item.added",
            "output_index": 4,
            "item": {
                "type": "function_call",
                "call_id": "call_a",
                "name": "first",
            },
        },
        {
            "type": "response.output_item.added",
            "output_index": 1,
            "item": {
                "type": "function_call",
                "call_id": "call_b",
                "name": "second",
            },
        },
        {
            "type": "response.function_call_arguments.delta",
            "output_index": 1,
            "delta": "b",
        },
        {
            "type": "response.function_call_arguments.delta",
            "output_index": 4,
            "delta": "a",
        },
        {
            "type": "response.completed",
            "response": {
                "id": "resp_1",
                "created_at": 123,
                "model": "gpt-test",
                "status": "completed",
                "output": [{"type": "function_call"}],
            },
        },
    ]

    async def collect() -> list[dict[str, object]]:
        raw = b"".join(
            [
                chunk
                async for chunk in convert_stream_iterator(
                    ProtocolKind.OPENAI_CHAT,
                    ProtocolKind.OPENAI_RESPONSES,
                    _responses_frames(frames),
                )
            ]
        ).decode()
        return [
            json.loads(line.removeprefix("data: "))
            for line in raw.splitlines()
            if line.startswith("data: {")
        ]

    payloads = run_async(collect())
    tool_deltas = [
        payload["choices"][0]["delta"]["tool_calls"][0]
        for payload in payloads
        if payload["choices"] and payload["choices"][0]["delta"].get("tool_calls")
    ]

    assert [(item["index"], item.get("id")) for item in tool_deltas[:2]] == [
        (0, "call_a"),
        (1, "call_b"),
    ]
    assert [item["index"] for item in tool_deltas[2:]] == [1, 0]


def test_incomplete_responses_stream_uses_length_and_preserves_usage() -> None:
    frames: list[dict[str, object]] = [
        {
            "type": "response.created",
            "response": {"id": "resp_1", "created_at": 123, "model": "gpt-test"},
        },
        {
            "type": "response.output_item.added",
            "output_index": 0,
            "item": {
                "type": "function_call",
                "call_id": "call_1",
                "name": "lookup",
            },
        },
        {
            "type": "response.incomplete",
            "response": {
                "id": "resp_1",
                "created_at": 123,
                "model": "gpt-test",
                "status": "incomplete",
                "incomplete_details": {"reason": "max_output_tokens"},
                "output": [{"type": "function_call"}],
                "usage": {"input_tokens": 8, "output_tokens": 2},
            },
        },
    ]

    async def collect() -> str:
        chunks = [
            chunk
            async for chunk in convert_stream_iterator(
                ProtocolKind.OPENAI_CHAT,
                ProtocolKind.OPENAI_RESPONSES,
                _responses_frames(frames),
                include_usage=True,
            )
        ]
        return b"".join(chunks).decode()

    raw = run_async(collect())
    payloads = [
        json.loads(line.removeprefix("data: "))
        for line in raw.splitlines()
        if line.startswith("data: {")
    ]

    assert payloads[-2]["choices"][0]["finish_reason"] == "length"
    assert payloads[-1]["choices"] == []
    assert payloads[-1]["usage"]["total_tokens"] == 10
    assert raw.endswith("data: [DONE]\n\n")


@pytest.mark.parametrize(
    "frame",
    [
        {
            "type": "response.failed",
            "response": {
                "status": "failed",
                "error": {"message": "upstream failed"},
            },
        },
        {"type": "error", "message": "upstream failed"},
        {
            "type": "response.completed",
            "response": {"status": "completed"},
        },
    ],
)
def test_responses_stream_rejects_failure_and_malformed_terminal_events(
    frame: dict[str, object],
) -> None:
    async def collect() -> None:
        async for _ in convert_stream_iterator(
            ProtocolKind.OPENAI_CHAT,
            ProtocolKind.OPENAI_RESPONSES,
            _responses_frames([frame]),
        ):
            pass

    with pytest.raises(ValueError):
        run_async(collect())


def test_responses_stream_rejects_non_object_sse_payload() -> None:
    async def invalid_stream() -> AsyncIterator[bytes]:
        yield b"data: []\n\n"

    async def collect() -> None:
        async for _ in convert_stream_iterator(
            ProtocolKind.OPENAI_CHAT,
            ProtocolKind.OPENAI_RESPONSES,
            invalid_stream(),
        ):
            pass

    with pytest.raises(ValueError, match="JSON object"):
        run_async(collect())


@pytest.mark.parametrize(
    ("client_protocol", "channel_protocol"),
    [
        (ProtocolKind.ANTHROPIC, ProtocolKind.OPENAI_CHAT),
        (ProtocolKind.OPENAI_RESPONSES, ProtocolKind.OPENAI_CHAT),
        (ProtocolKind.OPENAI_CHAT, ProtocolKind.OPENAI_RESPONSES),
        (ProtocolKind.ANTHROPIC, ProtocolKind.OPENAI_RESPONSES),
    ],
)
def test_cross_protocol_stream_still_requires_upstream_terminal_event(
    client_protocol: ProtocolKind,
    channel_protocol: ProtocolKind,
) -> None:
    async def incomplete_stream() -> AsyncIterator[bytes]:
        if channel_protocol == ProtocolKind.OPENAI_CHAT:
            yield (
                b'data: {"id":"chat_1","model":"test-model","choices":['
                b'{"index":0,"delta":{"content":"hello"}}]}\n\n'
            )
            return
        yield (
            b'event: response.created\ndata: {"type":"response.created",'
            b'"response":{"id":"resp_1","model":"test-model"}}\n\n'
        )

    async def collect() -> None:
        async for _ in convert_stream_iterator(
            client_protocol,
            channel_protocol,
            incomplete_stream(),
        ):
            pass

    with pytest.raises(ValueError, match="ended before"):
        run_async(collect())


def test_terminal_event_remains_successful_after_client_disconnect() -> None:
    deadline = _RequestDeadline(0.0, 0.0, 0.0)
    for protocol, payload in (
        (
            ProtocolKind.OPENAI_CHAT,
            {"choices": [{"index": 0, "finish_reason": "stop"}]},
        ),
        (ProtocolKind.OPENAI_RESPONSES, {"type": "response.completed"}),
    ):
        capture = StreamCapture(capture_body=False, deadline=deadline)
        _record_stream_completion(protocol, capture, payload)
        capture.is_client_disconnected = True

        assert _describe_stream_capture_issue(capture) is None


def test_incomplete_responses_event_is_terminal_and_preserves_usage() -> None:
    capture = StreamCapture(
        capture_body=False,
        deadline=_RequestDeadline(0.0, 0.0, 0.0),
    )
    payload = {
        "type": "response.incomplete",
        "response": {
            "model": "gpt-test",
            "status": "incomplete",
            "usage": {
                "input_tokens": 7,
                "output_tokens": 3,
                "total_tokens": 10,
            },
        },
    }

    _record_stream_completion(ProtocolKind.OPENAI_RESPONSES, capture, payload)
    usage = _extract_stream_usage(
        ProtocolKind.OPENAI_RESPONSES,
        f"event: response.incomplete\ndata: {json.dumps(payload)}\n\n",
    )

    assert capture.protocol_completed is True
    assert _describe_stream_capture_issue(capture) is None
    assert usage == {
        "resolved_model": "gpt-test",
        "input_tokens": 7,
        "cache_read_input_tokens": 0,
        "cache_write_input_tokens": 0,
        "output_tokens": 3,
        "total_tokens": 10,
    }


def test_disconnect_before_responses_terminal_event_is_not_an_upstream_error() -> None:
    capture = StreamCapture(
        capture_body=False,
        deadline=_RequestDeadline(0.0, 0.0, 0.0),
        is_client_disconnected=True,
    )

    assert _describe_stream_capture_issue(capture) is None
