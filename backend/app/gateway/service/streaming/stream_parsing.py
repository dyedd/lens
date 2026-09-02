from __future__ import annotations

import json
from typing import Any

from ..runtime_types import _append_error_sample


def _parse_sse_payloads(
    raw_content: str, *, errors: list[str] | None = None
) -> list[dict[str, Any]]:
    lf_content = _to_lf_line_endings(raw_content)
    payloads: list[dict[str, Any]] = []
    for block in lf_content.split("\n\n"):
        data_lines = [
            line[5:].strip() for line in block.splitlines() if line.startswith("data:")
        ]
        if not data_lines:
            continue
        joined = "\n".join(line for line in data_lines if line and line != "[DONE]")
        if not joined:
            continue
        try:
            payload = json.loads(joined)
        except json.JSONDecodeError as exc:
            _append_error_sample(errors, f"invalid SSE JSON: {exc.msg}")
            continue
        if isinstance(payload, dict):
            payloads.append(payload)
    return payloads


def _parse_ndjson_payloads(
    raw_content: str, *, errors: list[str] | None = None
) -> list[dict[str, Any]]:
    payloads: list[dict[str, Any]] = []
    for line in _to_lf_line_endings(raw_content).splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError as exc:
            _append_error_sample(errors, f"invalid NDJSON: {exc.msg}")
            continue
        if isinstance(payload, dict):
            payloads.append(payload)
    return payloads


def _to_lf_line_endings(raw_content: str) -> str:
    return raw_content.replace("\r\n", "\n").replace("\r", "\n")
