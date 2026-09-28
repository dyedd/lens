import json
from collections.abc import AsyncIterator
from typing import Any

FINISH_REASON_CHAT_TO_ANTHROPIC: dict[str | None, str] = {
    "stop": "end_turn",
    "length": "max_tokens",
    "tool_calls": "tool_use",
    "content_filter": "end_turn",
}

FINISH_REASON_CHAT_TO_RESPONSES: dict[str | None, str] = {
    "stop": "completed",
    "length": "incomplete",
    "tool_calls": "completed",
    "content_filter": "incomplete",
}


async def parse_sse_json_stream(
    raw_iterator: AsyncIterator[bytes],
    *,
    require_done: bool = False,
) -> AsyncIterator[dict[str, Any]]:
    """Parse JSON payloads from an OpenAI-compatible SSE byte stream."""
    buffer = b""
    try:
        async for chunk in raw_iterator:
            buffer += chunk
            while b"\n" in buffer:
                line, buffer = buffer.split(b"\n", 1)
                line_str = line.decode("utf-8", errors="replace").strip()
                if not line_str.startswith("data:"):
                    continue
                data_str = line_str[5:].strip()
                if data_str == "[DONE]":
                    return
                try:
                    payload = json.loads(data_str)
                except json.JSONDecodeError as exc:
                    raise ValueError("Invalid stream JSON") from exc
                if not isinstance(payload, dict):
                    raise ValueError("Invalid stream JSON object")
                yield payload
        if require_done:
            raise ValueError("Chat stream ended before [DONE]")
    finally:
        aclose = getattr(raw_iterator, "aclose", None)
        if aclose is not None:
            await aclose()


def format_sse_event(event: str | None, data: dict[str, Any] | str) -> bytes:
    """Serialize an event and payload as an SSE frame."""
    lines: list[str] = []
    if event:
        lines.append(f"event: {event}")
    if isinstance(data, dict):
        lines.append(f"data: {json.dumps(data, ensure_ascii=False)}")
    else:
        lines.append(f"data: {data}")
    lines.extend(("", ""))
    return "\n".join(lines).encode("utf-8")


def anthropic_block_start(index: int, content_block: dict[str, Any]) -> bytes:
    return format_sse_event(
        "content_block_start",
        {"type": "content_block_start", "index": index, "content_block": content_block},
    )


def anthropic_block_delta(index: int, delta: dict[str, Any]) -> bytes:
    return format_sse_event(
        "content_block_delta",
        {"type": "content_block_delta", "index": index, "delta": delta},
    )


def anthropic_block_stop(index: int) -> bytes:
    return format_sse_event(
        "content_block_stop", {"type": "content_block_stop", "index": index}
    )


def build_chat_tool_call(call_id: str, name: str, arguments: str) -> dict[str, Any]:
    return {
        "id": call_id,
        "type": "function",
        "function": {"name": name, "arguments": arguments},
    }
