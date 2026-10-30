"""把 SSE 字节流切成完整事件，供 `response_event` 钩子逐个改写。"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

# ponytail: 超过上限仍未结束的事件转为整流透传，之后的事件不再改写；需要时改成逐事件恢复。
_PENDING_LIMIT_BYTES = 8 * 1024 * 1024


@dataclass(frozen=True, slots=True)
class SseJsonEvent:
    """只有一行 `data:` 且其值为 JSON 对象的完整事件。"""

    name: str
    data: dict[str, Any]
    # 原始行（含行尾），最后一行是结束事件的空行。
    lines: tuple[bytes, ...]
    data_index: int

    @property
    def raw(self) -> bytes:
        return b"".join(self.lines)

    def serialize(self, data: dict[str, Any]) -> bytes:
        """替换 data 行，其余行原样保留。"""
        line = self.lines[self.data_index]
        ending = line[len(line.rstrip(b"\r\n")) :]
        text = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
        # 孤立代理项只会出现在 JSON 字符串里，backslashreplace 正好还原成 \udXXX 转义。
        payload = b"data: " + text.encode("utf-8", "backslashreplace") + ending
        lines = list(self.lines)
        lines[self.data_index] = payload
        return b"".join(lines)


class SseEventSplitter:
    """增量切分 SSE：块边界可以落在行中、多字节字符中或 CRLF 之间。

    只按 LF 断行，所以 CRLF 与 LF 都行；只有 CR 的流会一直等到上限后透传。
    行尾是单字节，完整的行不会截断 UTF-8 字符，因此按行解码即可。
    """

    def __init__(self) -> None:
        self._partial = bytearray()
        self._lines: list[bytes] = []
        self._pending_bytes = 0
        self._is_passthrough = False

    def feed(self, chunk: bytes) -> list[bytes | SseJsonEvent]:
        """返回本块里已完整的片段；注释与事件之间的空行立即放行。"""
        if self._is_passthrough:
            return [chunk] if chunk else []
        self._partial += chunk
        pieces: list[bytes | SseJsonEvent] = []
        start = 0
        while (end := self._partial.find(b"\n", start)) >= 0:
            self._accept_line(bytes(self._partial[start : end + 1]), pieces)
            start = end + 1
        del self._partial[:start]
        if self._pending_bytes + len(self._partial) > _PENDING_LIMIT_BYTES:
            pieces.append(b"".join(self._lines) + bytes(self._partial))
            self._lines.clear()
            self._partial.clear()
            self._pending_bytes = 0
            self._is_passthrough = True
        return pieces

    def flush(self) -> bytes:
        """流结束时剩下的未完成内容，原样交给客户端自己处理。"""
        rest = b"".join(self._lines) + bytes(self._partial)
        self._lines.clear()
        self._partial.clear()
        self._pending_bytes = 0
        return rest

    def _accept_line(self, line: bytes, pieces: list[bytes | SseJsonEvent]) -> None:
        if not line.rstrip(b"\r\n"):
            if self._lines:
                self._lines.append(line)
                pieces.append(_parse_event(tuple(self._lines)))
                self._lines.clear()
                self._pending_bytes = 0
            else:
                pieces.append(line)
            return
        if not self._lines and line.startswith(b":"):
            pieces.append(line)
            return
        self._lines.append(line)
        self._pending_bytes += len(line)


def _parse_event(lines: tuple[bytes, ...]) -> bytes | SseJsonEvent:
    name = ""
    data_index = -1
    for index, line in enumerate(lines):
        field, value = _split_field(line)
        if field == b"event":
            name = value.decode("utf-8", "replace")
        elif field == b"data":
            if data_index >= 0:
                return b"".join(lines)
            data_index = index
    if data_index < 0:
        return b"".join(lines)
    _, value = _split_field(lines[data_index])
    if not value.startswith(b"{"):
        return b"".join(lines)
    try:
        data = json.loads(value)
    except (ValueError, RecursionError):
        return b"".join(lines)
    if not isinstance(data, dict):
        return b"".join(lines)
    return SseJsonEvent(name=name, data=data, lines=lines, data_index=data_index)


def _split_field(line: bytes) -> tuple[bytes, bytes]:
    field, _, value = line.rstrip(b"\r\n").partition(b":")
    return field, value.removeprefix(b" ")
