from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from fastapi import HTTPException

from ..core.config import Settings
from ..models import ProtocolKind, ProviderConfig


@dataclass(frozen=True)
class UpstreamRequest:
    method: str
    url: str
    headers: dict[str, str]
    json_body: dict[str, Any]
    proxy_url: str | None = None


def build_upstream_request(
    provider: ProviderConfig,
    body: dict[str, Any],
    settings: Settings,
) -> UpstreamRequest:
    base_url = _resolve_base_url(provider)
    api_key = _resolve_api_key(provider)
    proxy_url = _resolve_proxy_url(provider)

    if provider.protocol == ProtocolKind.OPENAI_CHAT:
        return UpstreamRequest(
            method="POST",
            url=f"{_protocol_base_url(provider).rstrip('/')}/chat/completions",
            headers={
                "authorization": f"Bearer {api_key}",
                "content-type": "application/json",
                **provider.headers,
            },
            json_body=dict(body),
            proxy_url=proxy_url,
        )

    if provider.protocol == ProtocolKind.OPENAI_RESPONSES:
        return UpstreamRequest(
            method="POST",
            url=f"{_protocol_base_url(provider).rstrip('/')}/responses",
            headers={
                "authorization": f"Bearer {api_key}",
                "content-type": "application/json",
                **provider.headers,
            },
            json_body=dict(body),
            proxy_url=proxy_url,
        )

    if provider.protocol == ProtocolKind.ANTHROPIC:
        return UpstreamRequest(
            method="POST",
            url=f"{_protocol_base_url(provider).rstrip('/')}/messages",
            headers={
                "x-api-key": api_key,
                "anthropic-version": settings.anthropic_version,
                "content-type": "application/json",
                **provider.headers,
            },
            json_body=dict(body),
            proxy_url=proxy_url,
        )

    if provider.protocol == ProtocolKind.GEMINI:
        model_name = body.get("model")
        if not model_name:
            raise HTTPException(status_code=400, detail="Gemini request requires model")

        path = "streamGenerateContent" if body.get("stream") else "generateContent"
        payload = {key: value for key, value in body.items() if key not in {"model", "stream"}}
        return UpstreamRequest(
            method="POST",
            url=(
                f"{_protocol_base_url(provider).rstrip('/')}/models/{model_name}:{path}"
                f"?key={api_key}"
            ),
            headers={
                "content-type": "application/json",
                **provider.headers,
            },
            json_body=payload,
            proxy_url=proxy_url,
        )

    raise HTTPException(status_code=500, detail=f"Unsupported protocol={provider.protocol.value}")


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


def _resolve_base_url(provider: ProviderConfig) -> str:
    return _normalize_base_url(str(provider.base_url))


def _protocol_base_url(provider: ProviderConfig) -> str:
    root = _resolve_base_url(provider)
    if provider.protocol in {ProtocolKind.OPENAI_CHAT, ProtocolKind.OPENAI_RESPONSES, ProtocolKind.ANTHROPIC}:
        return f"{root}/v1"
    if provider.protocol == ProtocolKind.GEMINI:
        return f"{root}/v1beta"
    return root


def _normalize_base_url(value: str) -> str:
    normalized = value.strip().rstrip("/")
    if normalized.endswith("/v1beta"):
        return normalized[:-7]
    if normalized.endswith("/v1"):
        return normalized[:-3]
    return normalized


def _resolve_api_key(provider: ProviderConfig) -> str:
    for item in provider.keys:
        if item.enabled and item.key.strip():
            return item.key.strip()
    if provider.keys:
        return provider.keys[0].key.strip()
    return provider.api_key.strip()


def _resolve_proxy_url(provider: ProviderConfig) -> str | None:
    if not provider.proxy:
        return None
    value = provider.channel_proxy.strip()
    return value or None


def resolve_provider_base_url(provider: ProviderConfig) -> str:
    return _resolve_base_url(provider)


def resolve_provider_api_key(provider: ProviderConfig) -> str:
    return _resolve_api_key(provider)


def resolve_provider_proxy_url(provider: ProviderConfig) -> str | None:
    return _resolve_proxy_url(provider)
