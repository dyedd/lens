from __future__ import annotations

import re
from collections.abc import Mapping
from functools import lru_cache
from typing import Any

import httpx
from fastapi import HTTPException

from ...models import ChannelConfig
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


async def _fetch_upstream_models(channel: ChannelConfig) -> list[str]:
    runtime = await app_state.settings_repo.get_runtime_settings()
    proxy_url = resolve_upstream_proxy_url(channel, runtime["proxy_url"])
    client = _resolve_http_client(proxy_url)

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
    names: list[str] = []
    seen: set[str] = set()
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
            continue
        value = str(item.get("id") or "").strip()
        if not value:
            value = str(item.get("name") or "").strip()
        if not value:
            continue
        if value not in seen:
            seen.add(value)
            names.append(value)

    if not match_regex.strip():
        return names

    pattern = _compile_model_list_pattern(match_regex)
    return [name for name in names if pattern.search(name)]
