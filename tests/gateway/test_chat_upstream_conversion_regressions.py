from __future__ import annotations

import importlib
import json
from collections.abc import AsyncIterator

import pytest
from conftest import run_async

from lens_api.gateway.converters import (
    convert_request,
    convert_response,
    convert_stream_iterator,
)
from lens_api.models import ProtocolKind


def test_anthropic_rich_tool_result_preserves_parts_and_tool_adjacency() -> None:
    converted = convert_request(
        ProtocolKind.ANTHROPIC,
        ProtocolKind.OPENAI_CHAT,
        {
            "messages": [
                {
                    "role": "assistant",
                    "content": [
                        {
                            "type": "tool_use",
                            "id": "call_1",
                            "name": "lookup",
                            "input": {"query": "lens"},
                        }
                    ],
                },
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "Continue after the result."},
                        {
                            "type": "tool_result",
                            "tool_use_id": "call_1",
                            "content": [
                                {"type": "text", "text": "Found it."},
                                {
                                    "type": "image",
                                    "source": {
                                        "type": "url",
                                        "url": "https://example.test/result.png",
                                    },
                                },
                                {
                                    "type": "document",
                                    "title": "result.pdf",
                                    "source": {
                                        "type": "base64",
                                        "media_type": "application/pdf",
                                        "data": "cGRm",
                                    },
                                },
                            ],
                        },
                    ],
                },
            ]
        },
    )

    assert converted["messages"] == [
        {
            "role": "assistant",
            "content": None,
            "tool_calls": [
                {
                    "id": "call_1",
                    "type": "function",
                    "function": {
                        "name": "lookup",
                        "arguments": '{"query": "lens"}',
                    },
                }
            ],
        },
        {
            "role": "tool",
            "tool_call_id": "call_1",
            "content": [
                {"type": "text", "text": "Found it."},
                {
                    "type": "image_url",
                    "image_url": {"url": "https://example.test/result.png"},
                },
                {
                    "type": "file",
                    "file": {
                        "file_data": "data:application/pdf;base64,cGRm",
                        "filename": "result.pdf",
                    },
                },
            ],
        },
        {"role": "user", "content": "Continue after the result."},
    ]


def test_responses_parallel_calls_are_merged_and_outputs_stay_adjacent() -> None:
    converted = convert_request(
        ProtocolKind.OPENAI_RESPONSES,
        ProtocolKind.OPENAI_CHAT,
        {
            "input": [
                {
                    "type": "function_call",
                    "call_id": "call_1",
                    "name": "first",
                    "arguments": "{}",
                },
                {
                    "type": "function_call",
                    "call_id": "call_2",
                    "name": "second",
                    "arguments": '{"value":2}',
                },
                {
                    "type": "message",
                    "role": "user",
                    "content": "This must follow the tool outputs.",
                },
                {
                    "type": "function_call_output",
                    "call_id": "call_1",
                    "output": "one",
                },
                {
                    "type": "function_call_output",
                    "call_id": "call_2",
                    "output": "two",
                },
            ]
        },
    )

    messages = converted["messages"]
    assert [message["role"] for message in messages] == [
        "assistant",
        "tool",
        "tool",
        "user",
    ]
    assert [call["id"] for call in messages[0]["tool_calls"]] == [
        "call_1",
        "call_2",
    ]
    assert [message.get("tool_call_id") for message in messages[1:3]] == [
        "call_1",
        "call_2",
    ]


def test_responses_interleaved_call_groups_keep_each_output_adjacent() -> None:
    converted = convert_request(
        ProtocolKind.OPENAI_RESPONSES,
        ProtocolKind.OPENAI_CHAT,
        {
            "input": [
                {
                    "type": "function_call",
                    "call_id": "call_1",
                    "name": "first",
                    "arguments": "{}",
                },
                {"type": "message", "role": "user", "content": "after first"},
                {
                    "type": "function_call",
                    "call_id": "call_2",
                    "name": "second",
                    "arguments": "{}",
                },
                {"type": "message", "role": "user", "content": "after second"},
                {
                    "type": "function_call_output",
                    "call_id": "call_1",
                    "output": "one",
                },
                {
                    "type": "function_call_output",
                    "call_id": "call_2",
                    "output": "two",
                },
            ]
        },
    )

    messages = converted["messages"]
    assert [message["role"] for message in messages] == [
        "assistant",
        "tool",
        "user",
        "assistant",
        "tool",
        "user",
    ]
    assert [messages[1]["tool_call_id"], messages[4]["tool_call_id"]] == [
        "call_1",
        "call_2",
    ]


