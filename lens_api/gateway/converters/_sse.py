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
    "content_filter": "failed",
}


async def parse_chat_sse_stream(
    raw_iterator: AsyncIterator[bytes],
) -> AsyncIterator[dict[str, Any]]:
    """Parse JSON payloads from an OpenAI chat SSE byte stream."""
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
                    yield json.loads(data_str)
                except json.JSONDecodeError as exc:
                    raise ValueError("Invalid stream JSON") from exc
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
