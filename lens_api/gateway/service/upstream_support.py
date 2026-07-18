from __future__ import annotations

import re
from collections.abc import Mapping
from functools import lru_cache
from html.parser import HTMLParser
from typing import Any

import httpx

from .app_state import _read_system_version, app_state

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


def _effective_user_agent_from_headers(
    headers: Mapping[str, str], fallback: str
) -> str:
    for name, value in headers.items():
        if name.lower() == "user-agent":
            return _normalize_user_agent(value)
    return fallback


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


def _resolve_http_client(proxy_url: str | None) -> httpx.AsyncClient:
    return app_state.get_http_client(proxy_url)
