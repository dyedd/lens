"""Restore authorized placeholders without buffering complete responses."""

import codecs
import json
import re
from collections.abc import AsyncIterator
from copy import deepcopy
from typing import Any

from app.core.privacy_rules import MAX_PRIVACY_TEXT_LENGTH, PrivacyError
from app.models.protocols import ProtocolKind

from ..privacy_content import ANTHROPIC_TOOL_TYPES
from ..privacy_context import PrivacyContext
from .capture import StreamCapture
from .privacy_content import stream_text_fields

MAX_PRIVACY_STREAM_FIELDS = 256


class PrivacyStreamRestorer:
    def __init__(self, context: PrivacyContext, protocol: ProtocolKind) -> None:
        self.context = context
        self.protocol = protocol
        self.pending: dict[tuple[Any, ...], str] = {}
        self.blocks: dict[tuple[Any, ...], dict[str, Any]] = {}
        self.response_templates: dict[tuple[Any, ...], dict[str, Any]] = {}
        self.flushed: list[dict[str, Any]] = []
        self.pattern = (
            re.compile("|".join(re.escape(token) for token in context.mapping))
            if context.mapping
            else None
        )

    def fragment(
        self, text: str, identity: tuple[Any, ...], *, json_string: bool = False
    ) -> str:
        text = self.pending.pop(identity, "") + text
        retained = 0
        start = text.rfind("[[")
        if start >= 0 and any(
            token.startswith(text[start:]) and token != text[start:]
            for token in self.context.mapping
        ):
            retained = len(text) - start
        elif text.endswith("[") and self.context.mapping:
            retained = 1
        if retained:
            self.pending[identity] = text[-retained:]
            text = text[:-retained]
        if self.pattern is None:
            return text
        self.context.validate_restoration(text)
        return self.pattern.sub(
            lambda match: (
                json.dumps(self.context.mapping[match.group()], ensure_ascii=False)[
                    1:-1
                ]
                if json_string
                else self.context.mapping[match.group()]
            ),
            text,
        )

    def complete(self, prefix: tuple[Any, ...] = ()) -> None:
        for identity in list(self.pending):
            if identity[: len(prefix)] != prefix:
                continue
            text = self.pending.pop(identity)
            if len(text) >= len("[[LENS_"):
                raise PrivacyError("Incomplete privacy placeholder in upstream stream")
            if identity[0] == "choice":
                if identity[2] == "tool":
                    delta = {
                        "tool_calls": [
                            {"index": identity[3], "function": {"arguments": text}}
                        ]
                    }
                elif identity[2] == "function":
                    delta = {"function_call": {"arguments": text}}
                else:
                    delta = {identity[2]: text}
                event = {"choices": [{"index": identity[1], "delta": delta}]}
            elif identity[0] == "block":
                name = identity[2]
                delta_type = {
                    "text": "text_delta",
                    "thinking": "thinking_delta",
                    "partial_json": "input_json_delta",
                }[name]
                event = {
                    "type": "content_block_delta",
                    "index": identity[1],
                    "delta": {"type": delta_type, name: text},
                }
            elif identity[0] == "item":
                event = {**self.response_templates[identity], "delta": text}
            else:
                part = {"text": text}
                if identity[3]:
                    part["thought"] = True
                event = {
                    "candidates": [
                        {
                            "index": identity[1],
                            "content": {
                                "parts": [{} for _ in range(identity[2])] + [part]
                            },
                        }
                    ]
                }
            self.flushed.append(event)

    def payload(self, payload: dict[str, Any]) -> dict[str, Any]:
        result = deepcopy(payload)
        event_type = result.get("type", "")
        if self.protocol == ProtocolKind.ANTHROPIC:
            identity = ("block", result.get("index", 0))
            if event_type == "content_block_start":
                block = result.get("content_block") or {}
                if block.get("type") == "thinking":
                    self.blocks[identity] = deepcopy(block)
                elif block.get("type") in ANTHROPIC_TOOL_TYPES:
                    result["content_block"] = self.context.restore(block, self.protocol)
            elif event_type == "content_block_delta" and identity in self.blocks:
                block = self.blocks[identity]
                delta = result.get("delta") or {}
                for name in ("thinking", "signature"):
                    if isinstance(delta.get(name), str):
                        block[name] = block.get(name, "") + delta[name]
                        if len(block[name]) > MAX_PRIVACY_TEXT_LENGTH:
                            raise PrivacyError("Privacy signed content limit exceeded")
        elif self.protocol == ProtocolKind.GEMINI:
            for candidate_index, candidate in enumerate(result.get("candidates") or []):
                for part_index, part in enumerate(
                    (candidate.get("content") or {}).get("parts") or []
                ):
                    identity = (
                        "candidate",
                        candidate.get("index", candidate_index),
                        part_index,
                    )
                    if isinstance(part.get("text"), str):
                        block = self.blocks.setdefault(identity, {})
                        if bool(block.get("thought")) != bool(part.get("thought")):
                            block = self.blocks[identity] = {}
                        block["text"] = block.get("text", "") + part["text"]
                        if len(block["text"]) > MAX_PRIVACY_TEXT_LENGTH:
                            raise PrivacyError("Privacy signed content limit exceeded")
                        if "thought" in part:
                            block["thought"] = part["thought"]
                    if "functionCall" in part:
                        self.blocks[identity] = {
                            "functionCall": deepcopy(part["functionCall"])
                        }
                        part["functionCall"] = self.context.restore(
                            part["functionCall"], self.protocol
                        )
                    if part.get("thoughtSignature"):
                        block = self.blocks.pop(identity, {})
                        block["thoughtSignature"] = part["thoughtSignature"]
                        self.context.restore(block, self.protocol)

        for field in stream_text_fields(result, self.protocol):
            if self.protocol == ProtocolKind.OPENAI_RESPONSES:
                self.response_templates[field.identity] = {
                    name: result[name]
                    for name in (
                        "type",
                        "item_id",
                        "output_index",
                        "content_index",
                        "summary_index",
                    )
                    if name in result
                }
            field.owner[field.name] = self.fragment(
                field.owner[field.name], field.identity, json_string=field.json_string
            )

        if (
            max(len(self.pending), len(self.blocks), len(self.response_templates))
            > MAX_PRIVACY_STREAM_FIELDS
            or sum(
                sum(
                    len(block.get(name, ""))
                    for name in ("text", "thinking", "signature")
                )
                + (
                    len(json.dumps(block["functionCall"], ensure_ascii=True))
                    if "functionCall" in block
                    else 0
                )
                for block in self.blocks.values()
            )
            > MAX_PRIVACY_TEXT_LENGTH
        ):
            raise PrivacyError("Privacy stream state limit exceeded")

        if self.protocol == ProtocolKind.OPENAI_CHAT:
            for choice in result.get("choices") or []:
                if choice.get("finish_reason") is not None:
                    self.complete(("choice", choice.get("index", 0)))
        elif self.protocol == ProtocolKind.ANTHROPIC:
            identity = ("block", result.get("index", 0))
            if event_type == "content_block_stop":
                self.complete(identity)
                block = self.blocks.pop(identity, None)
                if block is not None:
                    self.context.restore(block, self.protocol)
            elif event_type in {"message_stop", "error"}:
                self.complete()
                self.blocks.clear()
        elif self.protocol == ProtocolKind.OPENAI_RESPONSES:
            if event_type.endswith(".done"):
                self.complete(
                    ("item", result.get("item_id", result.get("output_index", 0)))
                )
                result = self.context.restore(result, self.protocol)
                self.response_templates = {
                    identity: template
                    for identity, template in self.response_templates.items()
                    if identity[1]
                    != result.get("item_id", result.get("output_index", 0))
                }
            if isinstance(result.get("response"), dict):
                if event_type in {
                    "response.completed",
                    "response.failed",
                    "response.incomplete",
                }:
                    self.complete()
                result["response"] = self.context.restore(
                    result["response"], self.protocol
                )
        elif self.protocol == ProtocolKind.GEMINI:
            for candidate_index, candidate in enumerate(result.get("candidates") or []):
                if candidate.get("finishReason"):
                    self.complete(
                        ("candidate", candidate.get("index", candidate_index))
                    )
                    self.blocks = {
                        identity: block
                        for identity, block in self.blocks.items()
                        if identity[1] != candidate.get("index", candidate_index)
                    }
        return result


