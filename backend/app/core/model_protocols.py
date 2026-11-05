"""根据模型家族、用途和显式配置生成协议预选值。"""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping
from typing import Any
from urllib.parse import urlsplit

from ..models.protocols import ProtocolKind

ENDPOINT_KIND_PROTOCOLS: dict[str, ProtocolKind] = {
    "openai_chat": ProtocolKind.OPENAI_CHAT,
    "openai_responses": ProtocolKind.OPENAI_RESPONSES,
    "openai_embedding": ProtocolKind.OPENAI_EMBEDDING,
    "openai_image": ProtocolKind.OPENAI_IMAGE,
    "anthropic": ProtocolKind.ANTHROPIC,
    "gemini": ProtocolKind.GEMINI,
    "rerank": ProtocolKind.RERANK,
}

_CHAT_PROTOCOL_ORDER = (
    ProtocolKind.OPENAI_RESPONSES,
    ProtocolKind.OPENAI_CHAT,
    ProtocolKind.ANTHROPIC,
)
_NON_CHAT_PROTOCOL_ORDER = (
    ProtocolKind.OPENAI_IMAGE,
    ProtocolKind.OPENAI_EMBEDDING,
    ProtocolKind.RERANK,
)

_RERANK_NAME_RE = re.compile(r"rerank")
_EMBEDDING_NAME_RE = re.compile(r"embed|^(?:bge|gte|m3e|voyage)-")
_IMAGE_NAME_RE = re.compile(
    r"gpt-image|dall-e|imagen|flux|seedream|cogview|kolors|hidream"
    r"|stable-diffusion|sdxl|wanx|qwen-image|grok-imagine-image"
)
_OPENAI_REASONING_NAME_RE = re.compile(r"^o[1-9](?:-|$)")

_DECLARED_ENDPOINT_PROTOCOLS: dict[str, ProtocolKind] = {
    "openai": ProtocolKind.OPENAI_CHAT,
    "chat": ProtocolKind.OPENAI_CHAT,
    "/v1/chat/completions": ProtocolKind.OPENAI_CHAT,
    "openai-response": ProtocolKind.OPENAI_RESPONSES,
    "openai-response-compact": ProtocolKind.OPENAI_RESPONSES,
    "responses": ProtocolKind.OPENAI_RESPONSES,
    "/v1/responses": ProtocolKind.OPENAI_RESPONSES,
    "/v1/responses/compact": ProtocolKind.OPENAI_RESPONSES,
    "anthropic": ProtocolKind.ANTHROPIC,
    "/v1/messages": ProtocolKind.ANTHROPIC,
    "embeddings": ProtocolKind.OPENAI_EMBEDDING,
    "/v1/embeddings": ProtocolKind.OPENAI_EMBEDDING,
    "jina-rerank": ProtocolKind.RERANK,
    "rerank": ProtocolKind.RERANK,
    "/v1/rerank": ProtocolKind.RERANK,
    "image-generation": ProtocolKind.OPENAI_IMAGE,
    "/v1/images/generations": ProtocolKind.OPENAI_IMAGE,
    "/v1/images/edits": ProtocolKind.OPENAI_IMAGE,
    "gemini": ProtocolKind.GEMINI,
    "generatecontent": ProtocolKind.GEMINI,
    "streamgeneratecontent": ProtocolKind.GEMINI,
}


def parse_declared_protocols(entry: Mapping[str, Any]) -> list[ProtocolKind]:
    protocols: list[ProtocolKind] = []
    for field in ("supported_endpoint_types", "supported_endpoints"):
        declared = entry.get(field)
        if not isinstance(declared, list):
            continue
        for value in declared:
            try:
                endpoint = urlsplit(str(value).strip().lower()).path.rstrip("/")
            except ValueError:
                continue
            protocol = _DECLARED_ENDPOINT_PROTOCOLS.get(endpoint)
            if protocol is None and endpoint.startswith("/"):
                protocol = _DECLARED_ENDPOINT_PROTOCOLS.get(f"/v1{endpoint}")
            if protocol is None and endpoint.rsplit(":", 1)[-1] in {
                "generatecontent",
                "streamgeneratecontent",
            }:
                protocol = ProtocolKind.GEMINI
            if protocol is not None and protocol not in protocols:
                protocols.append(protocol)
    return protocols


def resolve_known_protocol(
    model_name: str,
    *,
    pinned: ProtocolKind | None = None,
    declared: Iterable[ProtocolKind] = (),
) -> ProtocolKind | None:
    if pinned is not None:
        return pinned
    name = model_name.strip().lower().rsplit("/", 1)[-1]
    for pattern, protocol in (
        (_RERANK_NAME_RE, ProtocolKind.RERANK),
        (_EMBEDDING_NAME_RE, ProtocolKind.OPENAI_EMBEDDING),
        (_IMAGE_NAME_RE, ProtocolKind.OPENAI_IMAGE),
    ):
        if pattern.search(name):
            return protocol
    if name.startswith(("gemini", "gemma", "nano-banana")):
        return ProtocolKind.GEMINI
    if name.startswith(
        (
            "claude",
            "deepseek",
            "glm-",
            "qwen",
            "qwq",
            "qvq",
            "kimi",
            "moonshot",
            "minimax",
            "step-",
        )
    ):
        return ProtocolKind.ANTHROPIC
    if name.startswith(
        ("gpt-", "chatgpt-", "grok-")
    ) or _OPENAI_REASONING_NAME_RE.match(name):
        return ProtocolKind.OPENAI_RESPONSES
    declared_set = set(declared)
    return next(
        (
            protocol
            for protocol in (
                *_NON_CHAT_PROTOCOL_ORDER,
                *_CHAT_PROTOCOL_ORDER,
                ProtocolKind.GEMINI,
            )
            if protocol in declared_set
        ),
        None,
    )


def resolve_onboard_protocol(
    model_name: str,
    *,
    pinned: ProtocolKind | None = None,
    declared: Iterable[ProtocolKind] = (),
    configured: Iterable[ProtocolKind] = (),
) -> ProtocolKind:
    known = resolve_known_protocol(model_name, pinned=pinned, declared=declared)
    if known is not None:
        return known
    configured_set = set(configured)
    return next(
        (
            protocol
            for protocol in (*_CHAT_PROTOCOL_ORDER, ProtocolKind.GEMINI)
            if protocol in configured_set
        ),
        ProtocolKind.OPENAI_CHAT,
    )
