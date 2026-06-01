import json
from typing import Any, AsyncIterator

from ...core.protocol_reachability import can_reach_protocol, needs_conversion
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

__all__ = [
    "can_reach_protocol",
    "needs_conversion",
    "convert_request",
    "convert_response",
    "convert_stream_iterator",
]


def convert_request(
    client_protocol: ProtocolKind,
    channel_protocol: ProtocolKind,
    body: dict[str, Any],
    target_model: str | None = None,
    preserve_reasoning: bool = False,
) -> dict[str, Any]:
    if (
        client_protocol == ProtocolKind.ANTHROPIC
        and channel_protocol == ProtocolKind.OPENAI_CHAT
    ):
        result = anthropic_request_to_chat(body, preserve_thinking=preserve_reasoning)
    elif (
        client_protocol == ProtocolKind.OPENAI_RESPONSES
        and channel_protocol == ProtocolKind.OPENAI_CHAT
    ):
        result = responses_request_to_chat(body)
    else:
        raise ValueError(
            f"Unsupported conversion: {client_protocol.value} -> {channel_protocol.value}"
        )
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
    if (
        client_protocol == ProtocolKind.ANTHROPIC
        and channel_protocol == ProtocolKind.OPENAI_CHAT
    ):
        converted = chat_response_to_anthropic(chat_data, original_model)
    elif (
        client_protocol == ProtocolKind.OPENAI_RESPONSES
        and channel_protocol == ProtocolKind.OPENAI_CHAT
    ):
        converted = chat_response_to_responses(chat_data, original_model)
    else:
        raise ValueError(
            f"Unsupported conversion: {client_protocol.value} -> {channel_protocol.value}"
        )
    return json.dumps(converted, ensure_ascii=False).encode("utf-8")


async def convert_stream_iterator(
    client_protocol: ProtocolKind,
    channel_protocol: ProtocolKind,
    raw_iterator: AsyncIterator[bytes],
    original_model: str = "",
) -> AsyncIterator[bytes]:
    if (
        client_protocol == ProtocolKind.ANTHROPIC
        and channel_protocol == ProtocolKind.OPENAI_CHAT
    ):
        async for chunk in chat_stream_to_anthropic_stream(
            raw_iterator, original_model
        ):
            yield chunk
    elif (
        client_protocol == ProtocolKind.OPENAI_RESPONSES
        and channel_protocol == ProtocolKind.OPENAI_CHAT
    ):
        async for chunk in chat_stream_to_responses_stream(
            raw_iterator, original_model
        ):
            yield chunk
    else:
        raise ValueError(
            f"Unsupported conversion: {client_protocol.value} -> {channel_protocol.value}"
        )