async def restore_privacy_stream(
    stream: AsyncIterator[bytes],
    context: PrivacyContext,
    protocol: ProtocolKind,
    capture: StreamCapture,
    *,
    ndjson: bool,
) -> AsyncIterator[bytes]:
    restorer = PrivacyStreamRestorer(context, protocol)
    decoder = codecs.getincrementaldecoder("utf-8")("strict")
    buffer = ""

    def encode(payload: dict[str, Any], prefix: list[str]) -> bytes:
        text = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
        return (
            (text + "\n") if ndjson else "\n".join([*prefix, "data: " + text]) + "\n\n"
        ).encode()

    def drain() -> bytes:
        frames = b"".join(
            encode(payload, ["event: " + payload["type"]] if "type" in payload else [])
            for payload in restorer.flushed
        )
        restorer.flushed.clear()
        return frames

    def frame(raw: str) -> bytes:
        if len(raw) > MAX_PRIVACY_TEXT_LENGTH:
            raise PrivacyError("Privacy stream event limit exceeded")
        if ndjson:
            data = raw.strip()
            prefix: list[str] = []
        else:
            lines = raw.splitlines()
            data = "\n".join(
                line[5:].lstrip(" ") for line in lines if line.startswith("data:")
            )
            prefix = [line for line in lines if not line.startswith("data:")]
        ending = "\n" if ndjson else "\n\n"
        if not data:
            return (raw + ending).encode()
        if data == "[DONE]":
            restorer.complete()
            return drain() + (raw + ending).encode()
        try:
            payload = json.loads(data)
        except ValueError as exc:
            raise PrivacyError("Invalid JSON in privacy response stream") from exc
        if not isinstance(payload, dict):
            raise PrivacyError("Invalid privacy response stream event")
        try:
            restored = restorer.payload(payload)
        except Exception as exc:
            raise PrivacyError("Privacy response event could not be restored") from exc
        return drain() + encode(restored, prefix)

    try:
        async for chunk in stream:
            buffer += decoder.decode(chunk)
            while True:
                delimiter = re.search(r"\r?\n" if ndjson else r"\r?\n\r?\n", buffer)
                if delimiter is None:
                    break
                raw, buffer = buffer[: delimiter.start()], buffer[delimiter.end() :]
                yield frame(raw)
            if len(buffer) > MAX_PRIVACY_TEXT_LENGTH:
                raise PrivacyError("Privacy stream event limit exceeded")
        buffer += decoder.decode(b"", final=True)
        if buffer.strip():
            yield frame(buffer)
        restorer.complete()
        if restorer.flushed:
            yield drain()
    except (PrivacyError, UnicodeError) as exc:
        capture.skip_route_failure = True
        raise PrivacyError("Privacy response stream could not be restored") from exc
    finally:
        restorer.pending.clear()
        restorer.blocks.clear()
        restorer.response_templates.clear()
