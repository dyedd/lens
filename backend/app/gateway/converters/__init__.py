"""Protocol conversion dispatch.

Every convertible protocol contributes two spoke functions: a parser that
reads its own wire payload into the unified protocol (``unified.py``,
``unified_response.py``, ``unified_stream.py``) and a builder that writes the
unified value back out. Any client/upstream pair is therefore served by
composing one parser with one builder, so adding a protocol costs two
functions instead of converters for every existing pair.

Same-protocol requests and responses never reach this module: the caller
forwards them byte-for-byte, which keeps prompt caching, provider built-in
tools and server-side state (``previous_response_id``) intact.
"""

import json
from collections.abc import AsyncIterator, Callable, Mapping
from dataclasses import dataclass, replace
from typing import Any

from ...core.protocol_reachability import can_reach_protocol
from ...models.protocols import ProtocolKind
from . import capabilities
from .chat_stream import repair_chat_tool_call_stream
from .responses_common import is_reasoning_envelope
from .signatures import FOREIGN_THINKING_SIGNATURE, fits
from .unified import ToolCallPart, ToolDefinition, ToolKind, UnifiedRequest
from .unified_response import UnifiedResponse
from .unified_stream import BlockKind, BlockStart, StreamEvent

__all__ = [
    "ConvertedRequest",
    "can_reach_protocol",
    "convert_request",
    "convert_response",
    "convert_stream_iterator",
    "needs_protocol_conversion",
    "repair_chat_tool_call_stream",
    "strip_foreign_reasoning",
]


@dataclass(frozen=True, slots=True)
class ConvertedRequest:
    """转换后的请求与本次尝试使用的工具身份。"""

    body: dict[str, Any]
    tool_mapping: dict[str, ToolDefinition]


@dataclass(frozen=True, slots=True)
class Spoke:
    """One protocol's wire readers and writers for the unified protocol."""

    parse_request: Callable[[dict[str, Any]], UnifiedRequest]
    build_request: Callable[[UnifiedRequest], dict[str, Any]]
    parse_response: Callable[[dict[str, Any]], UnifiedResponse]
    build_response: Callable[[UnifiedResponse], dict[str, Any]]
    parse_stream: Callable[[AsyncIterator[bytes]], AsyncIterator[StreamEvent]]
    build_stream: Callable[[AsyncIterator[StreamEvent], str], AsyncIterator[bytes]]


def _spokes() -> dict[ProtocolKind, Spoke]:
    """Build the protocol registry at import time as the converter composition root."""
    from .spoke_anthropic import (
        build_anthropic_request,
        build_anthropic_response,
        parse_anthropic_request,
        parse_anthropic_response,
        parse_anthropic_stream,
        serialize_anthropic_stream,
    )
    from .spoke_chat import (
        build_chat_request,
        build_chat_response,
        parse_chat_request,
        parse_chat_response,
    )
    from .spoke_chat_stream import parse_chat_stream, serialize_chat_stream
    from .spoke_gemini import (
        build_gemini_request,
        build_gemini_response,
        parse_gemini_request,
        parse_gemini_response,
        parse_gemini_stream,
        serialize_gemini_stream,
    )
    from .spoke_responses import (
        build_responses_request,
        build_responses_response,
        parse_responses_request,
        parse_responses_response,
        parse_responses_stream,
        serialize_responses_stream,
    )

    return {
        ProtocolKind.OPENAI_CHAT: Spoke(
            parse_request=parse_chat_request,
            build_request=build_chat_request,
            parse_response=parse_chat_response,
            build_response=build_chat_response,
            parse_stream=parse_chat_stream,
            build_stream=serialize_chat_stream,
        ),
        ProtocolKind.OPENAI_RESPONSES: Spoke(
            parse_request=parse_responses_request,
            build_request=build_responses_request,
            parse_response=parse_responses_response,
            build_response=build_responses_response,
            parse_stream=parse_responses_stream,
            build_stream=serialize_responses_stream,
        ),
        ProtocolKind.ANTHROPIC: Spoke(
            parse_request=parse_anthropic_request,
            build_request=build_anthropic_request,
            parse_response=parse_anthropic_response,
            build_response=build_anthropic_response,
            parse_stream=parse_anthropic_stream,
            build_stream=serialize_anthropic_stream,
        ),
        ProtocolKind.GEMINI: Spoke(
            parse_request=parse_gemini_request,
            build_request=build_gemini_request,
            parse_response=parse_gemini_response,
            build_response=build_gemini_response,
            parse_stream=parse_gemini_stream,
            build_stream=serialize_gemini_stream,
        ),
    }


_SPOKES = _spokes()


def spoke_for(protocol: ProtocolKind) -> Spoke:
    spoke = _SPOKES.get(protocol)
    if spoke is None:
        raise ValueError(f"Unsupported conversion protocol: {protocol.value}")
    return spoke


def needs_protocol_conversion(
    client_protocol: ProtocolKind, channel_protocol: ProtocolKind
) -> bool:
    """Whether a request must pass through the conversion layer."""
    return client_protocol != channel_protocol


def _check_reachable(
    client_protocol: ProtocolKind, channel_protocol: ProtocolKind
) -> None:
    if not can_reach_protocol(channel_protocol, client_protocol):
        raise ValueError(
            f"Unsupported conversion: {client_protocol.value} -> {channel_protocol.value}"
        )


