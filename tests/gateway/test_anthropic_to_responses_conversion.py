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
from lens_api.models import ProtocolKind


def test_responses_channel_can_serve_anthropic_clients() -> None:
    matrix = build_protocol_conversion_matrix()

    assert ProtocolKind.ANTHROPIC.value in matrix[ProtocolKind.OPENAI_RESPONSES.value]


def test_anthropic_request_converts_messages_tools_and_adaptive_thinking() -> None:
    converted = convert_request(
        ProtocolKind.ANTHROPIC,
        ProtocolKind.OPENAI_RESPONSES,
        {
            "model": "claude-alias",
            "system": [{"type": "text", "text": "Be precise."}],
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
                        {
                            "type": "tool_result",
                            "tool_use_id": "call_1",
                            "content": [
                                {"type": "text", "text": "found"},
                                {
                                    "type": "image",
                                    "source": {
                                        "type": "url",
                                        "url": "https://example.test/result.png",
                                    },
                                },
                            ],
                        }
                    ],
                },
            ],
            "max_tokens": 4096,
            "stream": True,
            "thinking": {"type": "adaptive"},
            "output_config": {"effort": "high"},
            "tools": [
                {
                    "name": "lookup",
                    "description": "Look up a value",
                    "input_schema": {
                        "type": "object",
                        "properties": {"query": {"type": "string"}},
                    },
                    "strict": True,
                }
            ],
            "tool_choice": {
                "type": "any",
                "disable_parallel_tool_use": True,
            },
            "metadata": {"user_id": "user-1"},
            "stop_sequences": ["ignored"],
        },
        "responses-model",
    )

    assert converted == {
        "model": "responses-model",
        "input": [
            {"role": "system", "content": "Be precise."},
            {
                "type": "function_call",
                "call_id": "call_1",
                "name": "lookup",
                "arguments": '{"query": "lens"}',
            },
            {
                "type": "function_call_output",
                "call_id": "call_1",
                "output": [
                    {"type": "input_text", "text": "found"},
                    {
                        "type": "input_image",
                        "image_url": "https://example.test/result.png",
                    },
                ],
            },
        ],
        "max_output_tokens": 4096,
        "stream": True,
        "store": False,
        "include": ["reasoning.encrypted_content"],
        "reasoning": {"effort": "high", "summary": "auto"},
        "tools": [
            {
                "type": "function",
                "name": "lookup",
                "description": "Look up a value",
                "parameters": {
                    "type": "object",
                    "properties": {"query": {"type": "string"}},
                },
                "strict": True,
            }
        ],
        "tool_choice": "required",
        "parallel_tool_calls": False,
        "safety_identifier": "user-1",
    }


def test_legacy_thinking_budget_enables_summary_without_guessing_effort() -> None:
    converted = convert_request(
        ProtocolKind.ANTHROPIC,
        ProtocolKind.OPENAI_RESPONSES,
        {
            "messages": [{"role": "user", "content": "Hello"}],
            "max_tokens": 8192,
            "thinking": {"type": "enabled", "budget_tokens": 4096},
        },
    )

    assert converted["max_output_tokens"] == 8192
    assert converted["reasoning"] == {"summary": "auto"}


def test_output_effort_preserves_stateless_reasoning() -> None:
    converted = convert_request(
        ProtocolKind.ANTHROPIC,
        ProtocolKind.OPENAI_RESPONSES,
        {
            "messages": [{"role": "user", "content": "Hello"}],
            "max_tokens": 100,
            "output_config": {"effort": "high"},
        },
    )

    assert converted["reasoning"] == {"effort": "high"}
    assert converted["include"] == ["reasoning.encrypted_content"]


