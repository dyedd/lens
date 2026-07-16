from __future__ import annotations

from time import perf_counter
from typing import Any

import httpx
from fastapi import HTTPException

from ...models import (
    ChannelConfig,
    ProtocolKind,
    SiteModelTestRequest,
    SiteModelTestResult,
)
from ..upstream_request import (
    UpstreamRequest,
    build_upstream_request,
    resolve_upstream_proxy_url,
)
from .app_state import app_state
from .payload_serialization import _decode_content_bytes
from .routing_plan import _apply_param_override, _elapsed_ms
from .runtime_types import UpstreamRequestError
from .site_model_output import (
    extract_site_model_output,
    extract_site_model_stream_output,
)
from .upstream_support import (
    _default_lens_user_agent,
    _format_channel_error,
    _format_http_response_error,
    _format_transport_error,
    _resolve_http_client,
)


def _site_model_probe_channel(payload: SiteModelTestRequest) -> ChannelConfig:
    return ChannelConfig(
        id="model-test",
        name=payload.credential.name or "model-test",
        protocol=payload.protocol,
        base_url=payload.base_url,
        api_key=payload.credential.api_key,
        headers=payload.headers,
        model_patterns=[],
        keys=[
            {
                "id": payload.credential.id,
                "key": payload.credential.api_key,
                "remark": payload.credential.name,
                "enabled": True,
            }
        ],
        models=[],
        proxy_mode=payload.proxy_mode,
        channel_proxy=payload.channel_proxy,
        param_override=payload.param_override,
        match_regex="",
    )


async def _call_site_model_probe_channel(
    *,
    channel: ChannelConfig,
    body: dict[str, Any],
    model_name: str,
    credential_id: str,
) -> SiteModelTestResult:
    runtime = await app_state.settings_repo.get_runtime_settings()
    upstream = build_upstream_request(
        channel,
        body,
        credential_id=credential_id,
        user_agent=_default_lens_user_agent(),
        upstream_headers_config=runtime["upstream_headers_config"],
    )
    proxy_url = resolve_upstream_proxy_url(channel, runtime["proxy_url"])
    client = _resolve_http_client(proxy_url)

    started_at = perf_counter()
    return await _run_site_model_probe_request(
        client=client,
        upstream=upstream,
        channel=channel,
        model_name=model_name,
        credential_id=credential_id,
        started_at=started_at,
    )


async def _run_site_model_probe_request(
    *,
    client: httpx.AsyncClient,
    upstream: UpstreamRequest,
    channel: ChannelConfig,
    model_name: str,
    credential_id: str,
    started_at: float,
) -> SiteModelTestResult:
    try:
        response = await client.request(
            upstream.method,
            upstream.url,
            headers=upstream.headers,
            json=upstream.json_body,
        )
        latency_ms = _elapsed_ms(started_at)
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            await exc.response.aread()
            return SiteModelTestResult(
                success=False,
                status_code=exc.response.status_code,
                latency_ms=latency_ms,
                model_name=model_name,
                credential_id=credential_id,
                error_message=_format_http_response_error(exc.response),
            )
        content_type = (response.headers.get("content-type") or "").lower()
        if "text/event-stream" in content_type:
            raw_content = _decode_content_bytes(response.content) or ""
            output_text = extract_site_model_stream_output(
                channel.protocol, raw_content
            )
        else:
            output_text = extract_site_model_output(channel.protocol, response.json())
        return SiteModelTestResult(
            success=True,
            status_code=response.status_code,
            latency_ms=latency_ms,
            model_name=model_name,
            credential_id=credential_id,
            output_text=output_text,
        )
    except httpx.HTTPError as exc:
        return SiteModelTestResult(
            success=False,
            status_code=502,
            latency_ms=_elapsed_ms(started_at),
            model_name=model_name,
            credential_id=credential_id,
            error_message=_format_transport_error(exc, upstream.url),
        )
    except ValueError as exc:
        return SiteModelTestResult(
            success=False,
            status_code=502,
            latency_ms=_elapsed_ms(started_at),
            model_name=model_name,
            credential_id=credential_id,
            error_message=f"Invalid upstream response: {exc}",
        )


def _site_model_probe_body(payload: SiteModelTestRequest) -> dict[str, Any]:
    text = payload.prompt.strip()
    if payload.protocol == ProtocolKind.OPENAI_CHAT:
        return {
            "model": payload.model_name,
            "messages": [{"role": "user", "content": text}],
            "max_tokens": 64,
            "stream": False,
        }
    if payload.protocol == ProtocolKind.OPENAI_RESPONSES:
        return {
            "model": payload.model_name,
            "input": text,
            "max_output_tokens": 64,
            "stream": False,
        }
    if payload.protocol == ProtocolKind.OPENAI_EMBEDDING:
        return {"model": payload.model_name, "input": text}
    if payload.protocol == ProtocolKind.OPENAI_IMAGE:
        return {
            "model": payload.model_name,
            "prompt": text,
            "n": 1,
            "size": "1024x1024",
        }
    if payload.protocol == ProtocolKind.RERANK:
        query, documents = _rerank_test_prompt(text)
        return {
            "model": payload.model_name,
            "query": query,
            "documents": documents,
            "top_n": min(3, len(documents)),
            "return_documents": True,
        }
    if payload.protocol == ProtocolKind.ANTHROPIC:
        return {
            "model": payload.model_name,
            "messages": [{"role": "user", "content": text}],
            "max_tokens": 64,
            "stream": False,
        }
    if payload.protocol == ProtocolKind.GEMINI:
        return {
            "model": payload.model_name,
            "contents": [{"role": "user", "parts": [{"text": text}]}],
            "generationConfig": {"maxOutputTokens": 64},
            "stream": False,
        }
    raise HTTPException(
        status_code=500, detail=f"Unsupported protocol={payload.protocol.value}"
    )


def _apply_site_model_probe_param_override(
    channel: ChannelConfig, body: dict[str, Any], payload: SiteModelTestRequest
) -> dict[str, Any] | SiteModelTestResult:
    try:
        prepared_body = _apply_param_override(channel, body)
    except UpstreamRequestError as exc:
        return SiteModelTestResult(
            success=False,
            status_code=exc.status_code,
            latency_ms=0,
            model_name=payload.model_name,
            credential_id=payload.credential.id,
            error_message=_format_channel_error(exc.detail),
        )
    if payload.protocol == ProtocolKind.RERANK:
        prepared_body.pop("stream", None)
    else:
        prepared_body["stream"] = False
    return prepared_body


def _rerank_test_prompt(text: str) -> tuple[str, list[str]]:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if len(lines) >= 2:
        return lines[0], lines[1:]
    query = lines[0] if lines else text.strip()
    return query, [query]