def test_reversible_chat_generation_parameters_are_preserved() -> None:
    responses_request = convert_request(
        ProtocolKind.OPENAI_RESPONSES,
        ProtocolKind.OPENAI_CHAT,
        {
            "input": "hello",
            "reasoning": {"effort": "high"},
            "text": {
                "format": {
                    "type": "json_schema",
                    "name": "result",
                    "schema": {"type": "object"},
                    "strict": True,
                }
            },
        },
    )
    chat_request = convert_request(
        ProtocolKind.OPENAI_CHAT,
        ProtocolKind.OPENAI_RESPONSES,
        {"messages": [], "max_tokens": 128},
    )

    assert responses_request["reasoning_effort"] == "high"
    assert responses_request["response_format"] == {
        "type": "json_schema",
        "json_schema": {
            "name": "result",
            "schema": {"type": "object"},
            "strict": True,
        },
    }
    assert chat_request["max_output_tokens"] == 128


@pytest.mark.parametrize(
    ("client_protocol", "body", "message"),
    [
        (
            ProtocolKind.ANTHROPIC,
            {"messages": ["not-an-object"]},
            "messages must contain objects",
        ),
        (
            ProtocolKind.OPENAI_RESPONSES,
            {"input": ["not-an-object"]},
            "input must contain objects",
        ),
        (
            ProtocolKind.ANTHROPIC,
            {
                "messages": [
                    {
                        "role": "user",
                        "content": [{"type": "unknown_block"}],
                    }
                ]
            },
            "Unsupported Anthropic content block type",
        ),
        (
            ProtocolKind.OPENAI_RESPONSES,
            {
                "input": [
                    {
                        "type": "message",
                        "role": "user",
                        "content": [{"type": "unknown_part"}],
                    }
                ]
            },
            "Unsupported Responses content part type",
        ),
    ],
)
def test_chat_upstream_requests_reject_malformed_or_unsupported_input(
    client_protocol: ProtocolKind,
    body: dict[str, object],
    message: str,
) -> None:
    with pytest.raises(ValueError, match=message):
        convert_request(client_protocol, ProtocolKind.OPENAI_CHAT, body)


def test_anthropic_to_responses_rejects_unknown_content_blocks() -> None:
    with pytest.raises(ValueError, match="Unsupported Anthropic content block type"):
        convert_request(
            ProtocolKind.ANTHROPIC,
            ProtocolKind.OPENAI_RESPONSES,
            {
                "messages": [
                    {
                        "role": "user",
                        "content": [{"type": "unknown_block"}],
                    }
                ]
            },
        )


def test_chat_length_response_is_consistently_incomplete() -> None:
    converted = json.loads(
        convert_response(
            ProtocolKind.OPENAI_RESPONSES,
            ProtocolKind.OPENAI_CHAT,
            json.dumps(
                {
                    "choices": [
                        {
                            "message": {"role": "assistant", "content": "Partial"},
                            "finish_reason": "length",
                        }
                    ]
                }
            ).encode(),
        )
    )

    assert converted["status"] == "incomplete"
    assert converted["incomplete_details"] == {"reason": "max_output_tokens"}
    assert converted["output"][0]["status"] == "incomplete"


