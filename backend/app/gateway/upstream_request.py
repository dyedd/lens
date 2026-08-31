from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlsplit

from fastapi import HTTPException

from ..core.upstream_rules import (
    RuleContext,
    RuleLayer,
    apply_header_rules,
    request_rule_context,
    rules_from_config,
)
from ..core.urls import append_url_path, canonicalize_base_url
from ..models.channels import ChannelConfig
from ..models.protocols import ChannelProxyMode, ProtocolKind
from ..models.upstream_rules import HeaderRule


@dataclass(frozen=True, slots=True)
class UpstreamRequest:
    method: str
    url: str
    headers: dict[str, str]
    json_body: dict[str, Any]


_OPENAI_LIKE_PATH = {
    ProtocolKind.OPENAI_CHAT: "chat/completions",
    ProtocolKind.OPENAI_RESPONSES: "responses",
    ProtocolKind.OPENAI_EMBEDDING: "embeddings",
    ProtocolKind.OPENAI_IMAGE: "images/generations",
    ProtocolKind.RERANK: "rerank",
    ProtocolKind.ANTHROPIC: "messages",
}

_OPENAI_COMPATIBLE_PROTOCOLS = frozenset(
    {
        ProtocolKind.OPENAI_CHAT,
        ProtocolKind.OPENAI_RESPONSES,
        ProtocolKind.OPENAI_EMBEDDING,
        ProtocolKind.OPENAI_IMAGE,
        ProtocolKind.RERANK,
    }
)
_GLM_HOSTS = frozenset({"open.bigmodel.cn", "api.z.ai"})
_GLM_OPENAI_VERSIONED_PATHS = frozenset({"/api/paas/v4", "/api/coding/paas/v4"})
ANTHROPIC_VERSION = "2023-06-01"


def build_upstream_request(
    channel: ChannelConfig,
    body: dict[str, Any],
    credential_id: str | None = None,
    user_agent: str | None = None,
    forwarded_headers: Mapping[str, str] | None = None,
    upstream_headers_config: Mapping[str, Any] | None = None,
    model_group_headers: list[HeaderRule] | None = None,
    path_suffix: str | None = None,
) -> UpstreamRequest:
    """Build an authenticated request for an upstream channel."""
    api_key = resolve_channel_api_key(channel, credential_id=credential_id)
    context_model_name = str(body.get("model") or "")

    if channel.protocol == ProtocolKind.GEMINI:
        from ..core.model_name_parser import parse_model_name

        model_name = str(body.get("model") or "")
        model_name = parse_model_name(model_name).base_model
        context_model_name = model_name
        if not model_name:
            raise HTTPException(status_code=400, detail="Gemini request requires model")

        operation = "streamGenerateContent" if body.get("stream") else "generateContent"
        payload = {
            key: value for key, value in body.items() if key not in {"model", "stream"}
        }
        url = append_url_path(
            _protocol_base_url(channel),
            "models",
            f"{model_name}:{operation}",
            query_params={"key": api_key},
        )
        default_headers = {
            "content-type": "application/json",
            "accept": "application/json",
        }
    else:
        suffix = path_suffix or _OPENAI_LIKE_PATH.get(channel.protocol)
        if suffix is None:
            raise HTTPException(
                status_code=500, detail=f"Unsupported protocol={channel.protocol.value}"
            )
        if channel.protocol == ProtocolKind.ANTHROPIC:
            default_headers = {
                "x-api-key": api_key,
                "anthropic-version": ANTHROPIC_VERSION,
                "content-type": "application/json",
                "accept": "application/json",
            }
            if forwarded_headers:
                default_headers.update(forwarded_headers)
        else:
            default_headers = {
                "authorization": f"Bearer {api_key}",
                "content-type": "application/json",
                "accept": "application/json",
            }
        url = append_url_path(_protocol_base_url(channel), suffix)
        payload = dict(body)

    context = request_rule_context(
        url, model_name=context_model_name, protocol=channel.protocol
    )
    headers = build_upstream_headers(
        default_headers,
        channel.headers,
        user_agent=user_agent,
        upstream_headers_config=upstream_headers_config,
        model_group_headers=model_group_headers,
        context=context,
    )
    return UpstreamRequest(method="POST", url=url, headers=headers, json_body=payload)


