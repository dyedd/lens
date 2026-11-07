from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx

from ....core.context_windows import parse_upstream_model_context_window
from ....core.errors import ModelDiscoveryError
from ....core.model_protocols import parse_declared_protocols
from ....core.upstream_rules import request_rule_context
from ....models.channels import ChannelConfig
from ....models.protocols import ProtocolKind
from ....models.upstream_rules import UpstreamHeadersConfig
from ....plugins.contract import UpstreamCall
from ....plugins.runtime import apply_credential_hooks, system_run
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
    errors: list[ModelDiscoveryError] = []
    for protocol in protocols:
        try:
            models = await fetch_upstream_models(
                channel.model_copy(update={"protocol": protocol})
            )
        except ModelDiscoveryError as exc:
            errors.append(exc)
            continue
        return UpstreamModelList(protocol=protocol, models=models)
    if len(errors) == 1:
        raise errors[0]
    if not errors:
        raise ModelDiscoveryError("No model listing protocol is available")
    raise ModelDiscoveryError(
        status_code=errors[0].status_code,
        message="; ".join(
            f"{protocol.value}: {exc.public_message}"
            for protocol, exc in zip(protocols, errors, strict=True)
        ),
    ) from errors[-1]


async def fetch_upstream_models(channel: ChannelConfig) -> list[UpstreamModel]:
    """List all models currently offered by an upstream."""
    runtime = await app_state.settings_repo.get_runtime_settings()
    proxy_url = resolve_upstream_proxy_url(channel, runtime["proxy_url"])
    client = resolve_http_client(proxy_url)

    try:
        request = await _model_list_request(channel, runtime["upstream_headers_config"])
        response = await client.request(**request, timeout=30)
        response.raise_for_status()
        return _parse_model_list(response.json(), protocol=channel.protocol)
    except httpx.HTTPStatusError as exc:
        detail = format_http_response_error(exc.response)
        raise ModelDiscoveryError(detail, status_code=exc.response.status_code) from exc
    except httpx.HTTPError as exc:
        raise ModelDiscoveryError(f"Transport error: {exc}") from exc
    except ValueError as exc:
        raise ModelDiscoveryError(str(exc), status_code=400) from exc


async def _model_list_request(
    channel: ChannelConfig, upstream_headers_config: UpstreamHeadersConfig | None = None
) -> dict[str, Any]:
    api_key = resolve_channel_api_key(channel)
    url = resolve_channel_model_list_url(channel, api_key)
    headers = build_upstream_headers(
        build_upstream_auth_headers(channel, api_key),
        list(channel.headers),
        user_agent=default_lens_user_agent(),
        upstream_headers_config=upstream_headers_config,
        context=request_rule_context(url, model_name="", protocol=channel.protocol),
    )
    # 凭据插件接手渠道鉴权时，模型列表请求也要用它签发的凭据；GET 没有请求体。
    hooked = await apply_credential_hooks(
        system_run(app_state.plugin_registry.hook_set(), channel.protocol.value),
        UpstreamCall(
            channel=channel,
            protocol=channel.protocol.value,
            url=url,
            headers=headers,
            body={},
        ),
    )
    return {"method": "GET", "url": hooked.url, "headers": hooked.headers}


def _parse_model_list(
    payload: dict[str, Any], *, protocol: ProtocolKind
) -> list[UpstreamModel]:
    if not isinstance(payload, dict):
        raise ValueError("Model list response must be an object")
    if payload.get("error") or payload.get("success") is False:
        raise ValueError("Upstream model list request failed")
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
            raise ValueError("Model list entry must be an object")
        methods = item.get("supportedGenerationMethods")
        if (
            protocol == ProtocolKind.GEMINI
            and isinstance(methods, list)
            and not any(
                method in {"generateContent", "streamGenerateContent"}
                for method in methods
            )
        ):
            continue
        value = str(item.get("id") or "").strip()
        if not value:
            # Gemini lists resource names such as "models/gemini-2.5-pro".
            value = str(item.get("name") or "").strip().removeprefix("models/")
        if not value:
            raise ValueError("Model list entry missing id/name")
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