async def _chat_stream(
    chunks: list[dict[str, object]], *, include_done: bool = True
) -> AsyncIterator[bytes]:
    payload = "".join(f"data: {json.dumps(chunk)}\n\n" for chunk in chunks)
    if include_done:
        payload += "data: [DONE]\n\n"
    split = max(1, len(payload) // 2)
    yield payload[:split].encode()
    yield payload[split:].encode()


async def _tool_chunk_then_fail() -> AsyncIterator[bytes]:
    yield (
        b'data: {"id":"chatcmpl_1","choices":[{"index":0,"delta":'
        b'{"tool_calls":[{"index":0,"id":"call_1","function":'
        b'{"name":"lookup","arguments":"{\\"query\\":\\"lens\\"}"}}]}}]}\n\n'
    )
    raise AssertionError("converter read past an emit-ready tool chunk")


def _sse_events(raw: bytes) -> list[tuple[str | None, dict[str, object] | str]]:
    events: list[tuple[str | None, dict[str, object] | str]] = []
    event_name: str | None = None
    for line in raw.decode().splitlines():
        if line.startswith("event: "):
            event_name = line.removeprefix("event: ")
        elif line.startswith("data: "):
            data = line.removeprefix("data: ")
            events.append((event_name, data if data == "[DONE]" else json.loads(data)))
            event_name = None
    return events


def test_fragmented_chat_tool_call_stays_one_anthropic_tool_block() -> None:
    chunks = [
        {
            "choices": [
                {
                    "index": 0,
                    "delta": {
                        "tool_calls": [
                            {
                                "index": 0,
                                "id": "call_1",
                                "function": {
                                    "name": "lookup",
                                    "arguments": '{"query":',
                                },
                            }
                        ]
                    },
                }
            ]
        },
        {
            "choices": [
                {
                    "index": 0,
                    "delta": {
                        "tool_calls": [
                            {
                                "index": 0,
                                "function": {"arguments": '"lens"}'},
                            }
                        ]
                    },
                    "finish_reason": "tool_calls",
                }
            ],
            "usage": {"completion_tokens": 3},
        },
    ]

    async def collect() -> bytes:
        return b"".join(
            [
                chunk
                async for chunk in convert_stream_iterator(
                    ProtocolKind.ANTHROPIC,
                    ProtocolKind.OPENAI_CHAT,
                    _chat_stream(chunks),
                    "client-model",
                )
            ]
        )

    events = _sse_events(run_async(collect()))
    starts = [
        data
        for event, data in events
        if event == "content_block_start"
        and isinstance(data, dict)
        and data["content_block"]["type"] == "tool_use"
    ]
    deltas = [
        data
        for event, data in events
        if event == "content_block_delta"
        and isinstance(data, dict)
        and data["delta"]["type"] == "input_json_delta"
    ]

    assert len(starts) == 1
    assert starts[0]["content_block"] == {
        "type": "tool_use",
        "id": "call_1",
        "name": "lookup",
        "input": {},
    }
    assert "".join(delta["delta"]["partial_json"] for delta in deltas) == (
        '{"query":"lens"}'
    )


@pytest.mark.parametrize(
    ("client_protocol", "headers", "expected_event"),
    [
        (ProtocolKind.ANTHROPIC, 2, "content_block_start"),
        (ProtocolKind.OPENAI_RESPONSES, 2, "response.output_item.added"),
    ],
)
def test_chat_tool_events_are_emitted_before_upstream_done(
    client_protocol: ProtocolKind,
    headers: int,
    expected_event: str,
) -> None:
    async def first_tool_event() -> bytes:
        converted = convert_stream_iterator(
            client_protocol,
            ProtocolKind.OPENAI_CHAT,
            _tool_chunk_then_fail(),
            "client-model",
        )
        try:
            for _ in range(headers):
                await anext(converted)
            return await anext(converted)
        finally:
            await converted.aclose()

    assert f"event: {expected_event}".encode() in run_async(first_tool_event())


def test_chat_length_stream_emits_complete_incomplete_responses_lifecycle(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    converter_module = importlib.import_module(
        "lens_api.gateway.converters.chat_to_responses"
    )
    timestamps = iter([100, 101, 102, 103])
    monkeypatch.setattr(converter_module.time, "time", lambda: next(timestamps))
    chunks = [
        {
            "id": "chatcmpl_1",
            "model": "upstream-model",
            "choices": [
                {"index": 0, "delta": {"content": "Hello"}, "finish_reason": None}
            ],
        },
        {
            "choices": [{"index": 0, "delta": {}, "finish_reason": "length"}],
            "usage": {"prompt_tokens": 4, "completion_tokens": 2},
        },
    ]

    async def collect() -> bytes:
        return b"".join(
            [
                chunk
                async for chunk in convert_stream_iterator(
                    ProtocolKind.OPENAI_RESPONSES,
                    ProtocolKind.OPENAI_CHAT,
                    _chat_stream(chunks),
                    "client-model",
                )
            ]
        )

    events = _sse_events(run_async(collect()))
    event_names = [event for event, _ in events]
    assert event_names == [
        "response.created",
        "response.in_progress",
        "response.output_item.added",
        "response.content_part.added",
        "response.output_text.delta",
        "response.output_text.done",
        "response.content_part.done",
        "response.output_item.done",
        "response.incomplete",
        None,
    ]
    terminal = events[-2][1]
    assert isinstance(terminal, dict)
    assert terminal["type"] == "response.incomplete"
    assert terminal["response"]["status"] == "incomplete"
    assert terminal["response"]["incomplete_details"] == {"reason": "max_output_tokens"}
    assert terminal["response"]["output"][0]["content"][0]["text"] == "Hello"
    response_events = [
        data
        for _, data in events
        if isinstance(data, dict) and isinstance(data.get("response"), dict)
    ]
    assert {event["response"]["created_at"] for event in response_events} == {100}
    numbered_events = [
        data for _, data in events if isinstance(data, dict) and "type" in data
    ]
    assert [event["sequence_number"] for event in numbered_events] == list(
        range(len(numbered_events))
    )


def test_fragmented_chat_tool_call_has_complete_responses_lifecycle() -> None:
    chunks = [
        {
            "id": "chatcmpl_1",
            "choices": [
                {
                    "index": 0,
                    "delta": {
                        "tool_calls": [
                            {
                                "index": 0,
                                "function": {
                                    "name": "lookup",
                                    "arguments": '{"query":',
                                },
                            }
                        ]
                    },
                }
            ],
        },
        {
            "choices": [
                {
                    "index": 0,
                    "delta": {
                        "tool_calls": [
                            {
                                "index": 0,
                                "id": "call_1",
                                "function": {"arguments": '"lens"}'},
                            }
                        ]
                    },
                    "finish_reason": "tool_calls",
                }
            ]
        },
    ]

    async def collect() -> bytes:
        return b"".join(
            [
                chunk
                async for chunk in convert_stream_iterator(
                    ProtocolKind.OPENAI_RESPONSES,
                    ProtocolKind.OPENAI_CHAT,
                    _chat_stream(chunks),
                    "client-model",
                )
            ]
        )

    events = _sse_events(run_async(collect()))
    event_names = [event for event, _ in events]
    assert event_names.count("response.output_item.added") == 1
    assert "response.function_call_arguments.done" in event_names
    assert "response.output_item.done" in event_names
    terminal = next(data for event, data in events if event == "response.completed")
    assert isinstance(terminal, dict)
    assert terminal["response"]["output"][0]["call_id"] == "call_1"
    assert terminal["response"]["output"][0]["arguments"] == '{"query":"lens"}'


@pytest.mark.parametrize(
    "client_protocol",
    [ProtocolKind.ANTHROPIC, ProtocolKind.OPENAI_RESPONSES],
)
def test_chat_stream_rejects_eof_before_done(client_protocol: ProtocolKind) -> None:
    async def collect() -> None:
        async for _ in convert_stream_iterator(
            client_protocol,
            ProtocolKind.OPENAI_CHAT,
            _chat_stream(
                [
                    {
                        "choices": [
                            {
                                "index": 0,
                                "delta": {"content": "partial"},
                                "finish_reason": "stop",
                            }
                        ]
                    }
                ],
                include_done=False,
            ),
        ):
            pass

    with pytest.raises(ValueError, match=r"before \[DONE\]"):
        run_async(collect())


def test_responses_stream_rejects_eof_before_terminal_event() -> None:
    async def incomplete_stream() -> AsyncIterator[bytes]:
        yield (
            b"event: response.created\n"
            b'data: {"type":"response.created","response":{"id":"resp_1"}}\n\n'
        )

    async def collect() -> None:
        async for _ in convert_stream_iterator(
            ProtocolKind.OPENAI_CHAT,
            ProtocolKind.OPENAI_RESPONSES,
            incomplete_stream(),
        ):
            pass

    with pytest.raises(ValueError, match="before terminal event"):
        run_async(collect())