def test_anthropic_request_converts_documents_and_disables_reasoning() -> None:
    converted = convert_request(
        ProtocolKind.ANTHROPIC,
        ProtocolKind.OPENAI_RESPONSES,
        {
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": "image/png",
                                "data": "aW1hZ2U=",
                            },
                        },
                        {
                            "type": "document",
                            "title": "guide.pdf",
                            "source": {
                                "type": "base64",
                                "media_type": "application/pdf",
                                "data": "cGRm",
                            },
                        },
                        {
                            "type": "document",
                            "source": {
                                "type": "url",
                                "url": "https://example.test/guide.pdf",
                            },
                        },
                        {
                            "type": "document",
                            "source": {"type": "text", "data": "Reference"},
                        },
                        {
                            "type": "document",
                            "source": {
                                "type": "content",
                                "content": [
                                    {"type": "text", "text": "Nested reference"}
                                ],
                            },
                        },
                    ],
                }
            ],
            "max_tokens": 100,
            "thinking": {"type": "disabled"},
            "tools": [
                {"type": "web_search_20250305", "name": "web_search"},
                {
                    "type": "custom",
                    "name": "lookup",
                    "input_schema": {"type": "object"},
                },
            ],
        },
    )

    assert converted["input"] == [
        {
            "role": "user",
            "content": [
                {
                    "type": "input_image",
                    "image_url": "data:image/png;base64,aW1hZ2U=",
                },
                {
                    "type": "input_file",
                    "file_data": "data:application/pdf;base64,cGRm",
                    "filename": "guide.pdf",
                },
                {
                    "type": "input_file",
                    "file_url": "https://example.test/guide.pdf",
                },
                {"type": "input_text", "text": "Reference"},
                {"type": "input_text", "text": "Nested reference"},
            ],
        }
    ]
    assert converted["reasoning"] == {"effort": "none"}
    assert "include" not in converted
    assert [tool["name"] for tool in converted["tools"]] == ["lookup"]


@pytest.mark.parametrize(
    "content",
    [
        [{"type": "image", "source": {"type": "file", "file_id": "file_1"}}],
        [{"type": "document", "source": {}}],
        [
            {
                "type": "tool_result",
                "tool_use_id": "call_1",
                "content": {"unexpected": "object"},
            }
        ],
    ],
)
def test_recognized_content_blocks_reject_unsupported_shapes(
    content: list[dict[str, object]],
) -> None:
    with pytest.raises(ValueError, match="Anthropic"):
        convert_request(
            ProtocolKind.ANTHROPIC,
            ProtocolKind.OPENAI_RESPONSES,
            {
                "messages": [{"role": "user", "content": content}],
                "max_tokens": 100,
            },
        )


def test_unsupported_named_server_tool_is_rejected() -> None:
    with pytest.raises(ValueError, match="unsupported tool"):
        convert_request(
            ProtocolKind.ANTHROPIC,
            ProtocolKind.OPENAI_RESPONSES,
            {
                "messages": [{"role": "user", "content": "Search"}],
                "max_tokens": 100,
                "tools": [{"type": "web_search_20250305", "name": "web_search"}],
                "tool_choice": {"type": "tool", "name": "web_search"},
            },
        )


def test_required_tool_choice_without_custom_tools_is_rejected() -> None:
    with pytest.raises(ValueError, match="supported custom tool"):
        convert_request(
            ProtocolKind.ANTHROPIC,
            ProtocolKind.OPENAI_RESPONSES,
            {
                "messages": [{"role": "user", "content": "Search"}],
                "max_tokens": 100,
                "tools": [{"type": "web_search_20250305", "name": "web_search"}],
                "tool_choice": {"type": "any"},
            },
        )