def build_upstream_headers(
    default_headers: dict[str, str],
    channel_headers: list[HeaderRule],
    user_agent: str | None = None,
    upstream_headers_config: Mapping[str, Any] | None = None,
    model_group_headers: list[HeaderRule] | None = None,
    *,
    path: str = "",
    model_name: str = "",
    context: RuleContext | None = None,
) -> dict[str, str]:
    """Apply default, global, channel, and model-group header rules."""
    if context is None:
        context = RuleContext(path=path, model_name=model_name, protocol="")
    headers: dict[str, str] = {}
    _merge_headers(headers, default_headers)
    if user_agent and not any(
        rule.name.lower() == "user-agent"
        and rule.action in {"override", "append", "remove"}
        for rule in channel_headers
    ):
        _set_header(headers, "user-agent", user_agent)
    global_rules = rules_from_config(upstream_headers_config, "headers")
    return apply_header_rules(
        headers,
        [
            RuleLayer("global", headers=global_rules),
            RuleLayer("channel", headers=channel_headers),
            RuleLayer("model group", headers=model_group_headers or []),
        ],
        context=context,
    )


def _get_header(headers: dict[str, str], name: str) -> str | None:
    return next(
        (value for key, value in headers.items() if key.lower() == name.lower()), None
    )


def _remove_header(headers: dict[str, str], name: str, token: str) -> None:
    for key in list(headers):
        if key.lower() != name.lower():
            continue
        if not token:
            headers.pop(key)
            return
        tokens = [
            part.strip()
            for part in headers[key].split(",")
            if part.strip().lower() != token.lower()
        ]
        if tokens:
            headers[key] = ", ".join(tokens)
        else:
            headers.pop(key)


def _set_header(headers: dict[str, str], key: str, value: str) -> None:
    trimmed_key = key.strip()
    if not trimmed_key:
        return
    lower_key = trimmed_key.lower()
    for existing_key in list(headers):
        if existing_key.lower() == lower_key:
            headers.pop(existing_key)
            break
    headers[trimmed_key] = str(value)


def _merge_headers(headers: dict[str, str], updates: Mapping[str, str] | None) -> None:
    if not updates:
        return
    for key, value in updates.items():
        _set_header(headers, key, value)


def _protocol_base_url(channel: ChannelConfig) -> str:
    root = canonicalize_base_url(str(channel.base_url))
    parsed = urlsplit(root)

    if (
        channel.protocol in _OPENAI_COMPATIBLE_PROTOCOLS
        and (parsed.hostname or "") in _GLM_HOSTS
        and parsed.path.rstrip("/") in _GLM_OPENAI_VERSIONED_PATHS
    ):
        return root

    if (
        channel.protocol in _OPENAI_COMPATIBLE_PROTOCOLS
        or channel.protocol == ProtocolKind.ANTHROPIC
    ):
        return append_url_path(root, "v1")
    if channel.protocol == ProtocolKind.GEMINI:
        return append_url_path(root, "v1beta")
    return root


def resolve_channel_api_key(
    channel: ChannelConfig, credential_id: str | None = None
) -> str:
    """Resolve an enabled API key for a channel."""
    if credential_id:
        for item in channel.keys:
            if item.id == credential_id and item.enabled and item.key.strip():
                return item.key.strip()
        raise HTTPException(
            status_code=503,
            detail=f"Credential {credential_id} is not available for channel {channel.name}",
        )

    for item in channel.keys:
        if item.enabled and item.key.strip():
            return item.key.strip()
    raise HTTPException(
        status_code=503,
        detail=f"No enabled credentials available for channel {channel.name}",
    )


def resolve_upstream_proxy_url(
    channel: ChannelConfig, global_proxy_url: str | None = None
) -> str | None:
    """Resolve the effective proxy URL for a channel."""
    if channel.proxy_mode == ChannelProxyMode.DIRECT:
        return None
    if channel.proxy_mode == ChannelProxyMode.CUSTOM:
        return channel.channel_proxy.strip() or None
    global_proxy = (global_proxy_url or "").strip()
    return global_proxy or None


def resolve_channel_model_list_url(channel: ChannelConfig) -> str:
    """Build the model-list endpoint URL for a channel."""
    return append_url_path(_protocol_base_url(channel), "models")
