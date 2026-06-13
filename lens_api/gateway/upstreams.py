from dataclasses import dataclass
from collections.abc import Mapping
import re
from typing import Any
from urllib.parse import urlsplit

from fastapi import HTTPException

from ..core.config import Settings
from ..core.url_utils import normalize_base_url, append_url_path
from ..models import ChannelConfig, ChannelProxyMode, ProtocolKind


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
    ProtocolKind.RERANK: "rerank",
    ProtocolKind.ANTHROPIC: "messages",
}


def build_upstream_request(
    channel: ChannelConfig,
    body: dict[str, Any],
    settings: Settings,
    credential_id: str | None = None,
    user_agent: str | None = None,
    forwarded_headers: Mapping[str, str] | None = None,
    upstream_headers_config: Mapping[str, Any] | None = None,
) -> UpstreamRequest:
    api_key = resolve_channel_api_key(channel, credential_id=credential_id)

    if channel.protocol == ProtocolKind.GEMINI:
        model_name = body.get("model")
        if not model_name:
            raise HTTPException(status_code=400, detail="Gemini request requires model")

        path = "streamGenerateContent" if body.get("stream") else "generateContent"
        payload = {
            key: value for key, value in body.items() if key not in {"model", "stream"}
        }
        return UpstreamRequest(
            method="POST",
            url=append_url_path(
                _protocol_base_url(channel),
                "models",
                f"{model_name}:{path}",
                query_params={"key": api_key},
            ),
            headers=build_upstream_headers(
                {"content-type": "application/json"},
                channel.headers,
                user_agent=user_agent,
                upstream_headers_config=upstream_headers_config,
                model_name=model_name,
            ),
            json_body=payload,
        )

    suffix = _OPENAI_LIKE_PATH.get(channel.protocol)
    if suffix is None:
        raise HTTPException(
            status_code=500, detail=f"Unsupported protocol={channel.protocol.value}"
        )

    if channel.protocol == ProtocolKind.ANTHROPIC:
        default_headers = {
            "x-api-key": api_key,
            "anthropic-version": settings.anthropic_version,
            "content-type": "application/json",
        }
        if forwarded_headers:
            default_headers.update(forwarded_headers)
    else:
        default_headers = {
            "authorization": f"Bearer {api_key}",
            "content-type": "application/json",
        }

    return UpstreamRequest(
        method="POST",
        url=append_url_path(_protocol_base_url(channel), suffix),
        headers=build_upstream_headers(
            default_headers,
            channel.headers,
            user_agent=user_agent,
            upstream_headers_config=upstream_headers_config,
            model_name=body.get("model") or "",
        ),
        json_body=dict(body),
    )


def build_upstream_headers(
    default_headers: dict[str, str],
    channel_headers: dict[str, str],
    user_agent: str | None = None,
    upstream_headers_config: Mapping[str, Any] | None = None,
    model_name: str | None = None,
) -> dict[str, str]:
    headers: dict[str, str] = {}
    _merge_headers(headers, default_headers)
    if user_agent and not any(key.lower() == "user-agent" for key in channel_headers):
        _set_header(headers, "user-agent", user_agent)
    _merge_headers(headers, _upstream_global_headers(upstream_headers_config))
    for rule_headers in _matching_upstream_rule_headers(
        upstream_headers_config, model_name
    ):
        _merge_headers(headers, rule_headers)
    _merge_headers(headers, channel_headers)
    return headers


def _set_header(headers: dict[str, str], key: str, value: str) -> None:
    normalized_key = key.strip()
    if not normalized_key:
        return
    lower_key = normalized_key.lower()
    for existing_key in list(headers):
        if existing_key.lower() == lower_key:
            headers.pop(existing_key)
            break
    headers[normalized_key] = str(value)


def _merge_headers(headers: dict[str, str], updates: Mapping[str, str] | None) -> None:
    if not updates:
        return
    for key, value in updates.items():
        _set_header(headers, key, value)


def _upstream_global_headers(
    upstream_headers_config: Mapping[str, Any] | None,
) -> dict[str, str] | None:
    if not upstream_headers_config:
        return None
    return upstream_headers_config.get("global")


def _matching_upstream_rule_headers(
    upstream_headers_config: Mapping[str, Any] | None,
    model_name: str | None,
) -> list[dict[str, str]]:
    if not upstream_headers_config:
        return []
    rules = upstream_headers_config.get("rules", [])
    matched: list[dict[str, str]] = []
    normalized_model = (model_name or "").strip()
    if not normalized_model:
        return []
    for rule in rules:
        if not rule.get("enabled", True):
            continue
        if not _upstream_header_rule_matches(rule, normalized_model):
            continue
        matched.append(rule["headers"])
    return matched


def _upstream_header_rule_matches(rule: dict[str, Any], model_name: str) -> bool:
    match_type = rule.get("match_type", "exact")
    if match_type == "regex":
        pattern = rule.get("pattern", "").strip()
        if not pattern:
            return False
        try:
            return bool(re.search(pattern, model_name))
        except re.error:
            return False
    models = rule.get("models", [])
    return model_name in models


def _protocol_base_url(channel: ChannelConfig) -> str:
    root = normalize_base_url(str(channel.base_url))
    if channel.protocol == ProtocolKind.OPENAI_CHAT:
        parsed = urlsplit(root)
        if parsed.hostname == "open.bigmodel.cn" and parsed.path.rstrip("/") in {
            "/api/paas/v4",
            "/api/coding/paas/v4",
        }:
            return root
    if channel.protocol in {
        ProtocolKind.OPENAI_CHAT,
        ProtocolKind.OPENAI_RESPONSES,
        ProtocolKind.OPENAI_EMBEDDING,
        ProtocolKind.RERANK,
        ProtocolKind.ANTHROPIC,
    }:
        return append_url_path(root, "v1")
    if channel.protocol == ProtocolKind.GEMINI:
        return append_url_path(root, "v1beta")
    return root


def resolve_channel_api_key(
    channel: ChannelConfig, credential_id: str | None = None
) -> str:
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
    if channel.proxy_mode == ChannelProxyMode.DIRECT:
        return None
    if channel.proxy_mode == ChannelProxyMode.CUSTOM:
        return channel.channel_proxy.strip() or None
    global_proxy = (global_proxy_url or "").strip()
    return global_proxy or None


def resolve_channel_model_list_url(channel: ChannelConfig) -> str:
    return append_url_path(_protocol_base_url(channel), "models")
