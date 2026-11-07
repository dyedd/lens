"""Chat Completions streaming spoke: SSE bytes <-> unified stream events.

Parsing reuses ``ChatToolCalls`` so the malformed-index and split-argument
repairs that Chat upstreams need apply on the way in, and writing reuses the
same accumulator shape so an IR stream becomes a well-formed chat SSE stream.
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator, Mapping
from typing import Any

from .chat_response import (
    parse_chat_finish_reason,
    parse_chat_usage,
    serialize_chat_finish_reason,
    serialize_chat_usage,
)
from .chat_stream import ChatToolCall, ChatToolCalls, chat_choice_index
from .unified_stream import (
    BlockKind,
    BlockStart,
    CitationDelta,
    ReasoningDelta,
    RefusalDelta,
    ServerToolStatusDelta,
    StreamFinish,
    StreamStart,
    TextDelta,
    ToolCallArgsDelta,
)


async def parse_chat_stream(raw_iterator: AsyncIterator[bytes]) -> AsyncIterator[Any]:
    """Parse a chat SSE stream into unified stream events."""
    from .sse import parse_sse_json_stream

    started = False
    text_index: int | None = None
    reasoning_index: int | None = None
    next_index = 0
    tool_calls = ChatToolCalls()
    tool_blocks: dict[int, int] = {}
    announced: set[int] = set()
    finish_reason: str | None = None
    usage: dict[str, Any] = {}

    def allocate() -> int:
        nonlocal next_index
        index = next_index
        next_index += 1
        return index

    async for payload in parse_sse_json_stream(raw_iterator):
        if not started:
            started = True
            yield StreamStart(
                id=str(payload.get("id") or ""), model=str(payload.get("model") or "")
            )
        payload_usage = payload.get("usage")
        if isinstance(payload_usage, Mapping):
            usage = dict(payload_usage)
        choices = payload.get("choices")
        if not isinstance(choices, list):
            continue
        for choice in choices:
            if not isinstance(choice, Mapping):
                continue
            finish_reason = choice.get("finish_reason") or finish_reason
            delta = choice.get("delta")
            if not isinstance(delta, Mapping):
                continue
            reasoning = _chat_delta_reasoning(delta)
            if reasoning is not None:
                if reasoning_index is None:
                    reasoning_index = allocate()
                    yield BlockStart(index=reasoning_index, kind=BlockKind.REASONING)
                if reasoning:
                    yield ReasoningDelta(index=reasoning_index, text=reasoning)
            content = delta.get("content")
            if content:
                if not isinstance(content, str):
                    raise ValueError("Chat content delta must be a string")
                if text_index is None:
                    text_index = allocate()
                    yield BlockStart(index=text_index, kind=BlockKind.TEXT)
                yield TextDelta(index=text_index, text=content)
            for value in delta.get("tool_calls") or []:
                for tool_call in tool_calls.update_many(
                    value, choice_index=chat_choice_index(choice)
                ):
                    index = tool_blocks.get(tool_call.index)
                    if index is None:
                        index = allocate()
                        tool_blocks[tool_call.index] = index
                    if tool_call.index not in announced:
                        if not tool_call.call_id or not tool_call.name:
                            continue
                        announced.add(tool_call.index)
                        yield BlockStart(
                            index=index,
                            kind=BlockKind.TOOL_CALL,
                            call_id=tool_call.call_id,
                            name=tool_call.name,
                        )
                    arguments = tool_call.take_argument_delta()
                    if arguments:
                        yield ToolCallArgsDelta(index=index, arguments=arguments)

    for tool_call in tool_calls:
        index = tool_blocks.get(tool_call.index)
        if index is None or tool_call.index in announced:
            continue
        if not tool_call.call_id or not tool_call.name:
            raise ValueError("Chat tool call stream ended without id")
        yield BlockStart(
            index=index,
            kind=BlockKind.TOOL_CALL,
            call_id=tool_call.call_id,
            name=tool_call.name,
        )
        arguments = tool_call.take_argument_delta()
        if arguments:
            yield ToolCallArgsDelta(index=index, arguments=arguments)

    yield StreamFinish(
        reason=parse_chat_finish_reason(finish_reason),
        usage=parse_chat_usage(usage),
    )


async def serialize_chat_stream(
    events: AsyncIterator[Any], original_model: str
) -> AsyncIterator[bytes]:
    """Serialize unified stream events into a chat SSE stream."""
    import time
    import uuid

    stream_id = f"chatcmpl-{uuid.uuid4().hex[:24]}"
    created = int(time.time())
    model = original_model
    tool_calls: dict[int, ChatToolCall] = {}
    announced: set[int] = set()
    finish_reason = "stop"
    usage: dict[str, Any] = {}

    def chunk(
        delta: dict[str, Any],
        *,
        finish: str | None = None,
        with_usage: bool = False,
    ) -> bytes:
        payload: dict[str, Any] = {
            "id": stream_id,
            "object": "chat.completion.chunk",
            "created": created,
            "model": model,
            "choices": (
                []
                if with_usage
                else [{"index": 0, "delta": delta, "finish_reason": finish}]
            ),
        }
        if with_usage:
            payload["usage"] = usage
        return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n".encode()

    yield chunk({"role": "assistant", "content": ""})
    async for event in events:
        if isinstance(event, StreamStart):
            model = event.model or model
            continue
        if isinstance(event, BlockStart):
            if event.kind == BlockKind.TOOL_CALL:
                tool_calls[event.index] = ChatToolCall(
                    index=len(tool_calls), call_id=event.call_id, name=event.name
                )
            continue
        if isinstance(event, TextDelta):
            if not event.text:
                # Strict clients (AI SDK, Qoder) treat an empty content delta as
                # a protocol error, and it carries no information anyway.
                continue
            yield chunk({"content": event.text})
            continue
        if isinstance(event, ReasoningDelta):
            if not event.text:
                # ``reasoning_content: ""`` is the classic cause of a rejected
                # stream; a real reasoning delta always has text.
                continue
            yield chunk({"reasoning_content": event.text})
            continue
        if isinstance(event, ToolCallArgsDelta):
            call = tool_calls.get(event.index)
            if call is None:
                raise ValueError("Chat tool call arguments arrived before its block")
            function: dict[str, Any] = {"arguments": event.arguments}
            delta: dict[str, Any] = {"function": function}
            if event.index not in announced:
                announced.add(event.index)
                delta["id"] = call.call_id
                delta["type"] = call.call_type or "function"
                function["name"] = call.name
            yield chunk({"tool_calls": [{"index": call.index, **delta}]})
            continue
        if isinstance(event, StreamFinish):
            finish_reason = serialize_chat_finish_reason(event.reason)
            usage = serialize_chat_usage(event.usage)
            continue
        if isinstance(event, RefusalDelta):
            # Chat has no refusal channel, so the refusal text streams as content
            # instead of being dropped.
            if event.text:
                yield chunk({"content": event.text})
            continue
        if isinstance(event, CitationDelta):
            # Chat has no annotation channel on a delta; the citation is folded
            # into the text so the source is not silently lost.
            url = event.citation.url
            if url:
                yield chunk({"content": f" [{url}]"})
            continue
        if isinstance(event, ServerToolStatusDelta):
            # Chat cannot express a provider tool lifecycle, so nothing streams.
            continue
    # A tool call whose upstream sent no argument delta still needs an identity
    # frame; otherwise the client never learns the call happened.
    for index in sorted(tool_calls):
        if index in announced:
            continue
        call = tool_calls[index]
        if not call.call_id and not call.name:
            continue
        announced.add(index)
        yield chunk(
            {
                "tool_calls": [
                    {
                        "index": call.index,
                        "id": call.call_id,
                        "type": call.call_type or "function",
                        "function": {"name": call.name, "arguments": "{}"},
                    }
                ]
            }
        )
    yield chunk({}, finish=finish_reason)
    yield chunk({}, with_usage=True)
    yield b"data: [DONE]\n\n"


def _chat_delta_reasoning(delta: Mapping[str, Any]) -> str | None:
    for key in ("reasoning_content", "reasoning"):
        value = delta.get(key)
        if isinstance(value, str):
            return value
    return None
