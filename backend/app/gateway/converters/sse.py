import json
from collections.abc import AsyncIterator
from typing import Any

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
    buffer = b""
    data: list[str] = []
    try:
        async for chunk in raw_iterator:
            buffer += chunk
            while b"\n" in buffer:
                raw_line, buffer = buffer.split(b"\n", 1)
                line = raw_line.decode("utf-8", errors="replace").rstrip("\r")
                if line.startswith("data:"):
                    data.append(line[5:].removeprefix(" "))
                elif not line and data:
                    value = "\n".join(data)
                    data.clear()
                    if value.strip() == "[DONE]":
                        return
                    yield _parse_sse_data(value)
        if buffer.startswith(b"data:"):
            data.append(buffer[5:].decode("utf-8", errors="replace").strip())
        if data:
            value = "\n".join(data)
            if value.strip() == "[DONE]":
                return
            yield _parse_sse_data(value)
        if require_done:
            raise ValueError("Chat stream ended before [DONE]")
    finally:
        aclose = getattr(raw_iterator, "aclose", None)
        if aclose is not None:
            await aclose()


def _parse_sse_data(value: str) -> dict[str, Any]:
    try:
        payload = json.loads(value)
    except json.JSONDecodeError as exc:
        raise ValueError("Invalid stream JSON") from exc
    if not isinstance(payload, dict):
        raise ValueError("Invalid stream JSON object")
    return payload


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
