from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from time import perf_counter
from typing import Any

from fastapi import HTTPException, Response
from starlette.background import BackgroundTask

from ...models.protocols import ProtocolKind, RequestLogLifecycleStatus
from ..converters import convert_request
from ..router import RouteTarget
from ..router.cooldown import classify_error
from .app_state import app_state
from .error_responses import _protocol_error_response
from .payload_serialization import _dump_log_json
from .proxy_upstream import (
    _call_channel,
    _client_stream_includes_usage,
    _prepare_channel_request,
)
from .request_logger import _RequestLogger
from .routing_plan import (
    _elapsed_ms,
    _is_request_too_large_error,
)
from .routing_request import (
    _apply_deepseek_thinking_compat,
    _apply_glm_chat_reasoning_compat,
    _apply_global_param_override,
    _apply_param_override,
    _apply_reasoning_intent,
    _extract_request_reasoning_effort,
    _is_deepseek_thinking_target,
)
from .runtime_types import (
    AttemptLog,
    RoutingPlan,
    UpstreamRequestError,
    _attempt_logs_to_dicts,
    _RequestDeadline,
)
from .stream_logging import _record_stream_request_log
from .upstream_support import (
    _effective_user_agent_from_headers,
    _format_channel_error,
)


async def _record_target_failure(
    *,
    target: RouteTarget,
    runtime: dict[str, Any],
    log_ctx: _RequestLogger,
    plan: RoutingPlan,
    errors: list[str],
    failure_status_codes: list[int | None],
    attempt_started_at: float,
    effective_user_agent: str,
    upstream_body: dict[str, Any],
    exc: UpstreamRequestError,
    attempt: AttemptLog,
    request_content: str | None = None,
) -> Response | None:
    channel = target.channel
    message = _format_channel_error(exc.detail)
    log_body_enabled = bool(runtime["relay_log_body_enabled"])
    category = exc.router_error_category
    scope = exc.router_error_scope
    if category is None:
        classification = classify_error(exc.router_status_code)
        if classification is not None:
            category, scope, _ = classification
    if (
        category is not None
        and not exc.skip_route_failure
        and not _is_request_too_large_error(exc.status_code, message)
    ):
        app_state.router.record_failure(
            channel.id,
            message,
            category=category,
            scope=scope,
            credential_id=target.credential_id,
            model_name=target.model_name,
            cooldown_seconds=exc.router_cooldown_seconds,
        )
    errors.append(message)
    failure_status_codes.append(exc.status_code)
    reasoning_effort = _extract_request_reasoning_effort(log_ctx.body, upstream_body)
    attempt.status_code = exc.status_code
    attempt.duration_ms = _elapsed_ms(attempt_started_at)
    attempt.error_message = message
    attempt.reasoning_effort = reasoning_effort
    await log_ctx.update(
        requested_group_name=plan.requested_group_name,
        resolved_group_name=plan.resolved_group_name,
        upstream_model_name=None,
        channel=channel,
        user_agent=effective_user_agent,
        lifecycle_status=RequestLogLifecycleStatus.FAILED,
        status_code=exc.status_code,
        success=False,
        is_stream=bool(upstream_body.get("stream")),
        rate_multiplier=target.rate_multiplier,
        request_content=(
            exc.request_content
            if exc.request_content is not None
            else (
                request_content
                if request_content is not None
                else (_dump_log_json(upstream_body) if log_body_enabled else None)
            )
        ),
        error_message=message,
    )
    if exc.stop_fallback:
        return _protocol_error_response(
            protocol=log_ctx.protocol,
            status_code=exc.status_code,
            error_type=exc.error_type,
            message=message,
        )
    return None


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
    route_started_revision = app_state.router.current_failure_revision()
    attempt = AttemptLog(
        channel_id=channel.id,
        channel_name=channel.name,
        credential_id=target.credential_id,
        credential_name=target.credential_name or "",
        model_name=target.model_name,
        status_code=None,
        success=False,
        duration_ms=0,
    )
    log_ctx.attempts.append(attempt)

    if protocol != channel.protocol:
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
                    skip_route_failure=True,
                ),
                attempt=attempt,
            )
    else:
        upstream_body = deepcopy(body)
        if target.model_name:
            upstream_body["model"] = target.model_name
    try:
        upstream_body = _apply_global_param_override(
            upstream_body,
            runtime["upstream_param_override_config"],
        )
        upstream_body = _apply_param_override(
            upstream_body,
            channel.param_override,
            source=f"channel {channel.name}",
        )
        if plan.requested_group is not None:
            upstream_body = _apply_param_override(
                upstream_body,
                plan.requested_group.param_override,
                source=f"model group {plan.requested_group.name}",
            )
        upstream_body = _apply_deepseek_thinking_compat(channel, upstream_body)
        upstream_body = _apply_glm_chat_reasoning_compat(channel, upstream_body, body)
        upstream_body = _apply_reasoning_intent(
            channel, upstream_body, plan.parsed_model
        )
    except UpstreamRequestError as exc:
        return await _record_target_failure(
            target=target,
            runtime=runtime,
            log_ctx=log_ctx,
            plan=plan,
            errors=errors,
            failure_status_codes=failure_status_codes,
            attempt_started_at=attempt_started_at,
            effective_user_agent=upstream_user_agent,
            upstream_body=upstream_body,
            exc=exc,
            attempt=attempt,
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
            model_group_headers=(
                plan.requested_group.headers
                if plan.requested_group is not None
                else None
            ),
            log_body_enabled=log_body_enabled,
            max_request_body_bytes=int(runtime["max_request_body_bytes"]),
            path_suffix=path_suffix,
            multipart_files=multipart_files,
        )
        effective_user_agent = _effective_user_agent_from_headers(
            upstream.headers, upstream_user_agent
        )
    except UpstreamRequestError as exc:
        return await _record_target_failure(
            target=target,
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
            attempt=attempt,
        )
    except HTTPException as exc:
        return await _record_target_failure(
            target=target,
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
                skip_route_failure=True,
            ),
            attempt=attempt,
        )
    attempt.reasoning_effort = reasoning_effort
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
        rate_multiplier=target.rate_multiplier,
        request_content=upstream_request_content,
    )
    try:
        result = await _call_channel(
            channel,
            upstream_body,
            upstream,
            body_bytes,
            upstream_request_content,
            pricing_group_name=plan.resolved_group_name,
            rate_multiplier=target.rate_multiplier,
            client_protocol=protocol,
            include_stream_usage=_client_stream_includes_usage(protocol, body),
            log_body_enabled=log_body_enabled,
            deadline=deadline,
            global_proxy_url=str(runtime["proxy_url"]),
        )
    except UpstreamRequestError as exc:
        return await _record_target_failure(
            target=target,
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
            attempt=attempt,
        )

    attempt.status_code = result.status_code
    attempt.success = True
    attempt.duration_ms = _elapsed_ms(attempt_started_at)

    if not result.is_stream:
        app_state.router.record_success(
            channel.id,
            credential_id=target.credential_id,
            model_name=target.model_name,
            started_revision=route_started_revision,
        )

    merged_request_content = result.request_content or upstream_request_content
    if result.is_stream:
        if result.stream_capture is not None:
            result.stream_capture.request_log_id = log_ctx.request_log_id
            result.stream_capture.stream_started_at = log_ctx.started_at
            result.stream_capture.route_started_revision = route_started_revision
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
            rate_multiplier=target.rate_multiplier,
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
            rate_multiplier=target.rate_multiplier,
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
        rate_multiplier=target.rate_multiplier,
        first_token_latency_ms=result.first_token_latency_ms,
        request_content=merged_request_content,
        response_content=result.response_content,
        result=result,
    )
    return result.response
