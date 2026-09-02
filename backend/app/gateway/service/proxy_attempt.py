from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from dataclasses import dataclass, field
from time import perf_counter
from typing import Any

from fastapi import HTTPException, Response
from starlette.background import BackgroundTask

from ...core.upstream_rules import (
    RuleEvaluationError,
    apply_param_rules,
    param_rule_layers,
)
from ...models.channels import ChannelConfig
from ...models.protocols import ProtocolKind, RequestLogLifecycleStatus
from ..converters import convert_request
from ..router import RouteTarget
from ..router.cooldown import ErrorCategory, classify_error
from .app_state import app_state
from .error_responses import _protocol_error_response
from .payload_serialization import _dump_log_json
from .proxy_upstream import (
    _call_channel,
    _client_stream_includes_usage,
    _prepare_channel_request,
)
from .request_logger import _RequestLogger
from .routing_plan import _elapsed_ms
from .routing_request import (
    _apply_deepseek_thinking_compat,
    _apply_glm_chat_reasoning_compat,
    _apply_reasoning_intent,
    _extract_request_reasoning_effort,
    _is_deepseek_thinking_target,
)
from .runtime_types import (
    AttemptLog,
    RoutingPlan,
    StreamCapture,
    UpstreamRequestError,
    UpstreamResult,
    _attempt_logs_to_dicts,
    _RequestDeadline,
)
from .streaming.stream_logging import (
    _record_stream_request_log,
    _stream_log_outcome,
)
from .upstream_support import (
    _effective_user_agent_from_headers,
    _format_channel_error,
)


@dataclass(slots=True)
class AttemptRequest:
    """Per-request facts a failover loop passes to every target attempt."""

    protocol: ProtocolKind
    body: dict[str, Any]
    runtime: dict[str, Any]
    upstream_user_agent: str
    inbound_headers: Mapping[str, str] | None = None
    path_suffix: str | None = None
    multipart_files: list[tuple[str, tuple[str, bytes, str]]] | None = None


@dataclass(slots=True)
class FailureLedger:
    """Accumulate failed-target diagnostics and select the final client error."""

    errors: list[str] = field(default_factory=list)
    status_codes: list[int | None] = field(default_factory=list)

    def record(self, message: str, status_code: int | None) -> None:
        self.errors.append(message)
        self.status_codes.append(status_code)

    def final_failure(self) -> tuple[int, str, str]:
        return _final_upstream_failure(self.errors, self.status_codes)


@dataclass(slots=True)
class _AttemptRun:
    """State one target attempt accumulates from start to logged outcome."""

    request: AttemptRequest
    plan: RoutingPlan
    target: RouteTarget
    deadline: _RequestDeadline
    log_ctx: _RequestLogger
    failures: FailureLedger
    attempt: AttemptLog
    attempt_started_at: float
    effective_user_agent: str

    @property
    def log_body_enabled(self) -> bool:
        return bool(self.request.runtime["relay_log_body_enabled"])


