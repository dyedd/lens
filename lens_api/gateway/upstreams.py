from dataclasses import dataclass
from collections.abc import Mapping
import re
from typing import Any
from urllib.parse import urlencode, urlsplit, urlunsplit

from fastapi import HTTPException

from ..core.config import Settings
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
                upstream_headers_config=upstream_headers_config,
                model_name=str(model_name),
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
        url=_append_url_path(_protocol_base_url(channel), suffix),
        headers=build_upstream_headers(
            default_headers,
            channel.headers,
            user_agent=user_agent,
            upstream_headers_config=upstream_headers_config,
            model_name=str(body.get("model") or ""),
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
        _set_header(headers, str(key), str(value))


def _upstream_global_headers(
    upstream_headers_config: Mapping[str, Any] | None,
) -> Mapping[str, str] | None:
    if not isinstance(upstream_headers_config, Mapping):
        return None
    global_headers = upstream_headers_config.get("global")
    if isinstance(global_headers, Mapping):
        return {str(key): str(value) for key, value in global_headers.items()}
    return None


def _matching_upstream_rule_headers(
    upstream_headers_config: Mapping[str, Any] | None,
    model_name: str | None,
) -> list[Mapping[str, str]]:
    if not isinstance(upstream_headers_config, Mapping):
        return []
    rules = upstream_headers_config.get("rules")
    if not isinstance(rules, list):
        return []
    matched: list[Mapping[str, str]] = []
    normalized_model = (model_name or "").strip()
    for rule in rules:
        if not isinstance(rule, Mapping):
            continue
        if not bool(rule.get("enabled", True)):
            continue
        if not _upstream_header_rule_matches(rule, normalized_model):
            continue
        headers = rule.get("headers")
        if isinstance(headers, Mapping):
            matched.append({str(key): str(value) for key, value in headers.items()})
    return matched


def _upstream_header_rule_matches(rule: Mapping[str, Any], model_name: str) -> bool:
    if not model_name:
        return False
    match_type = str(rule.get("match_type") or "exact")
    if match_type == "regex":
        pattern = str(rule.get("pattern") or "").strip()
        if not pattern:
            return False
        try:
            return bool(re.search(pattern, model_name))
        except re.error:
            return False
    models = rule.get("models")
    if not isinstance(models, list):
        return False
    return any(str(item).strip() == model_name for item in models)


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
        ProtocolKind.RERANK,
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