def test_responses_json_converts_reasoning_tools_refusal_and_usage() -> None:
    response = {
        "id": "resp_1",
        "status": "completed",
        "model": "responses-model",
        "output": [
            {
                "type": "reasoning",
                "id": "rs_1",
                "status": "completed",
                "summary": [{"type": "summary_text", "text": "Checked inputs."}],
                "encrypted_content": "encrypted",
            },
            {
                "type": "message",
                "role": "assistant",
                "content": [
                    {"type": "output_text", "text": "Result"},
                    {"type": "refusal", "refusal": "Cannot continue"},
                ],
            },
            {
                "type": "function_call",
                "call_id": "call_1",
                "name": "lookup",
                "arguments": '{"query":"lens"}',
            },
        ],
        "usage": {
            "input_tokens": 20,
            "input_tokens_details": {
                "cached_tokens": 5,
                "cache_write_tokens": 3,
            },
            "output_tokens": 8,
            "output_tokens_details": {"reasoning_tokens": 4},
            "total_tokens": 28,
        },
    }

    converted = json.loads(
        convert_response(
            ProtocolKind.ANTHROPIC,
            ProtocolKind.OPENAI_RESPONSES,
            json.dumps(response).encode(),
        )
    )

    assert converted["content"][0]["type"] == "thinking"
    assert converted["content"][0]["thinking"] == "Checked inputs."
    assert converted["content"][0]["signature"].startswith(
        "lens-responses-reasoning-v1:"
    )
    assert converted["content"][1:] == [
        {"type": "text", "text": "Result"},
        {"type": "text", "text": "Cannot continue"},
        {
            "type": "tool_use",
            "id": "call_1",
            "name": "lookup",
            "input": {"query": "lens"},
        },
    ]
    assert converted["stop_reason"] == "tool_use"
    assert converted["usage"] == {
        "input_tokens": 12,
        "cache_creation_input_tokens": 3,
        "cache_read_input_tokens": 5,
        "output_tokens": 8,
        "output_tokens_details": {"thinking_tokens": 4},
    }

    continued = convert_request(
        ProtocolKind.ANTHROPIC,
        ProtocolKind.OPENAI_RESPONSES,
        {
            "messages": [
                {
                    "role": "assistant",
                    "content": [converted["content"][0], converted["content"][3]],
                },
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "tool_result",
                            "tool_use_id": "call_1",
                            "content": "done",
                        }
                    ],
                },
            ],
            "max_tokens": 100,
        },
    )
    assert continued["input"][0] == response["output"][0]
    assert continued["input"][1] == {
        "type": "function_call",
        "call_id": "call_1",
        "name": "lookup",
        "arguments": '{"query": "lens"}',
    }


def test_incomplete_response_does_not_expose_partial_tool_call_as_ready() -> None:
    response = {
        "id": "resp_1",
        "status": "incomplete",
        "incomplete_details": {"reason": "max_output_tokens"},
        "output": [
            {
                "type": "function_call",
                "call_id": "call_1",
                "name": "lookup",
                "arguments": "{}",
            }
        ],
    }

    converted = json.loads(
        convert_response(
            ProtocolKind.ANTHROPIC,
            ProtocolKind.OPENAI_RESPONSES,
            json.dumps(response).encode(),
        )
    )

    assert converted["stop_reason"] == "max_tokens"


def test_reasoning_without_summary_uses_redacted_thinking_and_round_trips() -> None:
    reasoning = {
        "type": "reasoning",
        "id": "rs_1",
        "summary": [],
        "encrypted_content": "encrypted",
        "status": "completed",
    }
    response = {
        "id": "resp_1",
        "status": "completed",
        "model": "responses-model",
        "output": [reasoning],
    }

    converted = json.loads(
        convert_response(
            ProtocolKind.ANTHROPIC,
            ProtocolKind.OPENAI_RESPONSES,
            json.dumps(response).encode(),
        )
    )

    assert converted["content"][0]["type"] == "redacted_thinking"
    continued = convert_request(
        ProtocolKind.ANTHROPIC,
        ProtocolKind.OPENAI_RESPONSES,
        {
            "messages": [
                {"role": "assistant", "content": converted["content"]},
                {"role": "user", "content": "Continue"},
            ],
            "max_tokens": 100,
        },
    )
    assert continued["input"][0] == reasoning
    assert continued["include"] == ["reasoning.encrypted_content"]


def test_responses_usage_rejects_cache_tokens_exceeding_input_tokens() -> None:
    response = {
        "id": "resp_1",
        "status": "completed",
        "output": [],
        "usage": {
            "input_tokens": 3,
            "input_tokens_details": {
                "cached_tokens": 2,
                "cache_write_tokens": 2,
            },
            "output_tokens": 0,
        },
    }

    with pytest.raises(ValueError, match="cache token counts"):
        convert_response(
            ProtocolKind.ANTHROPIC,
            ProtocolKind.OPENAI_RESPONSES,
            json.dumps(response).encode(),
        )


