"""Protocol stream fields shared by restoration and log sanitization."""

import json
from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any

from app.models.protocols import ProtocolKind

from ..privacy_context import PrivacyContext
from .types import parse_ndjson_payloads, parse_sse_payloads


@dataclass(slots=True, kw_only=True)
class PrivacyStreamField:
    owner: dict[str, Any]
    name: str
    identity: tuple[Any, ...]
    json_string: bool = False


def stream_text_fields(
    payload: dict[str, Any], protocol: ProtocolKind
) -> Iterator[PrivacyStreamField]:
    if protocol == ProtocolKind.OPENAI_CHAT:
        for choice in payload.get("choices") or []:
            identity = ("choice", choice.get("index", 0))
            delta = choice.get("delta") or {}
            for name in ("content", "reasoning_content", "reasoning", "refusal"):
                if isinstance(delta.get(name), str):
                    yield PrivacyStreamField(
                        owner=delta, name=name, identity=(*identity, name)
                    )
            for tool in delta.get("tool_calls") or []:
                function = tool.get("function") or {}
                if isinstance(function.get("arguments"), str):
                    yield PrivacyStreamField(
                        owner=function,
                        name="arguments",
                        identity=(
                            *identity,
                            "tool",
                            tool.get("index", tool.get("id", 0)),
                        ),
                        json_string=True,
                    )
            function = delta.get("function_call") or {}
            if isinstance(function.get("arguments"), str):
                yield PrivacyStreamField(
                    owner=function,
                    name="arguments",
                    identity=(*identity, "function"),
                    json_string=True,
                )
    elif protocol == ProtocolKind.ANTHROPIC:
        if payload.get("type") == "content_block_start":
            owner = payload.get("content_block") or {}
        else:
            owner = payload.get("delta") or {}
        for name in ("text", "thinking", "partial_json"):
            if isinstance(owner.get(name), str):
                yield PrivacyStreamField(
                    owner=owner,
                    name=name,
                    identity=("block", payload.get("index", 0), name),
                    json_string=name == "partial_json",
                )
    elif protocol == ProtocolKind.OPENAI_RESPONSES:
        event_type = payload.get("type", "")
        if event_type.endswith(".delta") and isinstance(payload.get("delta"), str):
            yield PrivacyStreamField(
                owner=payload,
                name="delta",
                identity=(
                    "item",
                    payload.get("item_id", payload.get("output_index", 0)),
                    payload.get("content_index", payload.get("summary_index", 0)),
                    event_type,
                ),
                json_string="arguments" in event_type,
            )
    elif protocol == ProtocolKind.GEMINI:
        for candidate_index, candidate in enumerate(payload.get("candidates") or []):
            for part_index, part in enumerate(
                (candidate.get("content") or {}).get("parts") or []
            ):
                if isinstance(part.get("text"), str):
                    yield PrivacyStreamField(
                        owner=part,
                        name="text",
                        identity=(
                            "candidate",
                            candidate.get("index", candidate_index),
                            part_index,
                            bool(part.get("thought")),
                        ),
                    )


def clean_privacy_stream_log(
    raw: str,
    protocol: ProtocolKind,
    context: PrivacyContext,
    *,
    ndjson: bool | None = None,
) -> str:
    try:
        errors: list[str] = []
        if ndjson is None:
            try:
                saved = json.loads(raw)
            except ValueError:
                payloads = (
                    parse_sse_payloads(raw, errors=errors)
                    if "data:" in raw
                    else parse_ndjson_payloads(raw, errors=errors)
                )
            else:
                if isinstance(saved, dict):
                    if protocol == ProtocolKind.GEMINI:
                        for candidate in saved.get("candidates") or []:
                            groups: dict[bool, list[dict[str, Any]]] = {}
                            for part in (candidate.get("content") or {}).get(
                                "parts"
                            ) or []:
                                if isinstance(part.get("text"), str):
                                    groups.setdefault(
                                        bool(part.get("thought")), []
                                    ).append(part)
                            for parts in groups.values():
                                parts[0]["text"] = (
                                    context.clean_log(
                                        "".join(part["text"] for part in parts)
                                    )
                                    or ""
                                )
                                for part in parts[1:]:
                                    part["text"] = ""
                    return context.clean_log(json.dumps(saved, ensure_ascii=True)) or ""
                payloads = saved if isinstance(saved, list) else []
        else:
            payloads = (
                parse_ndjson_payloads(raw, errors=errors)
                if ndjson
                else parse_sse_payloads(raw, errors=errors)
            )
        if errors or not payloads:
            return "[privacy stream content unavailable]"
        fields: dict[tuple[Any, ...], list[PrivacyStreamField]] = {}
        for payload in payloads:
            for field in stream_text_fields(payload, protocol):
                fields.setdefault(field.identity, []).append(field)
        for parts in fields.values():
            joined = "".join(part.owner[part.name] for part in parts)
            cleaned = context.clean_log(joined)
            for index, part in enumerate(parts):
                part.owner[part.name] = (cleaned or "") if index == 0 else ""
        return context.clean_log(json.dumps(payloads, ensure_ascii=True)) or ""
    except (TypeError, ValueError, KeyError, AttributeError, RecursionError):
        return "[privacy stream content unavailable]"
