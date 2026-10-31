from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

import httpx
from fastapi import HTTPException

from ....core.context_windows import parse_upstream_model_context_window
from ....core.errors import ModelDiscoveryError
from ....core.model_protocols import parse_declared_protocols
from ....core.upstream_rules import request_rule_context
from ....models.channels import ChannelConfig
from ....models.protocols import ProtocolKind
from ...upstream_request import (
    build_upstream_auth_headers,
    build_upstream_headers,
    resolve_channel_api_key,
    resolve_channel_model_list_url,
    resolve_upstream_proxy_url,
)
from ..app_state import app_state
from ..upstream_support import (
    default_lens_user_agent,
    format_http_response_error,
    resolve_http_client,
)

LISTING_PROTOCOLS = (
    ProtocolKind.OPENAI_CHAT,
    ProtocolKind.ANTHROPIC,
    ProtocolKind.GEMINI,
)
NATIVE_LISTING_PROTOCOLS = frozenset({ProtocolKind.ANTHROPIC, ProtocolKind.GEMINI})


@dataclass(frozen=True, slots=True)
class UpstreamModel:
    name: str
    context_window: int | None = None
    # Protocols a NewAPI-style list declares for this model.
    protocols: tuple[ProtocolKind, ...] = ()


@dataclass(frozen=True, slots=True)
class UpstreamModelList:
    """A model list and the listing protocol that answered it."""

    protocol: ProtocolKind
    models: list[UpstreamModel]


async def fetch_upstream_model_list(
    channel: ChannelConfig, protocols: tuple[ProtocolKind, ...] = LISTING_PROTOCOLS
) -> UpstreamModelList:
    """List models with the first listing protocol the upstream accepts."""
    errors: list[HTTPException | ModelDiscoveryError] = []
    for protocol in protocols:
        try:
            models = await fetch_upstream_models(
                channel.model_copy(update={"protocol": protocol})
            )
        except (HTTPException, ModelDiscoveryError) as exc:
            errors.append(exc)
            continue
        return UpstreamModelList(protocol=protocol, models=models)
    if len(errors) == 1:
        raise errors[0]
    raise HTTPException(
        status_code=errors[0].status_code,
        detail="; ".join(
            f"{protocol.value}: {exc.public_message if isinstance(exc, ModelDiscoveryError) else exc.detail}"
            for protocol, exc in zip(protocols, errors, strict=True)
        ),
    )


async def fetch_upstream_models(channel: ChannelConfig) -> list[UpstreamModel]:
    """List all models currently offered by an upstream."""
    runtime = await app_state.settings_repo.get_runtime_settings()
    proxy_url = resolve_upstream_proxy_url(channel, runtime["proxy_url"])
    client = resolve_http_client(proxy_url)

    try:
        response = await client.request(
            **_model_list_request(channel, runtime["upstream_headers_config"])
        )
        response.raise_for_status()
        return _parse_model_list(response.json())
    except httpx.HTTPStatusError as exc:
        detail = format_http_response_error(exc.response)
        raise ModelDiscoveryError(detail, status_code=exc.response.status_code) from exc
    except httpx.HTTPError as exc:
        raise ModelDiscoveryError(f"Transport error: {exc}") from exc
    except ValueError as exc:
        raise ModelDiscoveryError(str(exc), status_code=400) from exc


def _model_list_request(
    channel: ChannelConfig, upstream_headers_config: Mapping[str, Any] | None = None
) -> dict[str, Any]:
    api_key = resolve_channel_api_key(channel)
    url = resolve_channel_model_list_url(channel, api_key)

    return {
        "method": "GET",
        "url": url,
        "headers": build_upstream_headers(
            build_upstream_auth_headers(channel, api_key),
            list(channel.headers),
            user_agent=default_lens_user_agent(),
            upstream_headers_config=upstream_headers_config,
            context=request_rule_context(url, model_name="", protocol=channel.protocol),
        ),
    }


def _parse_model_list(payload: dict[str, Any]) -> list[UpstreamModel]:
    models: list[UpstreamModel] = []
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
            # Gemini lists resource names such as "models/gemini-2.5-pro".
            value = str(item.get("name") or "").strip().removeprefix("models/")
        if not value:
            continue
        if value not in seen:
            seen.add(value)
            models.append(
                UpstreamModel(
                    name=value,
                    context_window=parse_upstream_model_context_window(item),
                    protocols=tuple(parse_declared_protocols(item)),
                )
            )

    return models
