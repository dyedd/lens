"""Protocol conversion dispatch.

Each (client protocol, upstream protocol) pair registers one adapter; the
public ``convert_*`` entrypoints look the pair up instead of repeating the
matrix as if/elif chains.
"""

import json
from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass
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

RequestConverter = Callable[[dict[str, Any], bool], dict[str, Any]]
ResponseConverter = Callable[[dict[str, Any], str], dict[str, Any]]
StreamConverter = Callable[[AsyncIterator[bytes], str, bool], AsyncIterator[bytes]]


@dataclass(frozen=True)
class ProtocolPairConverter:
    """Adapters normalizing one (client, upstream) pair's converter signatures."""

    request: RequestConverter
    response: ResponseConverter
    stream: StreamConverter


def _unsupported(
    client_protocol: ProtocolKind, channel_protocol: ProtocolKind
) -> ValueError:
    return ValueError(
        f"Unsupported conversion: {client_protocol.value} -> {channel_protocol.value}"
    )


_CONVERTERS: dict[tuple[ProtocolKind, ProtocolKind], ProtocolPairConverter] = {
    (ProtocolKind.ANTHROPIC, ProtocolKind.OPENAI_CHAT): ProtocolPairConverter(
        request=lambda body, preserve_reasoning: anthropic_request_to_chat(
            body, preserve_thinking=preserve_reasoning
        ),
        response=chat_response_to_anthropic,
        stream=lambda raw_iterator, original_model, include_usage: (
            chat_stream_to_anthropic_stream(raw_iterator, original_model)
        ),
    ),
    (ProtocolKind.OPENAI_RESPONSES, ProtocolKind.OPENAI_CHAT): ProtocolPairConverter(
        request=lambda body, preserve_reasoning: responses_request_to_chat(body),
        response=chat_response_to_responses,
        stream=lambda raw_iterator, original_model, include_usage: (
            chat_stream_to_responses_stream(raw_iterator, original_model)
        ),
    ),
    (ProtocolKind.OPENAI_CHAT, ProtocolKind.OPENAI_RESPONSES): ProtocolPairConverter(
        request=lambda body, preserve_reasoning: chat_request_to_responses(body),
        response=responses_response_to_chat,
        stream=lambda raw_iterator, original_model, include_usage: (
            responses_stream_to_chat_stream(
                raw_iterator, original_model, include_usage=include_usage
            )
        ),
    ),
    (ProtocolKind.ANTHROPIC, ProtocolKind.OPENAI_RESPONSES): ProtocolPairConverter(
        request=lambda body, preserve_reasoning: anthropic_request_to_responses(body),
        response=responses_response_to_anthropic,
        stream=lambda raw_iterator, original_model, include_usage: (
            responses_stream_to_anthropic_stream(raw_iterator, original_model)
        ),
    ),
}


def _lookup(
    client_protocol: ProtocolKind, channel_protocol: ProtocolKind
) -> ProtocolPairConverter:
    converter = _CONVERTERS.get((client_protocol, channel_protocol))
    if converter is None:
        raise _unsupported(client_protocol, channel_protocol)
    return converter


def convert_request(
    client_protocol: ProtocolKind,
    channel_protocol: ProtocolKind,
    body: dict[str, Any],
    target_model: str | None = None,
    preserve_reasoning: bool = False,
) -> dict[str, Any]:
    """Convert a client request into the selected upstream protocol."""
    result = _lookup(client_protocol, channel_protocol).request(
        body, preserve_reasoning
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
    converted = _lookup(client_protocol, channel_protocol).response(
        chat_data, original_model
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
    stream = _lookup(client_protocol, channel_protocol).stream(
        raw_iterator, original_model, include_usage
    )
    async for chunk in stream:
        yield chunk
