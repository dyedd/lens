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


def build_upstream_request(
    provider: ProviderConfig,
    body: dict[str, Any],
    settings: Settings,
) -> UpstreamRequest:
    if provider.protocol == ProtocolKind.OPENAI_CHAT:
        return UpstreamRequest(
            method="POST",
            url=f"{str(provider.base_url).rstrip('/')}/chat/completions",
            headers={
                "authorization": f"Bearer {provider.api_key}",
                "content-type": "application/json",
                **provider.headers,
            },
            json_body=_inject_model(body, provider.model_name),
        )

    if provider.protocol == ProtocolKind.OPENAI_RESPONSES:
        return UpstreamRequest(
            method="POST",
            url=f"{str(provider.base_url).rstrip('/')}/responses",
            headers={
                "authorization": f"Bearer {provider.api_key}",
                "content-type": "application/json",
                **provider.headers,
            },
            json_body=_inject_model(body, provider.model_name),
        )

    if provider.protocol == ProtocolKind.ANTHROPIC:
        return UpstreamRequest(
            method="POST",
            url=f"{str(provider.base_url).rstrip('/')}/messages",
            headers={
                "x-api-key": provider.api_key,
                "anthropic-version": settings.anthropic_version,
                "content-type": "application/json",
                **provider.headers,
            },
            json_body=_inject_model(body, provider.model_name),
        )

    if provider.protocol == ProtocolKind.GEMINI:
        model_name = provider.model_name or body.get("model")
        if not model_name:
            raise HTTPException(status_code=400, detail="Gemini provider requires model_name or request.model")

        path = "streamGenerateContent" if body.get("stream") else "generateContent"
        payload = {key: value for key, value in body.items() if key not in {"model", "stream"}}
        return UpstreamRequest(
            method="POST",
            url=(
                f"{str(provider.base_url).rstrip('/')}/models/{model_name}:{path}"
                f"?key={provider.api_key}"
            ),
            headers={
                "content-type": "application/json",
                **provider.headers,
            },
            json_body=payload,
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


def _inject_model(body: dict[str, Any], model_name: str | None) -> dict[str, Any]:
    if not model_name:
        return body

    payload = dict(body)
    payload["model"] = model_name
    return payload
