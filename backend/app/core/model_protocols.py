"""Which upstream protocol serves a channel model.

Admins no longer pick a protocol per model. The facts that decide it, in
order: an endpoint dedicated to one protocol, a name that only fits an
embedding, rerank or image API, and the endpoint types a NewAPI-style model
list declares. A chat model none of them settles is probed in
``chat_protocol_order``: OpenAI Responses first, then Chat, Anthropic and
Gemini, with Claude and Gemini models asked on their own API before the rest
so their requests pass through unconverted.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping
from typing import Any

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
    ProtocolKind.GEMINI,
)
_NON_CHAT_PROTOCOL_ORDER = (
    ProtocolKind.OPENAI_IMAGE,
    ProtocolKind.OPENAI_EMBEDDING,
    ProtocolKind.RERANK,
)

# NewAPI-style `supported_endpoint_types`, by name or by path. Their "gemini"
# is generateContent, which Lens does not call, so it is left out.
_DECLARED_ENDPOINT_PROTOCOLS: dict[str, ProtocolKind] = {
    "openai": ProtocolKind.OPENAI_CHAT,
    "chat": ProtocolKind.OPENAI_CHAT,
    "/v1/chat/completions": ProtocolKind.OPENAI_CHAT,
    "openai-response": ProtocolKind.OPENAI_RESPONSES,
    "openai-response-compact": ProtocolKind.OPENAI_RESPONSES,
    "responses": ProtocolKind.OPENAI_RESPONSES,
    "/v1/responses": ProtocolKind.OPENAI_RESPONSES,
    "anthropic": ProtocolKind.ANTHROPIC,
    "/v1/messages": ProtocolKind.ANTHROPIC,
    "embeddings": ProtocolKind.OPENAI_EMBEDDING,
    "/v1/embeddings": ProtocolKind.OPENAI_EMBEDDING,
    "jina-rerank": ProtocolKind.RERANK,
    "rerank": ProtocolKind.RERANK,
    "/v1/rerank": ProtocolKind.RERANK,
    "image-generation": ProtocolKind.OPENAI_IMAGE,
    "/v1/images/generations": ProtocolKind.OPENAI_IMAGE,
}

_RERANK_NAME_RE = re.compile(r"rerank")
_EMBEDDING_NAME_RE = re.compile(r"embed|^(?:bge|gte|m3e|voyage)-")
# Models served by an images API. Chat models that answer with pictures, such
# as gemini-2.5-flash-image, stay chat.
_IMAGE_NAME_RE = re.compile(
    r"gpt-image|dall-e|imagen|flux|seedream|cogview|kolors|hidream"
    r"|stable-diffusion|sdxl|wanx|qwen-image"
)


def _base_model_name(model_name: str) -> str:
    """Drop vendor prefixes such as `openai/` or `models/`."""
    return model_name.strip().lower().rsplit("/", 1)[-1]


def _protocol_for_model_name(model_name: str) -> ProtocolKind | None:
    name = _base_model_name(model_name)
    if _RERANK_NAME_RE.search(name):
        return ProtocolKind.RERANK
    if _EMBEDDING_NAME_RE.search(name):
        return ProtocolKind.OPENAI_EMBEDDING
    if _IMAGE_NAME_RE.search(name):
        return ProtocolKind.OPENAI_IMAGE
    return None


def chat_protocol_order(model_name: str) -> list[ProtocolKind]:
    """Chat protocols to try for a model, most preferred first."""
    name = _base_model_name(model_name)
    native = (
        ProtocolKind.ANTHROPIC
        if "claude" in name
        else ProtocolKind.GEMINI
        if "gemini" in name
        else None
    )
    if native is None:
        return list(_CHAT_PROTOCOL_ORDER)
    return [native, *(item for item in _CHAT_PROTOCOL_ORDER if item != native)]


def parse_declared_protocols(entry: Mapping[str, Any]) -> list[ProtocolKind]:
    """Read the protocols a model list entry says the upstream serves."""
    declared = entry.get("supported_endpoint_types")
    if not isinstance(declared, list):
        return []
    protocols: list[ProtocolKind] = []
    for value in declared:
        protocol = _DECLARED_ENDPOINT_PROTOCOLS.get(str(value).strip().lower())
        if protocol is not None and protocol not in protocols:
            protocols.append(protocol)
    return protocols


def resolve_known_protocol(
    model_name: str,
    *,
    pinned: ProtocolKind | None = None,
    declared: Iterable[ProtocolKind] = (),
) -> ProtocolKind | None:
    """Return the protocol the facts settle, or None when it must be probed."""
    if pinned is not None:
        return pinned
    named = _protocol_for_model_name(model_name)
    if named is not None:
        return named
    declared_set = set(declared)
    for protocol in _NON_CHAT_PROTOCOL_ORDER:
        if protocol in declared_set:
            return protocol
    return next(
        (
            protocol
            for protocol in chat_protocol_order(model_name)
            if protocol in declared_set
        ),
        None,
    )


def resolve_onboard_protocol(
    model_name: str,
    *,
    pinned: ProtocolKind | None,
    declared: Iterable[ProtocolKind],
    configured: Iterable[ProtocolKind],
) -> ProtocolKind:
    """Pick the protocol a model sync stores for a newly matched model.

    Syncs do not probe: a chat model the facts leave open takes the first
    configured chat protocol in preference order, else OpenAI Chat.
    """
    known = resolve_known_protocol(model_name, pinned=pinned, declared=declared)
    if known is not None:
        return known
    configured_set = set(configured)
    return next(
        (
            protocol
            for protocol in chat_protocol_order(model_name)
            if protocol in configured_set
        ),
        ProtocolKind.OPENAI_CHAT,
    )
