from __future__ import annotations

import asyncio
from time import perf_counter

from fastapi import HTTPException
from starlette.background import BackgroundTask

from ...core.config import settings
from ...models import ProtocolKind, RequestLogLifecycleStatus
from ..converters import convert_request, needs_conversion
from .runtime_types import (
    AttemptLog,
    UpstreamRequestError,
    _RequestDeadline,
    _attempt_logs_to_dicts,
)
from .app_state import app_state
from .auth import _gateway_key_allows_model
from .errors import (
    _apply_router_runtime_settings,
    _protocol_error_response,
)
from .upstream_support import (
    _default_lens_user_agent,
    _is_generic_user_agent,
    _normalize_user_agent,
)
from .payload_serialization import _dump_log_json
from .proxy_upstream import (
    _call_channel,
    _prepare_channel_request,
    _record_target_failure,
)
from .request_logger import _RequestLogger
from .routing_plan import (
    _apply_deepseek_thinking_compat,
    _apply_global_param_override,
    _apply_param_override,
    _elapsed_ms,
    _extract_request_reasoning_effort,
    _final_upstream_failure,
    _is_deepseek_thinking_target,
    _prepare_upstream_body,
    _resolve_routing_plan,
)
from .stream_logging import (
    _record_stream_request_log,
)


