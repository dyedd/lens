"""Protocol conversion entry point.

Conversion direction: (channel/upstream protocol) -> (client protocol)
- OpenAI Chat (upstream) -> Anthropic (client)
- OpenAI Chat (upstream) -> OpenAI Responses (client)
"""

from __future__ import annotations

import json
from typing import Any, AsyncIterator

from ...models import ProtocolKind
from .chat_to_anthropic import (
    anthropic_request_to_chat,
    chat_response_to_anthropic,
    chat_stream_to_anthropic_stream,
)
from .chat_to_responses import (
    chat_response_to_responses,
    chat_stream_to_responses_stream,
    responses_request_to_chat,
)

# (channel_protocol, client_protocol) pairs that support conversion
_SUPPORTED_CONVERSIONS: set[tuple[str, str]] = {
    (ProtocolKind.OPENAI_CHAT.value, ProtocolKind.ANTHROPIC.value),
    (ProtocolKind.OPENAI_CHAT.value, ProtocolKind.OPENAI_RESPONSES.value),
}


def can_reach_protocol(channel_protocol: ProtocolKind, group_protocol: ProtocolKind) -> bool:
    """Whether a channel's protocol can serve a group's client protocol (passthrough or conversion)."""
    if channel_protocol == group_protocol:
        return True
    return (channel_protocol.value, group_protocol.value) in _SUPPORTED_CONVERSIONS


def needs_conversion(client_protocol: ProtocolKind, channel_protocol: ProtocolKind) -> bool:
    return (channel_protocol.value, client_protocol.value) in _SUPPORTED_CONVERSIONS


def convert_request(
    client_protocol: ProtocolKind,
    channel_protocol: ProtocolKind,
    body: dict[str, Any],
    target_model: str | None = None,
) -> dict[str, Any]:
    if client_protocol == ProtocolKind.ANTHROPIC and channel_protocol == ProtocolKind.OPENAI_CHAT:
        result = anthropic_request_to_chat(body)
    elif client_protocol == ProtocolKind.OPENAI_RESPONSES and channel_protocol == ProtocolKind.OPENAI_CHAT:
        result = responses_request_to_chat(body)
    else:
        raise ValueError(f"Unsupported conversion: {client_protocol.value} -> {channel_protocol.value}")
    if target_model:
        result["model"] = target_model
    return result


def convert_response(
    client_protocol: ProtocolKind,
    channel_protocol: ProtocolKind,
    response_body: bytes,
    original_model: str = "",
) -> bytes:
    chat_data = json.loads(response_body)
    if client_protocol == ProtocolKind.ANTHROPIC and channel_protocol == ProtocolKind.OPENAI_CHAT:
        converted = chat_response_to_anthropic(chat_data, original_model)
    elif client_protocol == ProtocolKind.OPENAI_RESPONSES and channel_protocol == ProtocolKind.OPENAI_CHAT:
        converted = chat_response_to_responses(chat_data, original_model)
    else:
        raise ValueError(f"Unsupported conversion: {client_protocol.value} -> {channel_protocol.value}")
    return json.dumps(converted, ensure_ascii=False).encode("utf-8")


async def convert_stream_iterator(
    client_protocol: ProtocolKind,
    channel_protocol: ProtocolKind,
    raw_iterator: AsyncIterator[bytes],
    original_model: str = "",
) -> AsyncIterator[bytes]:
    if client_protocol == ProtocolKind.ANTHROPIC and channel_protocol == ProtocolKind.OPENAI_CHAT:
        async for chunk in chat_stream_to_anthropic_stream(raw_iterator, original_model):
            yield chunk
    elif client_protocol == ProtocolKind.OPENAI_RESPONSES and channel_protocol == ProtocolKind.OPENAI_CHAT:
        async for chunk in chat_stream_to_responses_stream(raw_iterator, original_model):
            yield chunk
    else:
        raise ValueError(f"Unsupported conversion: {client_protocol.value} -> {channel_protocol.value}")
