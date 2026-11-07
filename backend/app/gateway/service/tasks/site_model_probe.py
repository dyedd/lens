from __future__ import annotations

import asyncio
from collections.abc import Sequence
from time import perf_counter
from typing import Any
from urllib.parse import urlsplit

import httpx
from fastapi import HTTPException, Request

from ....core.errors import LensError
from ....core.protocol_reachability import CHAT_PROTOCOLS
from ....core.upstream_rules import (
    RuleEvaluationError,
    apply_param_rules,
    param_rule_layers,
)
from ....models.channels import ChannelConfig
from ....models.protocols import ProtocolKind
from ....models.settings import RuntimeSettings
from ....models.site_model_test import (
    ModelTestMode,
    SiteModelTestRequest,
    SiteModelTestResult,
)
from ....models.upstream_rules import (
    HeaderRule,
    ParamOverrideRule,
    UpstreamParamOverrideConfig,
)
from ....plugins.contract import UpstreamCall
from ....plugins.runtime import apply_credential_hooks, system_run
from ...converters import spoke_for
from ...upstream_request import (
    UpstreamRequest,
    build_upstream_request,
    resolve_upstream_proxy_url,
)
from ..app_state import app_state
from ..payload_serialization import decode_content_bytes, decode_log_content_bytes
from ..proxy.routing_plan import elapsed_ms, gateway_timeout_scope
from ..runtime_types import GatewayTimeoutError, RequestDeadline
from ..upstream_support import (
    default_lens_user_agent,
    format_channel_error,
    format_http_response_error,
    format_transport_error,
    resolve_http_client,
)
from .site_model_output import (
    extract_site_model_output,
    extract_site_model_stream_output,
)


def _probe_debug(
    upstream: UpstreamRequest, response: httpx.Response | None = None
) -> dict[str, dict[str, object]]:
    path = urlsplit(upstream.url).path
    request_headers = {
        key: value
        for key, value in upstream.headers.items()
        if key.lower()
        in {
            "content-type",
            "accept",
            "anthropic-version",
            "user-agent",
            "originator",
            "version",
            "x-app",
            "x-stainless-lang",
        }
    }
    response_headers = (
        {
            key: value
            for key, value in response.headers.items()
            if key.lower() in {"content-type", "request-id", "x-request-id"}
        }
        if response is not None
        else {}
    )
    return {
        "request": {
            "method": upstream.method,
            "path": path,
            "headers": request_headers,
            "body": upstream.json_body,
        },
        "response": {
            "headers": response_headers,
            "body": (decode_log_content_bytes(response.content) or "")[:32768]
            if response is not None
            else "",
        },
    }


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
            }
        ],
        models=[],
        proxy_mode=payload.proxy_mode,
        channel_proxy=payload.channel_proxy,
        param_override=payload.param_override,
    )


async def run_site_model_probe(
    payload: SiteModelTestRequest,
    request: Request | None,
    *,
    channel: ChannelConfig | None = None,
    model_group_headers: Sequence[HeaderRule] = (),
    model_group_param_override: Sequence[ParamOverrideRule] = (),
    timeout_seconds: float | None = None,
) -> SiteModelTestResult:
    """Run a model probe, ending it early when `request` disconnects.

    `timeout_seconds` caps the wait below the configured first-token timeout.
    """
    if payload.test_mode == "codex" and payload.protocol not in {
        ProtocolKind.OPENAI_CHAT,
        ProtocolKind.OPENAI_RESPONSES,
    }:
        raise LensError(
            "Codex tests require OpenAI Chat or Responses protocol",
            status_code=400,
            error_type="invalid_request_error",
        )
    if payload.test_mode == "claude" and payload.protocol != ProtocolKind.ANTHROPIC:
        raise LensError(
            "Claude tests require Anthropic protocol",
            status_code=400,
            error_type="invalid_request_error",
        )
    channel = channel or _site_model_probe_channel(payload)
    runtime = await app_state.settings_repo.get_runtime_settings()
    if timeout_seconds is not None:
        runtime["first_token_timeout_seconds"] = min(
            float(runtime["first_token_timeout_seconds"]), timeout_seconds
        )
    body = _site_model_probe_body(payload)
    prepared_body = _apply_site_model_probe_param_override(
        channel,
        body,
        payload,
        runtime["upstream_param_override_config"],
        model_group_param_override=model_group_param_override,
    )
    if isinstance(prepared_body, SiteModelTestResult):
        return prepared_body
    return await _call_site_model_probe_for_request(
        request,
        channel=channel,
        body=prepared_body,
        model_name=payload.model_name,
        credential_id=payload.credential.id,
        test_mode=payload.test_mode,
        runtime=runtime,
        model_group_headers=model_group_headers,
    )