async def _try_target(
    *,
    target: RouteTarget,
    protocol: ProtocolKind,
    body: dict[str, Any],
    runtime: dict[str, Any],
    upstream_user_agent: str,
    inbound_headers: Mapping[str, str] | None,
    plan: RoutingPlan,
    log_ctx: _RequestLogger,
    errors: list[str],
    failure_status_codes: list[int | None],
    deadline: _RequestDeadline,
    path_suffix: str | None = None,
    multipart_files: list[tuple[str, tuple[str, bytes, str]]] | None = None,
) -> Response | None:
    channel = target.channel
    attempt_started_at = perf_counter()

    if needs_conversion(protocol, channel.protocol):
        try:
            upstream_body = convert_request(
                protocol,
                channel.protocol,
                body,
                target.model_name,
                preserve_reasoning=_is_deepseek_thinking_target(
                    channel, target.model_name
                ),
            )
        except ValueError as exc:
            return await _record_target_failure(
                target=target,
                channel=channel,
                runtime=runtime,
                log_ctx=log_ctx,
                plan=plan,
                errors=errors,
                failure_status_codes=failure_status_codes,
                attempt_started_at=attempt_started_at,
                effective_user_agent=upstream_user_agent,
                upstream_body=body,
                exc=UpstreamRequestError(
                    status_code=400,
                    detail=str(exc),
                    router_status_code=None,
                ),
            )
    else:
        upstream_body = _prepare_upstream_body(protocol, body, target.model_name)
    try:
        upstream_body = _apply_global_param_override(
            upstream_body,
            runtime["upstream_param_override_config"],
            target.model_name or "",
        )
        upstream_body = _apply_param_override(channel, upstream_body)
        upstream_body = _apply_deepseek_thinking_compat(channel, upstream_body)
    except UpstreamRequestError as exc:
        return await _record_target_failure(
            target=target,
            channel=channel,
            runtime=runtime,
            log_ctx=log_ctx,
            plan=plan,
            errors=errors,
            failure_status_codes=failure_status_codes,
            attempt_started_at=attempt_started_at,
            effective_user_agent=upstream_user_agent,
            upstream_body=upstream_body,
            exc=exc,
        )
    if protocol in {ProtocolKind.OPENAI_EMBEDDING, ProtocolKind.RERANK}:
        upstream_body.pop("stream", None)

    log_body_enabled = bool(runtime["relay_log_body_enabled"])
    reasoning_effort = _extract_request_reasoning_effort(body, upstream_body)
    try:
        upstream, body_bytes, upstream_request_content = _prepare_channel_request(
            channel,
            upstream_body,
            credential_id=target.credential_id,
            user_agent=upstream_user_agent,
            forwarded_headers=inbound_headers,
            upstream_headers_config=runtime["upstream_headers_config"],
            log_body_enabled=log_body_enabled,
            path_suffix=path_suffix,
            multipart_files=multipart_files,
        )
        effective_user_agent = _effective_user_agent_from_headers(
            upstream.headers, upstream_user_agent
        )
    except UpstreamRequestError as exc:
        return await _record_target_failure(
            target=target,
            channel=channel,
            runtime=runtime,
            log_ctx=log_ctx,
            plan=plan,
            errors=errors,
            failure_status_codes=failure_status_codes,
            attempt_started_at=attempt_started_at,
            effective_user_agent=upstream_user_agent,
            upstream_body=upstream_body,
            request_content=exc.request_content,
            exc=exc,
        )
    except HTTPException as exc:
        return await _record_target_failure(
            target=target,
            channel=channel,
            runtime=runtime,
            log_ctx=log_ctx,
            plan=plan,
            errors=errors,
            failure_status_codes=failure_status_codes,
            attempt_started_at=attempt_started_at,
            effective_user_agent=upstream_user_agent,
            upstream_body=upstream_body,
            exc=UpstreamRequestError(
                status_code=exc.status_code,
                detail=exc.detail,
                router_status_code=exc.status_code,
            ),
        )
    await log_ctx.update(
        requested_group_name=plan.requested_group_name,
        resolved_group_name=plan.resolved_group_name,
        upstream_model_name=target.model_name,
        channel=channel,
        user_agent=effective_user_agent,
        lifecycle_status=RequestLogLifecycleStatus.CONNECTING,
        status_code=None,
        success=False,
        is_stream=bool(upstream_body.get("stream")),
        request_content=upstream_request_content,
    )
    try:
        result = await _call_channel(
            channel,
            upstream_body,
            upstream,
            body_bytes,
            upstream_request_content,
            credential_id=target.credential_id,
            pricing_group_name=plan.resolved_group_name,
            client_protocol=protocol,
            log_body_enabled=log_body_enabled,
            deadline=deadline,
            global_proxy_url=str(runtime["proxy_url"]),
        )
    except UpstreamRequestError as exc:
        return await _record_target_failure(
            target=target,
            channel=channel,
            runtime=runtime,
            log_ctx=log_ctx,
            plan=plan,
            errors=errors,
            failure_status_codes=failure_status_codes,
            attempt_started_at=attempt_started_at,
            effective_user_agent=effective_user_agent,
            upstream_body=upstream_body,
            request_content=upstream_request_content,
            exc=exc,
        )

    log_ctx.attempts.append(
        AttemptLog(
            channel_id=channel.id,
            channel_name=channel.name,
            credential_id=target.credential_id,
            credential_name=target.credential_name or "",
            model_name=target.model_name,
            status_code=result.status_code,
            success=True,
            duration_ms=_elapsed_ms(attempt_started_at),
            reasoning_effort=reasoning_effort,
        )
    )

    merged_request_content = result.request_content or upstream_request_content
    if result.is_stream:
        if result.stream_capture is not None:
            result.stream_capture.request_log_id = log_ctx.request_log_id
            result.stream_capture.stream_started_at = log_ctx.started_at
        first_token_latency_ms = (
            result.stream_capture.first_token_latency_ms
            if result.stream_capture is not None
            else result.first_token_latency_ms
        )
        await log_ctx.update(
            requested_group_name=plan.requested_group_name,
            resolved_group_name=plan.resolved_group_name,
            upstream_model_name=result.upstream_model_name,
            channel=channel,
            user_agent=effective_user_agent,
            lifecycle_status=RequestLogLifecycleStatus.STREAMING,
            status_code=result.status_code,
            success=False,
            is_stream=True,
            first_token_latency_ms=first_token_latency_ms,
            request_content=merged_request_content,
        )
        result.response.background = BackgroundTask(
            _record_stream_request_log,
            request_log_id=log_ctx.request_log_id,
            protocol=protocol,
            requested_group_name=plan.requested_group_name,
            resolved_group_name=plan.resolved_group_name,
            channel=channel,
            gateway_key=log_ctx.gateway_key,
            user_agent=effective_user_agent,
            started_at=log_ctx.started_at,
            result=result,
            attempts=_attempt_logs_to_dicts(log_ctx.attempts),
        )
        return result.response
    await log_ctx.update(
        requested_group_name=plan.requested_group_name,
        resolved_group_name=plan.resolved_group_name,
        upstream_model_name=result.upstream_model_name,
        channel=channel,
        user_agent=effective_user_agent,
        lifecycle_status=RequestLogLifecycleStatus.SUCCEEDED,
        status_code=result.status_code,
        success=True,
        is_stream=result.is_stream,
        first_token_latency_ms=result.first_token_latency_ms,
        request_content=merged_request_content,
        response_content=result.response_content,
        result=result,
    )
    return result.response
