from __future__ import annotations

from collections.abc import Mapping
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
from ..converters import (
    convert_request,
    needs_protocol_conversion,
    strip_foreign_reasoning,
)
from ..converters.responses_common import lift_additional_tools
from ..router import RouteTarget, TargetKey
from ..router.cooldown import ErrorCategory, classify_error, default_scope
from ..router.failover import FailurePolicy, RetryAction, policy_for
from .app_state import app_state
from .compat import (
    apply_deepseek_thinking_compat,
    apply_glm_chat_reasoning_compat,
    is_deepseek_thinking_target,
)
from .error_responses import protocol_error_response
from .payload_serialization import dump_log_json
from .proxy_upstream import (
    execute_upstream_request,
    prepare_upstream_request,
    request_includes_stream_usage,
)
from .request_logger import RequestLogger
from .routing_plan import elapsed_ms
from .routing_request import apply_reasoning_intent, extract_request_reasoning_effort
from .runtime_types import (
    AttemptLog,
    RequestDeadline,
    RoutingPlan,
    StreamCapture,
    UpstreamRequestError,
    UpstreamResult,
    attempt_logs_to_dicts,
)
from .streaming.logging import (
    record_stream_request_log,
    stream_log_outcome,
)
from .upstream_support import (
    effective_user_agent_from_headers,
    format_channel_error,
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
class LogFailure:
    status_code: int
    error_message: str
    is_stream: bool
    requested_group_name: str | None
    resolved_group_name: str | None
    channel: ChannelConfig | None = None
    user_agent: str | None = None
    rate_multiplier: float | None = None
    request_content: str | None = None

    async def write(self, log_ctx: RequestLogger) -> None:
        log_ctx.plan_route(
            requested_group_name=self.requested_group_name,
            resolved_group_name=self.resolved_group_name,
        )
        await log_ctx.record_failure(
            status_code=self.status_code,
            error_message=self.error_message,
            is_stream=self.is_stream,
            channel=self.channel,
            user_agent=self.user_agent,
            rate_multiplier=self.rate_multiplier,
            request_content=self.request_content,
        )


@dataclass(slots=True)
class FailureLedger:
    """Accumulate failed-target diagnostics and select the final client error."""

    errors: list[str] = field(default_factory=list)
    status_codes: list[int | None] = field(default_factory=list)
    error_types: list[str] = field(default_factory=list)
    last_log_failure: LogFailure | None = None
    last_action: RetryAction | None = None
    retry_after_seconds: float | None = None
    cooled_waits: dict[TargetKey, float] = field(default_factory=dict)

    def record(
        self,
        message: str,
        status_code: int | None,
        error_type: str = "upstream_error",
        *,
        retry_after_seconds: float | None = None,
    ) -> None:
        self.errors.append(message)
        self.status_codes.append(status_code)
        self.error_types.append(error_type)
        if retry_after_seconds is not None:
            self.retry_after_seconds = (
                retry_after_seconds
                if self.retry_after_seconds is None
                else min(self.retry_after_seconds, retry_after_seconds)
            )

    def final_failure(self) -> tuple[int, str, str]:
        return _final_upstream_failure(self.errors, self.status_codes, self.error_types)


@dataclass(slots=True)
class _AttemptRun:
    """State one target attempt accumulates from start to logged outcome."""

    request: AttemptRequest
    plan: RoutingPlan
    target: RouteTarget
    deadline: RequestDeadline
    log_ctx: RequestLogger
    failures: FailureLedger
    attempt: AttemptLog
    attempt_started_at: float
    route_started_revision: int
    effective_user_agent: str
    was_probe: bool = False

    @property
    def log_body_enabled(self) -> bool:
        return bool(self.request.runtime["relay_log_body_enabled"])


@dataclass(slots=True)
class _PreparedAttempt:
    channel: ChannelConfig
    upstream_body: dict[str, Any]
    upstream: Any
    body_bytes: bytes
    request_content: str | None
    reasoning_effort: str | None


async def _prepare_attempt(run: _AttemptRun) -> _PreparedAttempt | Response | None:
    request = run.request
    plan = run.plan
    target = run.target
    channel = target.channel

    if needs_protocol_conversion(request.protocol, channel.protocol):
        try:
            upstream_body = convert_request(
                request.protocol,
                channel.protocol,
                request.body,
                target.model_name,
                preserve_reasoning=is_deepseek_thinking_target(
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
                    error_type="bad_request",
                    skip_route_failure=True,
                ),
                upstream_body=request.body,
            )
    else:
        upstream_body = dict(request.body)
        if target.model_name:
            upstream_body["model"] = target.model_name
        if channel.protocol == ProtocolKind.OPENAI_RESPONSES:
            # Codex >= 0.149 nests tool definitions in `input` items of type
            # `additional_tools`; not every Responses upstream accepts that
            # encoding, while all of them read the top-level `tools` array.
            upstream_body = lift_additional_tools(upstream_body)
        # A history can carry reasoning state this upstream cannot read.
        upstream_body = strip_foreign_reasoning(
            upstream_body, channel.protocol, target.model_name
        )

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
        upstream_body = apply_deepseek_thinking_compat(channel, upstream_body)
        upstream_body = apply_glm_chat_reasoning_compat(
            channel, upstream_body, request.body
        )
        upstream_body = apply_reasoning_intent(
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

    reasoning_effort = extract_request_reasoning_effort(request.body, upstream_body)
    try:
        upstream, body_bytes, upstream_request_content = await prepare_upstream_request(
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
            log_body_enabled=run.log_body_enabled,
            max_request_body_bytes=int(request.runtime["max_request_body_bytes"]),
            path_suffix=request.path_suffix,
            multipart_files=request.multipart_files,
        )
        run.effective_user_agent = effective_user_agent_from_headers(
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

    return _PreparedAttempt(
        channel=channel,
        upstream_body=upstream_body,
        upstream=upstream,
        body_bytes=body_bytes,
        request_content=upstream_request_content,
        reasoning_effort=reasoning_effort,
    )


async def _send_attempt(
    run: _AttemptRun, prepared: _PreparedAttempt
) -> UpstreamResult | Response | None:
    request = run.request
    plan = run.plan
    target = run.target
    channel = prepared.channel
    run.attempt.reasoning_effort = prepared.reasoning_effort
    await run.log_ctx.record_connecting(
        is_stream=bool(prepared.upstream_body.get("stream")),
        upstream_model_name=target.model_name,
        channel=channel,
        user_agent=run.effective_user_agent,
        rate_multiplier=target.rate_multiplier,
        request_content=prepared.request_content,
    )
    try:
        return await execute_upstream_request(
            channel,
            prepared.upstream_body,
            prepared.upstream,
            prepared.body_bytes,
            prepared.request_content,
            pricing_group_name=plan.resolved_group_name,
            rate_multiplier=target.rate_multiplier,
            client_protocol=request.protocol,
            include_stream_usage=request_includes_stream_usage(
                request.protocol, request.body
            ),
            log_body_enabled=run.log_body_enabled,
            deadline=run.deadline,
            global_proxy_url=str(request.runtime["proxy_url"]),
        )
    except UpstreamRequestError as exc:
        return await _record_target_failure(
            run,
            exc,
            upstream_body=prepared.upstream_body,
            request_content=prepared.request_content,
        )


async def _finish_attempt(
    run: _AttemptRun, prepared: _PreparedAttempt, result: UpstreamResult
) -> Response:
    channel = prepared.channel
    target = run.target
    run.attempt.status_code = result.status_code
    run.attempt.success = True
    run.attempt.duration_ms = elapsed_ms(run.attempt_started_at)

    if not result.is_stream:
        app_state.router.record_success(
            channel.id,
            credential_id=target.credential_id,
            model_name=target.model_name,
            fault_protocol=target.fault_protocol,
            started_revision=run.route_started_revision,
        )

    merged_request_content = result.request_content or prepared.request_content
    if result.is_stream:
        if result.stream_capture is not None:
            result.stream_capture.request_log_id = run.log_ctx.request_log_id
            result.stream_capture.stream_started_at = run.log_ctx.started_at
            result.stream_capture.route_started_revision = run.route_started_revision
            result.stream_capture.route_cursor_key = (
                run.plan.cursor_key or run.plan.resolved_group_name or ""
            )
            result.stream_capture.route_was_probe = run.was_probe
        first_token_latency_ms = (
            result.stream_capture.first_token_latency_ms
            if result.stream_capture is not None
            else result.first_token_latency_ms
        )
        await run.log_ctx.record_streaming(
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
            log_ctx=run.log_ctx,
            channel=channel,
            fault_protocol=target.fault_protocol,
            result=result,
            attempts=attempt_logs_to_dicts(run.log_ctx.attempts),
            target=target,
            was_probe=run.was_probe,
        )
        return result.response

    await run.log_ctx.record_success(
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
    app_state.router.note_success(
        run.plan.cursor_key or run.plan.resolved_group_name or "", target
    )
    return result.response


async def run_attempt(
    *,
    request: AttemptRequest,
    plan: RoutingPlan,
    target: RouteTarget,
    deadline: RequestDeadline,
    log_ctx: RequestLogger,
    failures: FailureLedger,
    was_probe: bool = False,
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
        route_started_revision=route_started_revision,
        effective_user_agent=request.upstream_user_agent,
        was_probe=was_probe,
    )
    prepared = await _prepare_attempt(run)
    if not isinstance(prepared, _PreparedAttempt):
        return prepared
    result = await _send_attempt(run, prepared)
    if not isinstance(result, UpstreamResult):
        return result
    return await _finish_attempt(run, prepared, result)


async def _finalize_stream_request(
    *,
    log_ctx: RequestLogger,
    channel: ChannelConfig,
    fault_protocol: str,
    result: UpstreamResult,
    attempts: list[dict[str, Any]],
    target: RouteTarget,
    was_probe: bool,
) -> None:
    """Background close-out of a streamed attempt: route health, then the log row."""
    outcome = stream_log_outcome(result, result.stream_capture)
    try:
        await _record_stream_route_health(
            channel=channel,
            fault_protocol=fault_protocol,
            capture=result.stream_capture,
            capture_issue=outcome.capture_issue,
            lifecycle_status=outcome.lifecycle_status,
            attempts=attempts,
        )
        if outcome.capture_issue is None:
            app_state.router.note_success(
                result.stream_capture.route_cursor_key
                if result.stream_capture is not None
                else "",
                target,
            )
        elif was_probe and not (
            result.stream_capture is not None
            and result.stream_capture.error_category is not None
        ):
            app_state.router.record_failure(
                channel.id,
                outcome.capture_issue,
                category=ErrorCategory.SERVER,
                credential_id=target.credential_id,
                model_name=target.model_name,
                fault_protocol=fault_protocol,
                scope="model",
                cooldown_seconds=None,
                was_probe=True,
            )
        await record_stream_request_log(
            log_ctx=log_ctx,
            channel=channel,
            result=result,
            attempts=attempts,
            outcome=outcome,
        )
    finally:
        if was_probe:
            app_state.router.release_probe(target)


async def _record_stream_route_health(
    *,
    channel: ChannelConfig,
    fault_protocol: str,
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
            fault_protocol=fault_protocol,
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
    scope: str | None = None
    if category is None:
        classification = classify_error(status_code)
        if classification is not None:
            category, scope, classified_cooldown, classified_action = classification
            cooldown_seconds = cooldown_seconds or classified_cooldown
        else:
            classified_action = None
    else:
        classified_action = None
    category = category or ErrorCategory.SERVER
    app_state.router.record_failure(
        channel.id,
        format_channel_error(capture_issue),
        category=category,
        scope=scope or default_scope(category),
        cooldown_seconds=cooldown_seconds,
        credential_id=credential_id,
        model_name=model_name,
        fault_protocol=fault_protocol,
        was_probe=capture.route_was_probe if capture is not None else False,
        retry_action=(
            capture.error_retry_action
            if capture is not None and capture.error_retry_action is not None
            else classified_action
        ),
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


def _failure_policy(exc: UpstreamRequestError) -> FailurePolicy | None:
    category = exc.router_error_category
    if category is None:
        classification = classify_error(exc.router_status_code)
        if classification is None:
            return None
        return policy_for(
            classification.category, classification.scope, classification.action
        )
    return policy_for(category, exc.router_error_scope, exc.router_retry_action)


async def _record_target_failure(
    run: _AttemptRun,
    exc: UpstreamRequestError,
    *,
    upstream_body: dict[str, Any],
    request_content: str | None = None,
) -> Response | None:
    """Log the failed attempt, feed cooldowns, and honor stop-fallback."""
    channel = run.target.channel
    message = format_channel_error(exc.detail)
    policy = _failure_policy(exc)
    if (
        policy is not None
        and not exc.skip_route_failure
        and not _is_request_too_large_error(exc.status_code, message)
    ):
        app_state.router.record_failure(
            channel.id,
            message,
            category=policy.category,
            scope=policy.scope,
            credential_id=run.target.credential_id,
            model_name=run.target.model_name,
            fault_protocol=run.target.fault_protocol,
            cooldown_seconds=exc.router_cooldown_seconds,
            was_probe=run.was_probe,
            retry_action=exc.router_retry_action,
        )
    action = policy.action if policy is not None else RetryAction.RETRY_CHANNEL
    if exc.stop_fallback:
        action = RetryAction.TERMINAL
    run.failures.last_action = action
    run.failures.record(
        message,
        exc.status_code,
        exc.error_type,
        retry_after_seconds=exc.router_cooldown_seconds,
    )
    run.attempt.status_code = exc.status_code
    run.attempt.duration_ms = elapsed_ms(run.attempt_started_at)
    run.attempt.error_message = message
    run.attempt.reasoning_effort = extract_request_reasoning_effort(
        run.log_ctx.body, upstream_body
    )
    run.failures.last_log_failure = LogFailure(
        requested_group_name=run.plan.requested_group_name,
        resolved_group_name=run.plan.resolved_group_name,
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
                else (dump_log_json(upstream_body) if run.log_body_enabled else None)
            )
        ),
    )
    if action is RetryAction.TERMINAL:
        await run.failures.last_log_failure.write(run.log_ctx)
        return protocol_error_response(
            protocol=run.log_ctx.protocol,
            status_code=exc.status_code,
            error_type=exc.error_type,
            message=message,
        )
    return None


def _final_upstream_failure(
    errors: list[str],
    failure_status_codes: list[int | None],
    failure_error_types: list[str],
) -> tuple[int, str, str]:
    for error, status_code in zip(errors, failure_status_codes, strict=False):
        if _is_request_too_large_error(status_code, error):
            return 413, "request_too_large", error
    # Every target rejected the request itself, e.g. as longer than its context.
    if (
        errors
        and failure_status_codes
        and all(status_code in (400, 422) for status_code in failure_status_codes)
    ):
        # A request Lens itself could not convert is a client error, not an
        # upstream failure: no target ever saw it.
        error_type = (
            "bad_request"
            if failure_error_types
            and all(value == "bad_request" for value in failure_error_types)
            else "upstream_error"
        )
        return failure_status_codes[0] or 400, error_type, errors[0]
    if failure_status_codes and all(
        status_code == 504 for status_code in failure_status_codes
    ):
        return 504, "gateway_timeout", "All upstream channels timed out"
    if failure_status_codes and all(
        status_code == 429 for status_code in failure_status_codes
    ):
        return 429, "rate_limit_error", errors[0]
    if failure_status_codes and all(
        status_code == 503 for status_code in failure_status_codes
    ):
        return 503, "upstream_error", errors[0]
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
