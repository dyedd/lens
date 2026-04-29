from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from urllib.parse import urlsplit

from fastapi import HTTPException

from ..core.config import Settings
from ..models import ChannelConfig, ProtocolKind


@dataclass(frozen=True)
class UpstreamRequest:
    method: str
    url: str
    headers: dict[str, str]
    json_body: dict[str, Any]
    proxy_url: str | None = None


def build_upstream_request(
    channel: ChannelConfig,
    body: dict[str, Any],
    settings: Settings,
    credential_id: str | None = None,
) -> UpstreamRequest:
    api_key = _resolve_api_key(channel, credential_id=credential_id)
    proxy_url = _resolve_proxy_url(channel)
    target_url = _protocol_request_url(channel, body)

    if channel.protocol == ProtocolKind.OPENAI_CHAT:
        return UpstreamRequest(
            method="POST",
            url=target_url,
            headers={
                "authorization": f"Bearer {api_key}",
                "content-type": "application/json",
                **channel.headers,
            },
            json_body=dict(body),
            proxy_url=proxy_url,
        )

    if channel.protocol == ProtocolKind.OPENAI_RESPONSES:
        return UpstreamRequest(
            method="POST",
            url=target_url,
            headers={
                "authorization": f"Bearer {api_key}",
                "content-type": "application/json",
                **channel.headers,
            },
            json_body=dict(body),
            proxy_url=proxy_url,
        )

    if channel.protocol == ProtocolKind.ANTHROPIC:
        return UpstreamRequest(
            method="POST",
            url=target_url,
            headers={
                "x-api-key": api_key,
                "anthropic-version": settings.anthropic_version,
                "content-type": "application/json",
                **channel.headers,
            },
            json_body=dict(body),
            proxy_url=proxy_url,
        )

    if channel.protocol == ProtocolKind.GEMINI:
        model_name = body.get("model")
        if not model_name:
            raise HTTPException(status_code=400, detail="Gemini request requires model")

        path = "streamGenerateContent" if body.get("stream") else "generateContent"
        payload = {key: value for key, value in body.items() if key not in {"model", "stream"}}
        return UpstreamRequest(
            method="POST",
            url=_gemini_request_url(channel, model_name, path, api_key),
            headers={
                "content-type": "application/json",
                **channel.headers,
            },
            json_body=payload,
            proxy_url=proxy_url,
        )

    raise HTTPException(status_code=500, detail=f"Unsupported protocol={channel.protocol.value}")


def protocol_for_path(path: str) -> ProtocolKind:
    mapping = {
        "/v1/chat/completions": ProtocolKind.OPENAI_CHAT,
        "/v1/responses": ProtocolKind.OPENAI_RESPONSES,
        "/v1/messages": ProtocolKind.ANTHROPIC,
        "/v1beta/models": ProtocolKind.GEMINI,
    }
    try:
        return mapping[path]
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"Unsupported path={path}") from exc


def _resolve_base_url(channel: ChannelConfig) -> str:
    return _normalize_base_url(str(channel.base_url))


def _protocol_request_url(channel: ChannelConfig, body: dict[str, Any]) -> str:
    protocol_base = _protocol_base_url(channel).rstrip("/")
    if channel.protocol == ProtocolKind.OPENAI_CHAT:
        return f"{protocol_base}/chat/completions"
    if channel.protocol == ProtocolKind.OPENAI_RESPONSES:
        return f"{protocol_base}/responses"
    if channel.protocol == ProtocolKind.ANTHROPIC:
        return f"{protocol_base}/messages"
    raise HTTPException(status_code=500, detail=f"Unsupported protocol={channel.protocol.value}")


def _gemini_request_url(channel: ChannelConfig, model_name: str, path: str, api_key: str) -> str:
    return f"{_protocol_base_url(channel).rstrip('/')}/models/{model_name}:{path}?key={api_key}"


def _protocol_base_url(channel: ChannelConfig) -> str:
    root = _resolve_base_url(channel)
    if _is_bigmodel_openai_chat_prefix(root, channel.protocol):
        return root
    if channel.protocol in {ProtocolKind.OPENAI_CHAT, ProtocolKind.OPENAI_RESPONSES, ProtocolKind.ANTHROPIC}:
        return f"{root}/v1"
    if channel.protocol == ProtocolKind.GEMINI:
        return f"{root}/v1beta"
    return root


def _is_bigmodel_openai_chat_prefix(root: str, protocol: ProtocolKind) -> bool:
    if protocol != ProtocolKind.OPENAI_CHAT:
        return False

    parsed = urlsplit(root)
    if parsed.hostname != "open.bigmodel.cn":
        return False

    normalized_path = parsed.path.rstrip("/")
    return normalized_path in {"/api/paas/v4", "/api/coding/paas/v4"}


def _normalize_base_url(value: str) -> str:
    normalized = value.strip()
    if normalized.endswith("#"):
        normalized = normalized[:-1].rstrip()
    normalized = normalized.rstrip("/")
    if normalized.endswith("/v1beta"):
        return normalized[:-7]
    if normalized.endswith("/v1"):
        return normalized[:-3]
    return normalized


def _resolve_api_key(channel: ChannelConfig, credential_id: str | None = None) -> str:
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
    if channel.keys:
        return channel.keys[0].key.strip()
    return channel.api_key.strip()


def _resolve_proxy_url(channel: ChannelConfig) -> str | None:
    value = channel.channel_proxy.strip()
    return value or None


def resolve_upstream_proxy_url(channel: ChannelConfig, global_proxy_url: str | None = None) -> str | None:
    channel_proxy = _resolve_proxy_url(channel)
    if channel_proxy:
        return channel_proxy
    value = (global_proxy_url or "").strip()
    return value or None


def resolve_channel_base_url(channel: ChannelConfig) -> str:
    return _resolve_base_url(channel)


def resolve_channel_model_list_url(channel: ChannelConfig) -> str:
    return f"{_protocol_base_url(channel).rstrip('/')}/models"


def resolve_channel_api_key(channel: ChannelConfig, credential_id: str | None = None) -> str:
    return _resolve_api_key(channel, credential_id=credential_id)


def resolve_channel_proxy_url(channel: ChannelConfig) -> str | None:
    return _resolve_proxy_url(channel)