async def _call_site_model_probe_for_request(
    request: Request | None,
    *,
    channel: ChannelConfig,
    body: dict[str, Any],
    model_name: str,
    credential_id: str,
    test_mode: ModelTestMode,
    runtime: RuntimeSettings,
    model_group_headers: Sequence[HeaderRule],
) -> SiteModelTestResult:
    probe = _call_site_model_probe_channel(
        channel=channel,
        body=body,
        model_name=model_name,
        credential_id=credential_id,
        test_mode=test_mode,
        runtime=runtime,
        model_group_headers=model_group_headers,
    )
    if request is None:
        return await probe
    probe_task = asyncio.create_task(probe)
    disconnect_task = asyncio.create_task(_wait_for_request_disconnect(request))
    try:
        done, _ = await asyncio.wait(
            (probe_task, disconnect_task),
            return_when=asyncio.FIRST_COMPLETED,
        )
        if probe_task in done:
            return await probe_task
        await disconnect_task
        return SiteModelTestResult(
            success=False,
            model_name=model_name,
            credential_id=credential_id,
        )
    finally:
        for task in (probe_task, disconnect_task):
            if not task.done():
                task.cancel()
        await asyncio.gather(probe_task, disconnect_task, return_exceptions=True)


async def _wait_for_request_disconnect(request: Request) -> None:
    while True:
        message = await request.receive()
        if message["type"] == "http.disconnect":
            return


async def _call_site_model_probe_channel(
    *,
    channel: ChannelConfig,
    body: dict[str, Any],
    model_name: str,
    credential_id: str,
    test_mode: ModelTestMode,
    runtime: RuntimeSettings,
    model_group_headers: Sequence[HeaderRule],
) -> SiteModelTestResult:
    # shortcut: 固定 CLI 标识用于兼容性探测；上游要求新版特征时更新。
    client_headers: dict[str, str] = {}
    if test_mode == "codex":
        client_headers = {
            "user-agent": "codex_cli_rs/0.159.0",
            "originator": "codex_cli_rs",
            "version": "0.159.0",
            "accept": "application/json, text/event-stream",
        }
    elif test_mode == "claude":
        client_headers = {
            "user-agent": "claude-cli/2.1.90 (external, cli)",
            "x-app": "cli",
            "x-stainless-lang": "js",
            "accept": "application/json, text/event-stream",
        }
    headers_config = runtime["upstream_headers_config"].model_copy(
        update={
            "rules": [
                HeaderRule(name=name, action="override", value=value)
                for name, value in client_headers.items()
            ]
            + runtime["upstream_headers_config"].rules
        }
    )
    upstream = build_upstream_request(
        channel,
        body,
        credential_id=credential_id,
        user_agent=default_lens_user_agent(),
        upstream_headers_config=headers_config,
        model_group_headers=list(model_group_headers),
    )
    # 探测与真实请求一样经过凭据插件，测通的才是实际会发出的鉴权。
    hooked = await apply_credential_hooks(
        system_run(app_state.plugin_registry.hook_set(), channel.protocol.value),
        UpstreamCall(
            channel=channel,
            protocol=channel.protocol.value,
            url=upstream.url,
            headers=dict(upstream.headers),
            body=upstream.json_body,
            credential_id=credential_id,
            model_name=model_name,
        ),
    )
    upstream = UpstreamRequest(
        method=upstream.method,
        url=hooked.url,
        headers=hooked.headers,
        json_body=hooked.body,
    )
    proxy_url = resolve_upstream_proxy_url(channel, runtime["proxy_url"])
    client = resolve_http_client(proxy_url)

    started_at = perf_counter()
    deadline = RequestDeadline(
        started_at=started_at,
        first_token_timeout_seconds=float(runtime["first_token_timeout_seconds"]),
        stream_idle_timeout_seconds=float(runtime["stream_idle_timeout_seconds"]),
    )
    try:
        async with gateway_timeout_scope(
            deadline.first_token_remaining_seconds(),
            timeout_message=deadline.timeout_message(kind="first_token"),
        ):
            return await _run_site_model_probe_request(
                client=client,
                upstream=upstream,
                channel=channel,
                model_name=model_name,
                credential_id=credential_id,
                started_at=started_at,
            )
    except GatewayTimeoutError as exc:
        return SiteModelTestResult(
            success=False,
            status_code=504,
            latency_ms=elapsed_ms(started_at),
            model_name=model_name,
            credential_id=credential_id,
            error_message=str(exc),
            debug=_probe_debug(upstream),
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
        latency_ms = elapsed_ms(started_at)
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
                error_message=format_http_response_error(exc.response),
                debug=_probe_debug(upstream, exc.response),
            )
        content_type = (response.headers.get("content-type") or "").lower()
        if "text/event-stream" in content_type:
            raw_content = decode_content_bytes(response.content) or ""
            output_text = extract_site_model_stream_output(
                channel.protocol, raw_content
            )
        else:
            raw_payload = response.json()
            if not isinstance(raw_payload, dict):
                raise ValueError("Expected JSON object")
            if channel.protocol in CHAT_PROTOCOLS:
                spoke_for(channel.protocol).parse_response(raw_payload)
            output_text = extract_site_model_output(channel.protocol, raw_payload)
        return SiteModelTestResult(
            success=True,
            status_code=response.status_code,
            latency_ms=latency_ms,
            model_name=model_name,
            credential_id=credential_id,
            output_text=output_text,
            debug=_probe_debug(upstream, response),
        )
    except httpx.HTTPError as exc:
        return SiteModelTestResult(
            success=False,
            status_code=502,
            latency_ms=elapsed_ms(started_at),
            model_name=model_name,
            credential_id=credential_id,
            error_message=format_transport_error(exc, upstream.url),
            debug=_probe_debug(upstream),
        )
    except ValueError as exc:
        return SiteModelTestResult(
            success=False,
            status_code=502,
            latency_ms=elapsed_ms(started_at),
            model_name=model_name,
            credential_id=credential_id,
            error_message=f"Invalid upstream response: {exc}",
            debug=_probe_debug(upstream, response),
        )


