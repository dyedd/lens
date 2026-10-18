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
    """Import spokes lazily so protocol modules stay independently testable."""
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


def strip_foreign_reasoning(body: dict[str, Any]) -> dict[str, Any]:
    """Drop Anthropic thinking blocks that carry a foreign reasoning envelope.

    A client whose history passed through a Responses channel holds thinking
    blocks whose ``signature`` is a Lens envelope. Anthropic rejects those, so
    they are removed before a same-protocol request is forwarded.
    """
    messages = body.get("messages")
    if not isinstance(messages, list):
        return body

    cleaned: list[Any] = []
    changed = False
    for message in messages:
        if not isinstance(message, dict):
            cleaned.append(message)
            continue
        content = message.get("content")
        if not isinstance(content, list):
            cleaned.append(message)
            continue
        kept = [
            block
            for block in content
            if not (
                isinstance(block, dict)
                and (
                    (
                        block.get("type") == "thinking"
                        and is_reasoning_envelope(block.get("signature"))
                    )
                    or (
                        block.get("type") == "redacted_thinking"
                        and is_reasoning_envelope(block.get("data"))
                    )
                )
            )
        ]
        if len(kept) == len(content):
            cleaned.append(message)
            continue
        changed = True
        if kept:
            cleaned.append({**message, "content": kept})
    if not changed:
        return body
    return {**body, "messages": cleaned}


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
    *,
    include_usage: bool = False,
) -> AsyncIterator[bytes]:
    """Convert an upstream byte stream into the client protocol stream."""
    _check_reachable(client_protocol, channel_protocol)
    del include_usage
    events = _parse_upstream_stream(channel_protocol, raw_iterator)
    stream = spoke_for(client_protocol).build_stream(events, original_model)
    async for chunk in stream:
        yield chunk