async def _responses_stream() -> AsyncIterator[bytes]:
    frames = [
        {
            "type": "response.created",
            "response": {"id": "resp_1", "model": "responses-model"},
        },
        {
            "type": "response.output_item.added",
            "output_index": 0,
            "item": {"type": "reasoning", "id": "rs_1", "summary": []},
        },
        {
            "type": "response.reasoning_summary_text.delta",
            "output_index": 0,
            "summary_index": 0,
            "delta": "Checked.",
        },
        {
            "type": "response.output_item.done",
            "output_index": 0,
            "item": {
                "type": "reasoning",
                "id": "rs_1",
                "status": "completed",
                "summary": [{"type": "summary_text", "text": "Checked."}],
                "encrypted_content": "encrypted",
            },
        },
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
            "type": "response.output_item.done",
            "output_index": 1,
            "item": {
                "type": "function_call",
                "call_id": "call_1",
                "name": "lookup",
                "arguments": '{"query":"lens"}',
            },
        },
        {
            "type": "response.completed",
            "response": {
                "id": "resp_1",
                "model": "responses-model",
                "status": "completed",
                "output": [{"type": "function_call"}],
                "usage": {"input_tokens": 10, "output_tokens": 6},
            },
        },
    ]
    yield "".join(
        f"event: {frame['type']}\ndata: {json.dumps(frame)}\n\n" for frame in frames
    ).encode()


def test_responses_stream_converts_reasoning_tools_and_terminal_usage() -> None:
    async def collect() -> str:
        return b"".join(
            [
                chunk
                async for chunk in convert_stream_iterator(
                    ProtocolKind.ANTHROPIC,
                    ProtocolKind.OPENAI_RESPONSES,
                    _responses_stream(),
                )
            ]
        ).decode()

    raw = run_async(collect())
    payloads = [
        json.loads(line.removeprefix("data: "))
        for line in raw.splitlines()
        if line.startswith("data: {")
    ]

    assert payloads[0]["type"] == "message_start"
    assert any(
        payload.get("delta", {}).get("type") == "thinking_delta" for payload in payloads
    )
    assert any(
        payload.get("delta", {}).get("type") == "signature_delta"
        for payload in payloads
    )
    assert any(
        payload.get("content_block", {}).get("type") == "tool_use"
        for payload in payloads
    )
    message_delta = next(
        payload for payload in payloads if payload["type"] == "message_delta"
    )
    assert message_delta["delta"]["stop_reason"] == "tool_use"
    assert message_delta["usage"] == {"input_tokens": 10, "output_tokens": 6}
    assert payloads[-1] == {"type": "message_stop"}


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
def test_responses_anthropic_stream_rejects_failures_and_malformed_terminal(
    frame: dict[str, object],
) -> None:
    async def raw_stream() -> AsyncIterator[bytes]:
        yield f"event: {frame['type']}\ndata: {json.dumps(frame)}\n\n".encode()

    async def collect() -> None:
        async for _ in convert_stream_iterator(
            ProtocolKind.ANTHROPIC,
            ProtocolKind.OPENAI_RESPONSES,
            raw_stream(),
        ):
            pass

    with pytest.raises(ValueError):
        run_async(collect())


def test_responses_anthropic_stream_requires_text_event_indices() -> None:
    async def raw_stream() -> AsyncIterator[bytes]:
        frames = [
            {
                "type": "response.created",
                "response": {"id": "resp_1", "model": "responses-model"},
            },
            {
                "type": "response.output_text.delta",
                "output_index": 0,
                "delta": "Hello",
            },
        ]
        yield "".join(
            f"event: {frame['type']}\ndata: {json.dumps(frame)}\n\n" for frame in frames
        ).encode()

    async def collect() -> None:
        async for _ in convert_stream_iterator(
            ProtocolKind.ANTHROPIC,
            ProtocolKind.OPENAI_RESPONSES,
            raw_stream(),
        ):
            pass

    with pytest.raises(ValueError, match="content_index"):
        run_async(collect())
