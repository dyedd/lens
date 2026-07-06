from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from functools import lru_cache
from html.parser import HTMLParser
from typing import Any

import httpx
from fastapi import HTTPException

from ...core.config import settings
from ...models import ChannelConfig, ProtocolKind
from ..upstreams import (
    build_upstream_headers,
    resolve_channel_api_key,
    resolve_channel_model_list_url,
    resolve_upstream_proxy_url,
)
from .state import _read_system_version, app_state

GENERIC_USER_AGENT_TOKENS = (
    "python-httpx",
    "python/httpx",
    "python-requests",
    "python/requests",
    "python/http",
    "aiohttp",
    "httpcore",
    "urllib",
)

ANTHROPIC_FORWARD_HEADER_PREFIXES = (
    "anthropic-",
    "x-anthropic-",
    "x-claude-code-",
    "x-claude-remote-",
    "x-stainless-",
)
ANTHROPIC_FORWARD_HEADERS = frozenset(
    {
        "x-app",
        "x-app-name",
        "x-app-ver",
        "x-client-app",
        "x-environment-runner-version",
    }
)


@dataclass(slots=True)
class _ModelListItem:
    model_name: str
    protocols: list[ProtocolKind]


def _passthrough_headers(headers: httpx.Headers) -> dict[str, str]:
    allowed = {}
    for key in (
        "content-type",
        "cache-control",
        "x-request-id",
        "anthropic-request-id",
        "x-goog-request-id",
    ):
        if key in headers:
            allowed[key] = headers[key]
    return allowed


def _format_channel_error(detail: Any) -> str:
    detail_text = str(detail).strip() if detail is not None else ""
    if not detail_text:
        detail_text = "Unknown error"
    return _summarize_html_error_detail(detail_text)


class _HtmlTitleParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._in_title = False
        self._title_parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() == "title":
            self._in_title = True

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() == "title":
            self._in_title = False

    def handle_data(self, data: str) -> None:
        if self._in_title:
            self._title_parts.append(data)

    def title(self) -> str:
        return re.sub(r"\s+", " ", "".join(self._title_parts)).strip()


def _format_http_response_error(response: httpx.Response) -> str:
    detail = response.text or f"HTTP {response.status_code}"
    return _summarize_html_error_detail(
        detail,
        status_code=response.status_code,
        content_type=response.headers.get("content-type"),
    )


def _summarize_html_error_detail(
    detail: str,
    *,
    status_code: int | None = None,
    content_type: str | None = None,
) -> str:
    detail_text = detail.strip()
    if not detail_text:
        return f"HTTP {status_code}" if status_code is not None else "Unknown error"
    if not _looks_like_html(detail_text, content_type):
        return detail_text

    title = _extract_html_title(detail_text)
    if title:
        if status_code is not None:
            return f"HTTP {status_code}: {title}"
        return f"HTML error response: {title}"
    if status_code is not None:
        return f"HTTP {status_code}: HTML error response"
    return "HTML error response"


def _looks_like_html(detail: str, content_type: str | None = None) -> bool:
    if content_type and "html" in content_type.lower():
        return True
    lowered = detail[:1000].lower()
    return "<html" in lowered or "<!doctype html" in lowered or "<title" in lowered


def _extract_html_title(detail: str) -> str:
    parser = _HtmlTitleParser()
    parser.feed(detail)
    parser.close()
    return parser.title()[:200]


def _format_transport_error(exc: httpx.HTTPError, fallback_url: str) -> str:
    error_type = exc.__class__.__name__
    request = exc.request if hasattr(exc, "request") else None
    target_url = (
        str(request.url) if request and hasattr(request, "url") else fallback_url
    )
    try:
        target_label = str(httpx.URL(target_url).copy_with(query=None))
    except httpx.InvalidURL:
        target_label = target_url
    detail_text = str(exc).strip()
    if detail_text:
        return f"Transport error ({error_type}) while requesting {target_label}: {detail_text}"
    return f"Transport error ({error_type}) while requesting {target_label}"


@lru_cache(maxsize=1)
def _default_lens_user_agent() -> str:
    return f"Lens/{_read_system_version()}"


def _normalize_user_agent(value: str | None) -> str:
    normalized = (value or "").strip()
    if not normalized:
        return ""
    return "".join(char for char in normalized if ord(char) >= 32 and ord(char) != 127)[
        :300
    ].strip()


def _is_generic_user_agent(value: str) -> bool:
    normalized = value.strip().lower()
    if not normalized:
        return True
    return any(token in normalized for token in GENERIC_USER_AGENT_TOKENS)


def _forward_anthropic_headers(headers: Mapping[str, str]) -> dict[str, str]:
    forwarded: dict[str, str] = {}
    for name, value in headers.items():
        normalized_name = name.lower()
        if normalized_name not in ANTHROPIC_FORWARD_HEADERS and not (
            normalized_name.startswith(ANTHROPIC_FORWARD_HEADER_PREFIXES)
        ):
            continue
        normalized_value = value.strip()
        if normalized_value:
            forwarded[normalized_name] = normalized_value
    return forwarded


async def _fetch_upstream_models(channel: ChannelConfig) -> list[str]:
    runtime = await app_state.settings_repo.get_runtime_settings()
    proxy_url = resolve_upstream_proxy_url(channel, runtime["proxy_url"])
    client, close_client = _resolve_http_client(proxy_url)

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
        if close_client:
            await client.aclose()


def _resolve_http_client(proxy_url: str | None) -> tuple[httpx.AsyncClient, bool]:
    if not proxy_url:
        return app_state.http, False
    client = httpx.AsyncClient(
        proxy=proxy_url,
        timeout=app_state.http.timeout,
        limits=httpx.Limits(
            max_connections=settings.max_connections,
            max_keepalive_connections=settings.max_keepalive_connections,
        ),
        trust_env=False,
    )
    return client, True


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


def _append_inferred_protocol(
    protocols: list[ProtocolKind], raw_value: Any
) -> None:
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
