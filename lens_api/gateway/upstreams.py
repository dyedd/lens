from dataclasses import dataclass
from typing import Any
from urllib.parse import urlencode, urlsplit, urlunsplit

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


_OPENAI_LIKE_PATH = {
    ProtocolKind.OPENAI_CHAT: "chat/completions",
    ProtocolKind.OPENAI_RESPONSES: "responses",
    ProtocolKind.OPENAI_EMBEDDING: "embeddings",
    ProtocolKind.ANTHROPIC: "messages",
}


def build_upstream_request(
    channel: ChannelConfig,
    body: dict[str, Any],
    settings: Settings,
    credential_id: str | None = None,
    user_agent: str | None = None,
) -> UpstreamRequest:
    api_key = resolve_channel_api_key(channel, credential_id=credential_id)
    proxy_url = channel.channel_proxy.strip() or None

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
            url=_append_url_path(
                _protocol_base_url(channel),
                "models",
                f"{model_name}:{path}",
                query_params={"key": api_key},
            ),
            headers=build_upstream_headers(
                {"content-type": "application/json"},
                channel.headers,
                user_agent=user_agent,
            ),
            json_body=payload,
            proxy_url=proxy_url,
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
    else:
        default_headers = {
            "authorization": f"Bearer {api_key}",
            "content-type": "application/json",
        }

    return UpstreamRequest(
        method="POST",
        url=_append_url_path(_protocol_base_url(channel), suffix),
        headers=build_upstream_headers(
            default_headers, channel.headers, user_agent=user_agent
        ),
        json_body=dict(body),
        proxy_url=proxy_url,
    )


def build_upstream_headers(
    default_headers: dict[str, str],
    channel_headers: dict[str, str],
    user_agent: str | None = None,
) -> dict[str, str]:
    headers = dict(default_headers)
    if user_agent and not any(key.lower() == "user-agent" for key in channel_headers):
        headers["user-agent"] = user_agent
    headers.update(channel_headers)
    return headers


def _protocol_base_url(channel: ChannelConfig) -> str:
    root = _normalize_base_url(str(channel.base_url))
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
        ProtocolKind.ANTHROPIC,
    }:
        return _append_url_path(root, "v1")
    if channel.protocol == ProtocolKind.GEMINI:
        return _append_url_path(root, "v1beta")
    return root


def _normalize_base_url(value: str) -> str:
    normalized = value.strip()
    parsed = urlsplit(normalized)
    path = parsed.path.rstrip("/")
    if path.endswith("/v1beta"):
        path = path[:-7]
    elif path.endswith("/v1"):
        path = path[:-3]
    return _urlunsplit_preserving_empty_components(
        normalized,
        parsed.scheme,
        parsed.netloc,
        path,
        parsed.query,
        parsed.fragment,
    )


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
    if channel.keys:
        return channel.keys[0].key.strip()
    return channel.api_key.strip()


def resolve_upstream_proxy_url(
    channel: ChannelConfig, global_proxy_url: str | None = None
) -> str | None:
    channel_proxy = channel.channel_proxy.strip()
    if channel_proxy:
        return channel_proxy
    global_proxy = (global_proxy_url or "").strip()
    return global_proxy or None


def resolve_channel_model_list_url(channel: ChannelConfig) -> str:
    return _append_url_path(_protocol_base_url(channel), "models")


def append_channel_url_path(
    channel: ChannelConfig,
    *segments: str,
    query_params: dict[str, str] | None = None,
) -> str:
    return _append_url_path(
        _normalize_base_url(str(channel.base_url)),
        *segments,
        query_params=query_params,
    )


def _append_url_path(
    base_url: str,
    *segments: str,
    query_params: dict[str, str] | None = None,
) -> str:
    parsed = urlsplit(base_url)
    path_parts = [parsed.path.rstrip("/")]
    path_parts.extend(segment.strip("/") for segment in segments if segment.strip("/"))
    path = "/".join(part for part in path_parts if part)
    if parsed.path.startswith("/") and not path.startswith("/"):
        path = f"/{path}"
    if not path:
        path = parsed.path

    query = parsed.query
    if query_params:
        encoded_params = urlencode(query_params)
        query = f"{query}&{encoded_params}" if query else encoded_params

    return _urlunsplit_preserving_empty_components(
        base_url,
        parsed.scheme,
        parsed.netloc,
        path,
        query,
        parsed.fragment,
    )


def _urlunsplit_preserving_empty_components(
    source: str,
    scheme: str,
    netloc: str,
    path: str,
    query: str,
    fragment: str,
) -> str:
    rebuilt = urlunsplit((scheme, netloc, path, query, fragment))
    before_fragment, fragment_separator, _ = source.partition("#")
    has_empty_query = "?" in before_fragment and query == ""
    has_empty_fragment = bool(fragment_separator) and fragment == ""

    if has_empty_query:
        if "#" in rebuilt:
            rebuilt = rebuilt.replace("#", "?#", 1)
        else:
            rebuilt += "?"
    if has_empty_fragment and "#" not in rebuilt:
        rebuilt += "#"
    return rebuilt
