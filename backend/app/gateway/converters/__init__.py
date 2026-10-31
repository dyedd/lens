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
from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from ...core.protocol_reachability import can_reach_protocol
from ...models.protocols import ProtocolKind
from .chat_stream import repair_chat_tool_call_stream
from .responses_common import is_reasoning_envelope
from .signatures import fits

__all__ = [
    "can_reach_protocol",
    "convert_request",
    "convert_response",
    "convert_stream_iterator",
    "needs_protocol_conversion",
    "repair_chat_tool_call_stream",
    "strip_foreign_reasoning",
]

Parse = Callable[[dict[str, Any]], Any]
Build = Callable[[Any], dict[str, Any]]
ParseStream = Callable[[AsyncIterator[bytes]], AsyncIterator[Any]]
BuildStream = Callable[[AsyncIterator[Any], str], AsyncIterator[bytes]]


@dataclass(frozen=True, slots=True)
class Spoke:
    """One protocol's wire readers and writers for the unified protocol."""

    parse_request: Parse
    build_request: Build
    parse_response: Parse
    build_response: Build
    parse_stream: ParseStream
    build_stream: BuildStream


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
    from .spoke_gemini_interactions import (
        build_gemini_interaction_request,
        build_gemini_interaction_response,
        parse_gemini_interaction_request,
        parse_gemini_interaction_response,
        parse_gemini_interaction_stream,
        serialize_gemini_interaction_stream,
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
            parse_request=parse_gemini_interaction_request,
            build_request=build_gemini_interaction_request,
            parse_response=parse_gemini_interaction_response,
            build_response=build_gemini_interaction_response,
            parse_stream=parse_gemini_interaction_stream,
            build_stream=serialize_gemini_interaction_stream,
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


def _build_upstream_request(
    channel_protocol: ProtocolKind, request: Any
) -> dict[str, Any]:
    return spoke_for(channel_protocol).build_request(request)


def _parse_upstream_response(
    channel_protocol: ProtocolKind, body: dict[str, Any]
) -> Any:
    return spoke_for(channel_protocol).parse_response(body)


def _parse_upstream_stream(
    channel_protocol: ProtocolKind, raw_iterator: AsyncIterator[bytes]
) -> AsyncIterator[Any]:
    return spoke_for(channel_protocol).parse_stream(raw_iterator)


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
) -> dict[str, Any]:
    """Convert a client request into the selected upstream protocol."""
    _check_reachable(client_protocol, channel_protocol)
    request = spoke_for(client_protocol).parse_request(dict(body))
    request.origin = client_protocol
    request.replay_reasoning = preserve_reasoning
    if target_model:
        request.model = target_model
    result = _build_upstream_request(channel_protocol, request)
    if target_model:
        result["model"] = target_model
    # Upstream transport reads this flag to pick the streaming endpoint, so it
    # holds for every target protocol; Gemini drops it from the final payload.
    if request.stream:
        result["stream"] = True
    return result


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
    return is_reasoning_envelope(value) or not fits(value, target_model)


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
) -> bytes:
    """Convert an upstream response into the client protocol."""
    _check_reachable(client_protocol, channel_protocol)
    body = json.loads(response_body)
    response = _parse_upstream_response(channel_protocol, body)
    if not response.model:
        response.model = original_model
    converted = spoke_for(client_protocol).build_response(response)
    return json.dumps(converted, ensure_ascii=False).encode("utf-8")


async def convert_stream_iterator(
    client_protocol: ProtocolKind,
    channel_protocol: ProtocolKind,
    raw_iterator: AsyncIterator[bytes],
    original_model: str = "",
) -> AsyncIterator[bytes]:
    """Convert an upstream byte stream into the client protocol stream."""
    _check_reachable(client_protocol, channel_protocol)
    events = _parse_upstream_stream(channel_protocol, raw_iterator)
    stream = spoke_for(client_protocol).build_stream(events, original_model)
    async for chunk in stream:
        yield chunk