async def run_attempt(
    *,
    request: AttemptRequest,
    plan: RoutingPlan,
    target: RouteTarget,
    deadline: _RequestDeadline,
    log_ctx: _RequestLogger,
    failures: FailureLedger,
) -> Response | None:
    """Run one upstream target. None hands the failover loop the next target."""
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
    run = _AttemptRun(
        request=request,
        plan=plan,
        target=target,
        deadline=deadline,
        log_ctx=log_ctx,
        failures=failures,
        attempt=attempt,
        attempt_started_at=attempt_started_at,
        effective_user_agent=request.upstream_user_agent,
    )

    if request.protocol != channel.protocol:
        try:
            upstream_body = convert_request(
                request.protocol,
                channel.protocol,
                request.body,
                target.model_name,
                preserve_reasoning=_is_deepseek_thinking_target(
                    channel, target.model_name
                ),
            )
        except ValueError as exc:
            return await _record_target_failure(
                run,
                UpstreamRequestError(
                    status_code=400,
                    detail=str(exc),
                    router_status_code=None,
                    skip_route_failure=True,
                ),
                upstream_body=request.body,
            )
    else:
        upstream_body = deepcopy(request.body)
        if target.model_name:
            upstream_body["model"] = target.model_name
    try:
        upstream_body = apply_param_rules(
            upstream_body,
            param_rule_layers(
                request.runtime["upstream_param_override_config"],
                channel_rules=channel.param_override,
                model_group_rules=(
                    plan.requested_group.param_override
                    if plan.requested_group is not None
                    else ()
                ),
            ),
        )
        upstream_body = _apply_deepseek_thinking_compat(channel, upstream_body)
        upstream_body = _apply_glm_chat_reasoning_compat(
            channel, upstream_body, request.body
        )
        upstream_body = _apply_reasoning_intent(
            channel, upstream_body, plan.parsed_model
        )
    except RuleEvaluationError as exc:
        return await _record_target_failure(
            run,
            UpstreamRequestError(
                status_code=400,
                detail=str(exc),
                router_status_code=None,
            ),
            upstream_body=upstream_body,
        )
    except UpstreamRequestError as exc:
        return await _record_target_failure(run, exc, upstream_body=upstream_body)
    if request.protocol in {ProtocolKind.OPENAI_EMBEDDING, ProtocolKind.RERANK}:
        upstream_body.pop("stream", None)

    log_body_enabled = run.log_body_enabled
    reasoning_effort = _extract_request_reasoning_effort(request.body, upstream_body)
    try:
        upstream, body_bytes, upstream_request_content = _prepare_channel_request(
            channel,
            upstream_body,
            credential_id=target.credential_id,
            user_agent=request.upstream_user_agent,
            forwarded_headers=request.inbound_headers,
            upstream_headers_config=request.runtime["upstream_headers_config"],
            model_group_headers=(
                plan.requested_group.headers
                if plan.requested_group is not None
                else None
            ),
            log_body_enabled=log_body_enabled,
            max_request_body_bytes=int(request.runtime["max_request_body_bytes"]),
            path_suffix=request.path_suffix,
            multipart_files=request.multipart_files,
        )
        run.effective_user_agent = _effective_user_agent_from_headers(
            upstream.headers, request.upstream_user_agent
        )
    except UpstreamRequestError as exc:
        return await _record_target_failure(
            run,
            exc,
            upstream_body=upstream_body,
            request_content=exc.request_content,
        )
    except HTTPException as exc:
        return await _record_target_failure(
            run,
            UpstreamRequestError(
                status_code=exc.status_code,
                detail=exc.detail,
                router_status_code=exc.status_code,
                skip_route_failure=True,
            ),
            upstream_body=upstream_body,
        )
    attempt.reasoning_effort = reasoning_effort
    await log_ctx.connecting(
        is_stream=bool(upstream_body.get("stream")),
        upstream_model_name=target.model_name,
        channel=channel,
        user_agent=run.effective_user_agent,
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
            client_protocol=request.protocol,
            include_stream_usage=_client_stream_includes_usage(
                request.protocol, request.body
            ),
            log_body_enabled=log_body_enabled,
            deadline=deadline,
            global_proxy_url=str(request.runtime["proxy_url"]),
        )
    except UpstreamRequestError as exc:
        return await _record_target_failure(
            run,
            exc,
            upstream_body=upstream_body,
            request_content=upstream_request_content,
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
        await log_ctx.streaming(
            upstream_model_name=result.upstream_model_name,
            status_code=result.status_code,
            first_token_latency_ms=first_token_latency_ms,
            request_content=merged_request_content,
            channel=channel,
            user_agent=run.effective_user_agent,
            rate_multiplier=target.rate_multiplier,
        )
        result.response.background = BackgroundTask(
            _finalize_stream_request,
            log_ctx=log_ctx,
            channel=channel,
            result=result,
            attempts=_attempt_logs_to_dicts(log_ctx.attempts),
        )
        return result.response
    await log_ctx.succeeded(
        upstream_model_name=result.upstream_model_name,
        status_code=result.status_code,
        first_token_latency_ms=result.first_token_latency_ms,
        request_content=merged_request_content,
        response_content=result.response_content,
        result=result,
        channel=channel,
        user_agent=run.effective_user_agent,
        rate_multiplier=target.rate_multiplier,
    )
    return result.response


async def _finalize_stream_request(
    *,
    log_ctx: _RequestLogger,
    channel: ChannelConfig,
    result: UpstreamResult,
    attempts: list[dict[str, Any]],
) -> None:
    """Background close-out of a streamed attempt: route health, then the log row."""
    outcome = _stream_log_outcome(result, result.stream_capture)
    await _record_stream_route_health(
        channel=channel,
        capture=result.stream_capture,
        capture_issue=outcome.capture_issue,
        lifecycle_status=outcome.lifecycle_status,
        attempts=attempts,
    )
    await _record_stream_request_log(
        log_ctx=log_ctx,
        channel=channel,
        result=result,
        attempts=attempts,
        outcome=outcome,
    )


async def _record_stream_route_health(
    *,
    channel: ChannelConfig,
    capture: StreamCapture | None,
    capture_issue: str | None,
    lifecycle_status: RequestLogLifecycleStatus,
    attempts: list[dict[str, Any]],
) -> None:
    credential_id, model_name = _last_attempt_target(attempts)
    if lifecycle_status == RequestLogLifecycleStatus.CANCELLED:
        return
    if capture_issue is None:
        app_state.router.record_success(
            channel.id,
            credential_id=credential_id,
            model_name=model_name,
            started_revision=(
                capture.route_started_revision
                if capture is not None and capture.route_started_revision >= 0
                else None
            ),
        )
        return
    if capture is not None and capture.skip_route_failure:
        return

    status_code = capture.error_status_code if capture is not None else None
    category = capture.error_category if capture is not None else None
    cooldown_seconds = capture.error_cooldown_seconds if capture is not None else None
    if category is None:
        classification = classify_error(status_code)
        if classification is not None:
            category, _, classified_cooldown = classification
            cooldown_seconds = cooldown_seconds or classified_cooldown
    category = category or ErrorCategory.SERVER
    app_state.router.record_failure(
        channel.id,
        _format_channel_error(capture_issue),
        category=category,
        cooldown_seconds=cooldown_seconds,
        credential_id=credential_id,
        model_name=model_name,
    )


def _last_attempt_target(
    attempts: list[dict[str, Any]],
) -> tuple[str | None, str | None]:
    if not attempts:
        return None, None
    attempt = attempts[-1]
    credential_id = attempt.get("credential_id")
    model_name = attempt.get("model_name")
    return (
        credential_id if isinstance(credential_id, str) and credential_id else None,
        model_name if isinstance(model_name, str) and model_name else None,
    )


async def _record_target_failure(
    run: _AttemptRun,
    exc: UpstreamRequestError,
    *,
    upstream_body: dict[str, Any],
    request_content: str | None = None,
) -> Response | None:
    """Log the failed attempt, feed cooldowns, and honor stop-fallback."""
    channel = run.target.channel
    message = _format_channel_error(exc.detail)
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
            credential_id=run.target.credential_id,
            model_name=run.target.model_name,
            cooldown_seconds=exc.router_cooldown_seconds,
        )
    run.failures.record(message, exc.status_code)
    run.attempt.status_code = exc.status_code
    run.attempt.duration_ms = _elapsed_ms(run.attempt_started_at)
    run.attempt.error_message = message
    run.attempt.reasoning_effort = _extract_request_reasoning_effort(
        run.log_ctx.body, upstream_body
    )
    await run.log_ctx.failed(
        status_code=exc.status_code,
        error_message=message,
        is_stream=bool(upstream_body.get("stream")),
        channel=channel,
        user_agent=run.effective_user_agent,
        rate_multiplier=run.target.rate_multiplier,
        request_content=(
            exc.request_content
            if exc.request_content is not None
            else (
                request_content
                if request_content is not None
                else (_dump_log_json(upstream_body) if run.log_body_enabled else None)
            )
        ),
    )
    if exc.stop_fallback:
        return _protocol_error_response(
            protocol=run.log_ctx.protocol,
            status_code=exc.status_code,
            error_type=exc.error_type,
            message=message,
        )
    return None


def _final_upstream_failure(
    errors: list[str], failure_status_codes: list[int | None]
) -> tuple[int, str, str]:
    for error, status_code in zip(errors, failure_status_codes, strict=False):
        if _is_request_too_large_error(status_code, error):
            return 413, "request_too_large", error
    if failure_status_codes and all(
        status_code == 504 for status_code in failure_status_codes
    ):
        return 504, "gateway_timeout", "All upstream channels timed out"
    if errors:
        return 502, "upstream_error", errors[0]
    return 502, "upstream_error", "All upstream channels failed"


def _is_request_too_large_error(status_code: int | None, message: str) -> bool:
    if status_code != 413:
        return False
    lower_message = message.lower()
    return (
        "request body exceeds" in lower_message
        or "request_too_large" in lower_message
        or "too large" in lower_message
        or "exceeds lens limit" in lower_message
    )
