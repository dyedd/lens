from dataclasses import dataclass
from typing import Any


@dataclass
class ChatStreamDelta:
    content: str | None = None
    reasoning_content: str | None = None
    reasoning: str | None = None
    function_call: dict[str, Any] | None = None
    tool_calls: list[dict[str, Any]] | None = None


@dataclass
class ChatStreamChoice:
    index: int
    delta: ChatStreamDelta
    finish_reason: str | None = None


@dataclass
class ResponsesStreamItem:
    type: str
    delta: str | None = None
    text: str | None = None
    partial_json: str | None = None
    item: dict[str, Any] | None = None


@dataclass
class AnthropicStreamBlock:
    type: str
    delta: dict[str, Any] | None = None
    content_block: dict[str, Any] | None = None


@dataclass
class GeminiStreamCandidate:
    content: dict[str, Any]
    finish_reason: str | None = None


def parse_chat_stream_payload(payload: dict[str, Any]) -> list[ChatStreamChoice]:
    """Parse valid chat choices from a streaming payload."""
    choices_raw = payload.get("choices")
    if not isinstance(choices_raw, list):
        return []

    result: list[ChatStreamChoice] = []
    for choice_raw in choices_raw:
        if not isinstance(choice_raw, dict):
            continue

        delta_raw = choice_raw.get("delta")
        if not isinstance(delta_raw, dict):
            continue

        delta = ChatStreamDelta(
            content=_extract_text(delta_raw.get("content")),
            reasoning_content=_extract_text(delta_raw.get("reasoning_content")),
            reasoning=_extract_text(delta_raw.get("reasoning")),
            function_call=(
                delta_raw.get("function_call")
                if isinstance(delta_raw.get("function_call"), dict)
                else None
            ),
            tool_calls=(
                delta_raw.get("tool_calls")
                if isinstance(delta_raw.get("tool_calls"), list)
                else None
            ),
        )

        result.append(
            ChatStreamChoice(
                index=choice_raw.get("index", 0),
                delta=delta,
                finish_reason=choice_raw.get("finish_reason"),
            )
        )

    return result


def parse_anthropic_stream_payload(
    payload: dict[str, Any],
) -> AnthropicStreamBlock | None:
    """Parse an Anthropic stream block when the payload declares an event type."""
    payload_type = payload.get("type")
    if not isinstance(payload_type, str):
        return None

    return AnthropicStreamBlock(
        type=payload_type,
        delta=payload.get("delta") if isinstance(payload.get("delta"), dict) else None,
        content_block=(
            payload.get("content_block")
            if isinstance(payload.get("content_block"), dict)
            else None
        ),
    )


def _extract_text(value: Any) -> str | None:
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        parts = []
        for item in value:
            if isinstance(item, dict) and item.get("type") == "text":
                text = item.get("text")
                if isinstance(text, str):
                    parts.append(text)
        return "\n".join(parts) if parts else None
    return None
