import json
from collections.abc import AsyncIterator
from typing import Any

from ...core.protocol_reachability import can_reach_protocol
from ...models.protocols import ProtocolKind
from ._chat_stream import repair_chat_tool_call_stream
from .anthropic_request_to_chat import anthropic_request_to_chat
from .anthropic_to_responses import anthropic_request_to_responses
from .chat_request_to_responses import chat_request_to_responses
from .chat_to_anthropic import (
    chat_response_to_anthropic,
    chat_stream_to_anthropic_stream,
)
from .chat_to_responses import (
    chat_response_to_responses,
    chat_stream_to_responses_stream,
)
from .responses_request_to_chat import responses_request_to_chat
from .responses_to_anthropic import (
    responses_response_to_anthropic,
    responses_stream_to_anthropic_stream,
)
from .responses_to_chat import (
    responses_response_to_chat,
    responses_stream_to_chat_stream,
)

__all__ = [
    "can_reach_protocol",
    "convert_request",
    "convert_response",
    "convert_stream_iterator",
    "repair_chat_tool_call_stream",
]


def convert_request(
    client_protocol: ProtocolKind,
    channel_protocol: ProtocolKind,
    body: dict[str, Any],
    target_model: str | None = None,
    preserve_reasoning: bool = False,
) -> dict[str, Any]:
    """Convert a client request into the selected upstream protocol."""
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
    elif (
        client_protocol == ProtocolKind.OPENAI_CHAT
        and channel_protocol == ProtocolKind.OPENAI_RESPONSES
    ):
        result = chat_request_to_responses(body)
    elif (
        client_protocol == ProtocolKind.ANTHROPIC
        and channel_protocol == ProtocolKind.OPENAI_RESPONSES
    ):
        result = anthropic_request_to_responses(body)
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
    """Convert an upstream response into the client protocol."""
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
    elif (
        client_protocol == ProtocolKind.OPENAI_CHAT
        and channel_protocol == ProtocolKind.OPENAI_RESPONSES
    ):
        converted = responses_response_to_chat(chat_data, original_model)
    elif (
        client_protocol == ProtocolKind.ANTHROPIC
        and channel_protocol == ProtocolKind.OPENAI_RESPONSES
    ):
        converted = responses_response_to_anthropic(chat_data, original_model)
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
    *,
    include_usage: bool = False,
) -> AsyncIterator[bytes]:
    """Convert an upstream byte stream into the client protocol stream."""
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
    elif (
        client_protocol == ProtocolKind.OPENAI_CHAT
        and channel_protocol == ProtocolKind.OPENAI_RESPONSES
    ):
        async for chunk in responses_stream_to_chat_stream(
            raw_iterator, original_model, include_usage=include_usage
        ):
            yield chunk
    elif (
        client_protocol == ProtocolKind.ANTHROPIC
        and channel_protocol == ProtocolKind.OPENAI_RESPONSES
    ):
        async for chunk in responses_stream_to_anthropic_stream(
            raw_iterator, original_model
        ):
            yield chunk
    else:
        raise ValueError(
            f"Unsupported conversion: {client_protocol.value} -> {channel_protocol.value}"
        )