def convert_request(
    client_protocol: ProtocolKind,
    channel_protocol: ProtocolKind,
    body: dict[str, Any],
    target_model: str | None = None,
    preserve_reasoning: bool = False,
) -> ConvertedRequest:
    """Convert a client request into the selected upstream protocol."""
    _check_reachable(client_protocol, channel_protocol)
    request = spoke_for(client_protocol).parse_request(dict(body))
    request.origin = client_protocol
    request.replay_reasoning = preserve_reasoning
    if target_model:
        request.model = target_model
    tool_mapping: dict[str, ToolDefinition] = {}
    if channel_protocol is not ProtocolKind.OPENAI_RESPONSES:
        for tool in request.tools:
            name = capabilities.namespaced_name(tool.namespace, tool.name)
            previous = tool_mapping.get(name)
            if previous is not None and (
                previous.name != tool.name
                or previous.namespace != tool.namespace
                or previous.kind != tool.kind
            ):
                raise ValueError(f"Tool names collide in upstream protocol: {name}")
            tool_mapping[name] = tool
    result = spoke_for(channel_protocol).build_request(request)
    if target_model:
        result["model"] = target_model
    # Upstream transport reads this flag to pick the streaming endpoint, so it
    # holds for every target protocol; Gemini drops it from the final payload.
    if request.stream:
        result["stream"] = True
    return ConvertedRequest(body=result, tool_mapping=tool_mapping)


def strip_foreign_reasoning(
    body: dict[str, Any], protocol: ProtocolKind, target_model: str
) -> dict[str, Any]:
    """Drop sealed reasoning the target cannot read.

    A same-protocol request is forwarded untouched, but its history can still
    hold state another protocol or provider sealed: a Lens envelope written on
    an earlier hop, or a blob sealed with another provider's key. Replaying
    either makes the upstream reject the whole request, so it is removed here.
    """
    if protocol is ProtocolKind.ANTHROPIC:
        return _strip_anthropic_thinking(body, target_model)
    if protocol is ProtocolKind.OPENAI_RESPONSES:
        return _strip_responses_reasoning(body, target_model)
    return body


def _strip_anthropic_thinking(
    body: dict[str, Any], target_model: str
) -> dict[str, Any]:
    messages = body.get("messages")
    if not isinstance(messages, list):
        return body

    kept: list[Any] = []
    for message in messages:
        content = message.get("content") if isinstance(message, dict) else None
        if not isinstance(content, list):
            kept.append(message)
            continue
        blocks = [
            block for block in content if not _foreign_anthropic(block, target_model)
        ]
        if len(blocks) == len(content):
            kept.append(message)
        elif blocks:
            kept.append({**message, "content": blocks})
    return {**body, "messages": kept}


def _foreign_anthropic(block: Any, target_model: str) -> bool:
    if not isinstance(block, dict):
        return False
    field = {"thinking": "signature", "redacted_thinking": "data"}.get(
        block.get("type", "")
    )
    value = block.get(field) if field else None
    if not isinstance(value, str) or not value:
        return False
    return (
        value == FOREIGN_THINKING_SIGNATURE
        or is_reasoning_envelope(value)
        or not fits(value, target_model)
    )


def _strip_responses_reasoning(
    body: dict[str, Any], target_model: str
) -> dict[str, Any]:
    items = body.get("input")
    if not isinstance(items, list):
        return body
    return {
        **body,
        "input": [item for item in items if not _foreign_response(item, target_model)],
    }


def _foreign_response(item: Any, target_model: str) -> bool:
    if not isinstance(item, dict) or item.get("type") != "reasoning":
        return False
    value = item.get("encrypted_content")
    return isinstance(value, str) and bool(value) and not fits(value, target_model)


def convert_response(
    client_protocol: ProtocolKind,
    channel_protocol: ProtocolKind,
    response_body: bytes,
    original_model: str = "",
    *,
    tool_mapping: Mapping[str, ToolDefinition] | None = None,
) -> bytes:
    """Convert an upstream response into the client protocol."""
    _check_reachable(client_protocol, channel_protocol)
    body = json.loads(response_body)
    response = spoke_for(channel_protocol).parse_response(body)
    if not response.model:
        response.model = original_model
    if tool_mapping:
        for part in response.parts:
            if not isinstance(part, ToolCallPart):
                continue
            tool = tool_mapping.get(part.name)
            if tool is None:
                continue
            part.name, part.namespace, part.kind = tool.name, tool.namespace, tool.kind
            if tool.kind is ToolKind.CUSTOM:
                part.arguments = capabilities.unwrap_custom_tool_input(part.arguments)
    converted = spoke_for(client_protocol).build_response(response)
    return json.dumps(converted, ensure_ascii=False).encode("utf-8")


async def convert_stream_iterator(
    client_protocol: ProtocolKind,
    channel_protocol: ProtocolKind,
    raw_iterator: AsyncIterator[bytes],
    original_model: str = "",
    *,
    tool_mapping: Mapping[str, ToolDefinition] | None = None,
) -> AsyncIterator[bytes]:
    """Convert an upstream byte stream into the client protocol stream."""
    _check_reachable(client_protocol, channel_protocol)

    async def events() -> AsyncIterator[StreamEvent]:
        async for event in spoke_for(channel_protocol).parse_stream(raw_iterator):
            if (
                tool_mapping
                and isinstance(event, BlockStart)
                and event.kind is BlockKind.TOOL_CALL
                and (tool := tool_mapping.get(event.name)) is not None
            ):
                event = replace(
                    event,
                    name=tool.name,
                    namespace=tool.namespace,
                    tool_kind=tool.kind,
                )
            yield event

    stream = spoke_for(client_protocol).build_stream(events(), original_model)
    async for chunk in stream:
        yield chunk