def _site_model_probe_body(payload: SiteModelTestRequest) -> dict[str, Any]:
    text = "hi"
    if payload.protocol == ProtocolKind.OPENAI_CHAT:
        return {
            "model": payload.model_name,
            "messages": [{"role": "user", "content": text}],
            "stream": False,
        }
    if payload.protocol == ProtocolKind.OPENAI_RESPONSES:
        return {
            "model": payload.model_name,
            "input": [
                {
                    "type": "message",
                    "role": "user",
                    "content": [{"type": "input_text", "text": text}],
                }
            ],
            "max_output_tokens": 64,
            "stream": False,
        }
    if payload.protocol == ProtocolKind.OPENAI_EMBEDDING:
        return {"model": payload.model_name, "input": text}
    if payload.protocol == ProtocolKind.OPENAI_IMAGE:
        return {
            "model": payload.model_name,
            "prompt": "a dot",
            "n": 1,
            "size": "1024x1024",
        }
    if payload.protocol == ProtocolKind.RERANK:
        return {
            "model": payload.model_name,
            "query": text,
            "documents": [text],
            "top_n": 1,
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
    channel: ChannelConfig,
    body: dict[str, Any],
    payload: SiteModelTestRequest,
    global_config: UpstreamParamOverrideConfig | None,
    *,
    model_group_param_override: Sequence[ParamOverrideRule] = (),
) -> dict[str, Any] | SiteModelTestResult:
    try:
        prepared_body = apply_param_rules(
            body,
            param_rule_layers(
                global_config,
                channel_rules=channel.param_override,
                model_group_rules=model_group_param_override,
            ),
        )
    except RuleEvaluationError as exc:
        return SiteModelTestResult(
            success=False,
            status_code=400,
            latency_ms=0,
            model_name=payload.model_name,
            credential_id=payload.credential.id,
            error_message=format_channel_error(str(exc)),
        )
    if payload.protocol in {
        ProtocolKind.OPENAI_EMBEDDING,
        ProtocolKind.OPENAI_IMAGE,
        ProtocolKind.RERANK,
    }:
        prepared_body.pop("stream", None)
    else:
        prepared_body["stream"] = payload.test_mode != "direct"
    if (
        payload.test_mode == "codex"
        and payload.protocol == ProtocolKind.OPENAI_RESPONSES
    ):
        prepared_body["store"] = False
    return prepared_body
