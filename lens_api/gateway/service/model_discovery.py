from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from functools import lru_cache
from typing import Any

import httpx
from fastapi import HTTPException

from ...models import ChannelConfig, ProtocolKind
from ..upstream_request import (
    build_upstream_headers,
    resolve_channel_api_key,
    resolve_channel_model_list_url,
    resolve_upstream_proxy_url,
)
from .app_state import app_state
from .upstream_support import (
    _default_lens_user_agent,
    _format_http_response_error,
    _resolve_http_client,
)


@dataclass(slots=True)
class _ModelListItem:
    model_name: str
    protocols: list[ProtocolKind]


async def _fetch_upstream_models(channel: ChannelConfig) -> list[str]:
    runtime = await app_state.settings_repo.get_runtime_settings()
    proxy_url = resolve_upstream_proxy_url(channel, runtime["proxy_url"])
    client, should_close_client = _resolve_http_client(proxy_url)

    try:
        response = await client.request(
            **_model_list_request(channel, runtime["upstream_headers_config"])
        )
        response.raise_for_status()
        return _parse_model_list(response.json(), channel.match_regex)
    except httpx.HTTPStatusError as exc:
        detail = _format_http_response_error(exc.response)
        raise HTTPException(
            status_code=exc.response.status_code, detail=detail
        ) from exc
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"Transport error: {exc}") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    finally:
        if should_close_client:
            await client.aclose()


def _model_list_request(
    channel: ChannelConfig, upstream_headers_config: Mapping[str, Any] | None = None
) -> dict[str, Any]:
    api_key = resolve_channel_api_key(channel)
    headers = dict(channel.headers)

    return {
        "method": "GET",
        "url": resolve_channel_model_list_url(channel),
        "headers": build_upstream_headers(
            {"authorization": f"Bearer {api_key}"},
            headers,
            user_agent=_default_lens_user_agent(),
            upstream_headers_config=upstream_headers_config,
        ),
    }


@lru_cache(maxsize=256)
def _compile_model_list_pattern(match_regex: str) -> re.Pattern[str]:
    return re.compile(match_regex)


def _parse_model_list(payload: dict[str, Any], match_regex: str) -> list[str]:
    return [item.model_name for item in _parse_model_items(payload, match_regex)]


def _parse_model_items(
    payload: dict[str, Any], match_regex: str
) -> list[_ModelListItem]:
    unique_items: dict[str, _ModelListItem] = {}
    names: list[str] = []
    if "data" in payload:
        items = payload["data"]
    elif "models" in payload:
        items = payload["models"]
    else:
        raise ValueError("Model list response missing data/models")
    if not isinstance(items, list):
        raise ValueError("Model list response data/models must be a list")
    for item in items:
        if not isinstance(item, dict):
            raise ValueError("Model list item must be an object")
        value = str(item.get("id") or item.get("name") or "")
        value = value.strip()
        if not value:
            raise ValueError("Model list item missing model name")
        if value not in unique_items:
            names.append(value)
            unique_items[value] = _ModelListItem(model_name=value, protocols=[])
        existing = unique_items[value]
        for protocol in _infer_model_protocols(item):
            if protocol not in existing.protocols:
                existing.protocols.append(protocol)

    if not match_regex.strip():
        return [unique_items[name] for name in names]

    pattern = _compile_model_list_pattern(match_regex)
    return [unique_items[name] for name in names if pattern.search(name)]


def _infer_model_protocols(item: Mapping[str, Any]) -> list[ProtocolKind]:
    protocols: list[ProtocolKind] = []
    for key in ("supported_protocols", "protocols"):
        raw_values = item.get(key)
        if isinstance(raw_values, list):
            for raw_value in raw_values:
                _append_inferred_protocol(protocols, raw_value)

    capabilities = item.get("capabilities")
    if isinstance(capabilities, Mapping):
        if capabilities.get("chat") is True:
            _append_inferred_protocol(protocols, ProtocolKind.OPENAI_CHAT)
        if capabilities.get("responses") is True:
            _append_inferred_protocol(protocols, ProtocolKind.OPENAI_RESPONSES)
        if capabilities.get("embeddings") is True:
            _append_inferred_protocol(protocols, ProtocolKind.OPENAI_EMBEDDING)
        if capabilities.get("rerank") is True:
            _append_inferred_protocol(protocols, ProtocolKind.RERANK)

    for key in ("endpoint", "type"):
        raw_value = item.get(key)
        if isinstance(raw_value, str):
            _append_inferred_protocol(protocols, raw_value)
    return protocols


def _append_inferred_protocol(protocols: list[ProtocolKind], raw_value: Any) -> None:
    protocol = _coerce_model_protocol(raw_value)
    if protocol is not None and protocol not in protocols:
        protocols.append(protocol)


def _coerce_model_protocol(raw_value: Any) -> ProtocolKind | None:
    if isinstance(raw_value, ProtocolKind):
        return raw_value
    if not isinstance(raw_value, str):
        return None
    normalized = raw_value.strip().lower().replace("-", "_").replace(".", "_")
    aliases = {
        "chat": ProtocolKind.OPENAI_CHAT,
        "chat_completions": ProtocolKind.OPENAI_CHAT,
        "completions": ProtocolKind.OPENAI_CHAT,
        "openai_chat": ProtocolKind.OPENAI_CHAT,
        "responses": ProtocolKind.OPENAI_RESPONSES,
        "response": ProtocolKind.OPENAI_RESPONSES,
        "openai_responses": ProtocolKind.OPENAI_RESPONSES,
        "embedding": ProtocolKind.OPENAI_EMBEDDING,
        "embeddings": ProtocolKind.OPENAI_EMBEDDING,
        "openai_embedding": ProtocolKind.OPENAI_EMBEDDING,
        "image": ProtocolKind.OPENAI_IMAGE,
        "images": ProtocolKind.OPENAI_IMAGE,
        "openai_image": ProtocolKind.OPENAI_IMAGE,
        "rerank": ProtocolKind.RERANK,
        "reranking": ProtocolKind.RERANK,
        "anthropic": ProtocolKind.ANTHROPIC,
        "messages": ProtocolKind.ANTHROPIC,
        "gemini": ProtocolKind.GEMINI,
        "generate_content": ProtocolKind.GEMINI,
    }
    if normalized in aliases:
        return aliases[normalized]
    try:
        return ProtocolKind(normalized)
    except ValueError:
        return None
