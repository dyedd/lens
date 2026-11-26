from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator, Mapping
from dataclasses import dataclass
from math import ceil
from time import perf_counter
from typing import Any

from fastapi import Response
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.core.privacy_rules import PrivacyError
from app.models.request_logs import RequestLogInput

from ....core.errors import RequestCancelledError, RoutingError
from ....core.model_name_parser import ParsedModelName, parse_model_name
from ....models.channels import ChannelConfig
from ....models.gateway_keys import GatewayApiKey
from ....models.protocols import ProtocolKind
from ....models.settings import RuntimeSettings
from ...router import RouteTarget, TargetKey, target_key
from ...router.failover import RetryAction, next_candidate
from ..app_state import app_state
from ..auth import gateway_key_allows_model
from ..context_tokens import estimate_request_context_tokens
from ..error_responses import protocol_error_response
from ..multimodal import body_has_multimodal_content
from ..payload_serialization import dump_log_json
from ..privacy_context import PrivacyContext
from ..request_logger import RequestLogger
from ..runtime_types import (
    RequestDeadline,
    RouteResolution,
    RoutingPlan,
)
from ..streaming.transport import FinalizingStreamingResponse
from ..upstream_support import (
    default_lens_user_agent,
    is_generic_user_agent,
    sanitize_user_agent,
)
from .proxy_attempt import (
    AttemptLog,
    AttemptRequest,
    FailureLedger,
    LogFailure,
    execute_target_attempt,
)
from .routing_plan import resolve_routing_plan

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class _ProxyRouteContext:
    request: AttemptRequest
    channels: list[ChannelConfig]
    parsed_model: ParsedModelName
    requested_group_name: str
    log_ctx: RequestLogger
    failures: FailureLedger
    required_context_tokens: int | None
    deadline: RequestDeadline


async def _create_pending_proxy_log_context(
    *,
    protocol: ProtocolKind,
    user_agent: str,
    gateway_key: GatewayApiKey,
    started_at: float,
    body: dict[str, Any],
    requested_group_name: str | None,
    is_stream: bool,
    request_content: str | None,
    privacy: PrivacyContext | None = None,
) -> RequestLogger:
    request_log = await app_state.request_log_store.commands.create_request_log(
        RequestLogInput(
            protocol=protocol.value,
            user_agent=user_agent,
            requested_group_name=requested_group_name,
            resolved_group_name=None,
            upstream_model_name=None,
            channel_id=None,
            channel_name=None,
            gateway_key_id=gateway_key.id,
            is_stream=is_stream,
            request_content=request_content,
            privacy_summary=privacy.summary() if privacy is not None else [],
        )
    )
    return RequestLogger(
        request_log_id=request_log.id,
        privacy=privacy,
        protocol=protocol,
        gateway_key=gateway_key,
        started_at=started_at,
        body=body,
        request_content=request_content,
        attempts=[],
        user_agent=user_agent,
        requested_group_name=requested_group_name,
    )


async def _resolve_proxy_route(
    context: _ProxyRouteContext,
    *,
    fallback_group_id: str | None = None,
) -> RouteResolution | JSONResponse:
    request = context.request
    requested_model = context.parsed_model.base_model
    is_stream_body = bool(request.body.get("stream"))
    plan: RoutingPlan | None = None
    try:
        plan = await resolve_routing_plan(
            request.protocol,
            requested_model,
            context.channels,
            group_repo=app_state.group_repo,
            parsed_model=context.parsed_model,
            group_id=fallback_group_id,
            requested_group_name=context.requested_group_name,
        )
        selection = app_state.router.select(
            context.channels,
            request.protocol,
            requested_model=plan.resolved_group_name,
            strategy=plan.strategy,
            route_targets=plan.route_targets,
            use_model_matching=plan.use_model_matching,
            cursor_key=plan.cursor_key,
            required_context_tokens=context.required_context_tokens,
        )
        context.log_ctx.plan_route(
            requested_group_name=plan.requested_group_name,
            resolved_group_name=plan.resolved_group_name,
        )
        await context.log_ctx.record_connecting(is_stream=is_stream_body)
        return RouteResolution(plan=plan, selection=selection)
    except RoutingError as exc:
        error_msg = str(exc).strip()
        if error_msg:
            message = f"Gateway routing failed: {error_msg}"
        else:
            message = f"Gateway routing failed for model '{requested_model}'"
        failure = LogFailure(
            requested_group_name=plan.requested_group_name if plan else requested_model,
            resolved_group_name=plan.resolved_group_name if plan else None,
            status_code=503,
            error_message=error_msg or message,
            is_stream=is_stream_body,
        )
        if fallback_group_id is None:
            await failure.write(context.log_ctx)
        else:
            context.failures.last_log_failure = failure
        return protocol_error_response(
            protocol=request.protocol,
            status_code=503,
            error_type="routing_error",
            message=message,
        )


def _record_cooled_candidates(
    *,
    log_ctx: RequestLogger,
    failures: FailureLedger,
    ordered: list[RouteTarget],
    tried: set[TargetKey],
) -> None:
    """Record every candidate the loop skipped because it was cooling."""
    for target in ordered:
        if target_key(target) in tried:
            continue
        seconds = app_state.router.cooldown_remaining_seconds(target)
        if seconds <= 0:
            continue
        failures.cooled_waits[target_key(target)] = seconds
        log_ctx.attempts.append(
            AttemptLog(
                channel_id=target.channel.id,
                channel_name=target.channel.name or target.channel.id,
                credential_id=target.credential_id,
                credential_name=target.credential_name or "",
                model_name=target.model_name,
                status_code=503,
                success=False,
                duration_ms=0,
                error_message=app_state.router.cooldown_reason(target)
                or "cooling down",
            )
        )


async def _iter_route_plans(
    context: _ProxyRouteContext, initial_route: RouteResolution
) -> AsyncIterator[RouteResolution]:
    """Resolve fallback groups only after the current group's attempts fail."""
    request = context.request
    yield initial_route
    if not body_has_multimodal_content(request.body, request.protocol):
        return

    initial_plan = initial_route.plan
    seen_group_ids = {
        initial_plan.resolved_group.id if initial_plan.resolved_group else ""
    }
    for fallback_group_id in initial_plan.fallback_group_ids:
        if fallback_group_id in seen_group_ids:
            continue
        seen_group_ids.add(fallback_group_id)
        fallback_resolution = await _resolve_proxy_route(
            context, fallback_group_id=fallback_group_id
        )
        if isinstance(fallback_resolution, JSONResponse):
            context.failures.record(
                fallback_resolution.body.decode(errors="replace"),
                fallback_resolution.status_code,
            )
        else:
            yield fallback_resolution


async def _run_route_attempts(
    context: _ProxyRouteContext, initial_route: RouteResolution
) -> Response | None:
    """Try each available target, returning the first successful response."""
    request = context.request
    deadline = context.deadline
    log_ctx = context.log_ctx
    failures = context.failures
    is_stream_body = bool(request.body.get("stream"))
    async for route in _iter_route_plans(context, initial_route):
        current_plan = route.plan
        ordered = route.selection.ordered()
        tried: set[TargetKey] = set()
        failed: RouteTarget | None = None
        action = RetryAction.RETRY_CHANNEL
        while True:
            if deadline.is_first_token_expired():
                timeout_message = deadline.timeout_message(kind="first_token")
                log_ctx.plan_route(
                    requested_group_name=current_plan.requested_group_name,
                    resolved_group_name=current_plan.resolved_group_name,
                )
                await log_ctx.record_failure(
                    status_code=504,
                    error_message=timeout_message,
                    is_stream=is_stream_body,
                )
                return protocol_error_response(
                    protocol=request.protocol,
                    status_code=504,
                    error_type="gateway_timeout",
                    message=timeout_message,
                )
            candidate = next_candidate(
                ordered,
                failed=failed,
                tried=tried,
                action=action,
                claim=lambda target: app_state.router.claim_target(
                    target,
                    lease_seconds=float(request.runtime["first_token_timeout_seconds"]),
                ),
            )
            if candidate is None:
                _record_cooled_candidates(
                    log_ctx=log_ctx,
                    failures=failures,
                    ordered=ordered,
                    tried=tried,
                )
                break
            target, is_probe = candidate
            tried.add(target_key(target))
            response: Response | None = None
            try:
                response = await execute_target_attempt(
                    request=request,
                    plan=current_plan,
                    target=target,
                    deadline=deadline,
                    log_ctx=log_ctx,
                    failures=failures,
                    was_probe=is_probe,
                )
            finally:
                if is_probe and not isinstance(response, FinalizingStreamingResponse):
                    app_state.router.release_probe(target)
            if response is not None:
                return response
            failed = target
            action = failures.last_action or RetryAction.RETRY_CHANNEL
            app_state.router.note_failure(
                current_plan.cursor_key or current_plan.resolved_group_name or ""
            )
    return None


async def _missing_model_response(
    *,
    protocol: ProtocolKind,
    body: dict[str, Any],
    gateway_key: GatewayApiKey,
    started_at: float,
    user_agent: str,
    is_stream_body: bool,
    request_content: str | None,
) -> Response:
    log_ctx = await _create_pending_proxy_log_context(
        protocol=protocol,
        user_agent=user_agent,
        gateway_key=gateway_key,
        started_at=started_at,
        body=body,
        requested_group_name=None,
        is_stream=is_stream_body,
        request_content=request_content,
    )
    await log_ctx.record_failure(
        status_code=400,
        error_message="Request model is required",
        is_stream=is_stream_body,
        request_content=request_content,
    )
    return protocol_error_response(
        protocol=protocol,
        status_code=400,
        error_type="missing_model",
        message="Request model is required",
    )


async def _check_gateway_model_access(
    *,
    protocol: ProtocolKind,
    gateway_key: GatewayApiKey,
    requested_model: str,
    log_ctx: RequestLogger,
    is_stream_body: bool,
    request_content: str | None,
) -> Response | None:
    if gateway_key_allows_model(gateway_key, requested_model):
        return None
    error_message = "Gateway API key is not allowed to use this model"
    await log_ctx.record_failure(
        status_code=403,
        error_message=error_message,
        is_stream=is_stream_body,
        request_content=request_content,
    )
    return protocol_error_response(
        protocol=protocol,
        status_code=403,
        error_type="forbidden_model",
        message=error_message,
    )


def _retry_after_headers(seconds: float | None) -> dict[str, str] | None:
    """Tell the client when the soonest candidate becomes usable again."""
    if seconds is None or seconds <= 0:
        return None
    return {"Retry-After": str(max(int(ceil(seconds)), 1))}


def _all_cooled_failure(failures: FailureLedger) -> tuple[int, str, str]:
    """Describe a request that never reached an upstream: every target cools."""
    message = f"All {len(failures.cooled_waits)} matching route targets are in cooldown"
    remaining = min(failures.cooled_waits.values(), default=0.0)
    if remaining > 0:
        message = f"{message} (retry in {max(int(ceil(remaining)), 1)}s)"
    return 503, "routing_error", message


def _summarize_attempt_failures(log_ctx: RequestLogger) -> str | None:
    """Keep one readable diagnostic for every failed route target."""
    details: list[str] = []
    seen: set[tuple[str, str | None, str | None]] = set()
    for attempt in log_ctx.attempts:
        if attempt.success or not attempt.error_message:
            continue
        detail = attempt.error_message.strip()
        if not detail:
            continue
        key = (
            attempt.channel_id,
            attempt.credential_id,
            attempt.model_name,
        )
        if key in seen:
            continue
        seen.add(key)
        channel_name = attempt.channel_name.strip() or attempt.channel_id
        details.append(f"{channel_name}: {detail}")
    return "; ".join(details) or None


async def _finalize_proxy_failure(
    *,
    protocol: ProtocolKind,
    plan: RoutingPlan | None,
    requested_model: str,
    log_ctx: RequestLogger,
    failures: FailureLedger,
    is_stream_body: bool,
) -> Response:
    all_targets_cooled = not failures.errors and bool(failures.cooled_waits)
    if all_targets_cooled:
        failed_status_code, failed_error_type, failed_message = _all_cooled_failure(
            failures
        )
    else:
        failed_status_code, failed_error_type, failed_message = failures.final_failure()
    if all_targets_cooled:
        # 客户端重试期间没有新的上游尝试，不重复制造同一条失败日志。
        await app_state.request_log_store.commands.discard_running_request_log(
            log_ctx.request_log_id
        )
    elif failures.last_log_failure is not None:
        failure_details = _summarize_attempt_failures(log_ctx)
        if failure_details is not None:
            failures.last_log_failure.error_message = failure_details
        await failures.last_log_failure.write(log_ctx)
    else:
        # 没有真实失败上下文时也要把日志定稿，否则会停在连接中。
        log_ctx.plan_route(
            requested_group_name=plan.requested_group_name if plan else requested_model,
            resolved_group_name=plan.resolved_group_name if plan else None,
        )
        await log_ctx.record_failure(
            status_code=failed_status_code,
            error_message=_summarize_attempt_failures(log_ctx) or failed_message,
            is_stream=is_stream_body,
        )
    retry_after = failures.retry_after_seconds
    if failures.cooled_waits:
        cooled = min(failures.cooled_waits.values())
        retry_after = cooled if retry_after is None else min(retry_after, cooled)
    return protocol_error_response(
        protocol=protocol,
        status_code=failed_status_code,
        error_type=failed_error_type,
        message=failed_message,
        headers=_retry_after_headers(retry_after),
    )


async def _log_unexpected_proxy_error(
    *,
    log_ctx: RequestLogger,
    plan: RoutingPlan | None,
    requested_model: str,
    is_stream_body: bool,
    exc: Exception,
) -> None:
    log_ctx.plan_route(
        requested_group_name=plan.requested_group_name if plan else requested_model,
        resolved_group_name=plan.resolved_group_name if plan else None,
    )
    await log_ctx.record_failure(
        status_code=500,
        error_message=f"Unexpected proxy error: {type(exc).__name__}: {exc}",
        is_stream=is_stream_body,
    )


async def _prepare_proxy_context(
    *,
    body: dict[str, Any],
    inbound_user_agent: str | None,
    gateway_key_id: str,
    session_id: str | None,
) -> tuple[
    list[ChannelConfig],
    RuntimeSettings,
    RequestDeadline,
    str,
    bool,
    str | None,
    PrivacyContext,
]:
    started_at = perf_counter()
    channels, runtime = await asyncio.gather(
        app_state.channel_store.list_channels(),
        app_state.settings_repo.get_runtime_settings(),
    )
    deadline = RequestDeadline(
        started_at,
        float(runtime["first_token_timeout_seconds"]),
        float(runtime["stream_idle_timeout_seconds"]),
    )
    app_state.apply_router_settings(runtime)
    log_body_enabled = bool(runtime["relay_log_body_enabled"])
    privacy = PrivacyContext(
        runtime["privacy_config"],
        settings.auth_secret_key,
        gateway_key_id=gateway_key_id,
        history=app_state.privacy_history,
        session_id=session_id,
    )
    request_content = (
        dump_log_json(body) if log_body_enabled and not privacy.config.enabled else None
    )
    inbound_ua = sanitize_user_agent(inbound_user_agent)
    upstream_user_agent = (
        inbound_ua
        if inbound_ua and not is_generic_user_agent(inbound_ua)
        else default_lens_user_agent()
    )
    return (
        channels,
        runtime,
        deadline,
        upstream_user_agent,
        bool(body.get("stream")),
        request_content,
        privacy,
    )


def _cooled_wait_seconds(
    failures: FailureLedger,
    deadline: RequestDeadline,
    cap: int,
) -> float | None:
    """Return how long to wait for the soonest cooling target, when worth it."""
    if cap <= 0 or not failures.cooled_waits:
        return None
    remaining = min(failures.cooled_waits.values())
    if remaining <= 0:
        return None
    wait = min(remaining, cap)
    budget = deadline.first_token_remaining_seconds()
    if budget is not None and budget <= wait:
        return None
    return wait


async def proxy_protocol(
    protocol: ProtocolKind,
    body: dict[str, Any],
    gateway_key: GatewayApiKey,
    inbound_user_agent: str | None = None,
    inbound_headers: Mapping[str, str] | None = None,
    path_suffix: str | None = None,
    multipart_files: list[tuple[str, tuple[str, bytes, str]]] | None = None,
) -> Response:
    (
        channels,
        runtime,
        deadline,
        upstream_user_agent,
        is_stream_body,
        request_content,
        privacy,
    ) = await _prepare_proxy_context(
        body=body,
        inbound_user_agent=inbound_user_agent,
        gateway_key_id=gateway_key.id,
        session_id=(inbound_headers or {}).get("x-lens-session-id"),
    )
    started_at = deadline.started_at
    requested_model = body.get("model")
    if not isinstance(requested_model, str) or not requested_model.strip():
        return await _missing_model_response(
            protocol=protocol,
            body=body,
            gateway_key=gateway_key,
            started_at=started_at,
            user_agent=upstream_user_agent,
            is_stream_body=is_stream_body,
            request_content=request_content,
        )
    requested_model = requested_model.strip()
    original_requested_model = requested_model
    try:
        parsed_model = parse_model_name(requested_model)
    except ValueError as exc:
        return protocol_error_response(
            protocol=protocol,
            status_code=400,
            error_type="invalid_model",
            message=str(exc),
        )
    requested_model = parsed_model.base_model

    log_ctx = await _create_pending_proxy_log_context(
        protocol=protocol,
        user_agent=upstream_user_agent,
        gateway_key=gateway_key,
        started_at=started_at,
        body=body,
        requested_group_name=original_requested_model,
        privacy=privacy,
        is_stream=is_stream_body,
        request_content=request_content,
    )
    plan: RoutingPlan | None = None
    is_streaming = False
    app_state.active_requests[log_ctx.request_log_id] = log_ctx.cancellation
    try:
        privacy.load_references(body)
        if runtime["relay_log_body_enabled"]:
            log_ctx.request_content = privacy.clean_log(dump_log_json(body))
        body = privacy.prepare(body, protocol)
        access_error = await _check_gateway_model_access(
            protocol=protocol,
            gateway_key=gateway_key,
            requested_model=requested_model,
            log_ctx=log_ctx,
            is_stream_body=is_stream_body,
            request_content=request_content,
        )
        if access_error is not None:
            return access_error
        failures = FailureLedger()
        request = AttemptRequest(
            privacy=privacy,
            protocol=protocol,
            body=body,
            runtime=runtime,
            upstream_user_agent=upstream_user_agent,
            inbound_headers=inbound_headers,
            path_suffix=path_suffix,
            multipart_files=multipart_files,
        )
        route_context = _ProxyRouteContext(
            request=request,
            channels=channels,
            parsed_model=parsed_model,
            requested_group_name=original_requested_model,
            log_ctx=log_ctx,
            failures=failures,
            required_context_tokens=estimate_request_context_tokens(body, protocol),
            deadline=deadline,
        )
        route_resolution = await _resolve_proxy_route(route_context)
        if isinstance(route_resolution, JSONResponse):
            return route_resolution
        plan = route_resolution.plan
        response = await _run_route_attempts(route_context, route_resolution)
        # 全部候选都在冷却时，先在首字预算内等最早恢复再重选一次路。
        wait_seconds = (
            None
            if response is not None
            else _cooled_wait_seconds(
                failures, deadline, runtime["failover_cooled_wait_seconds"]
            )
        )
        if wait_seconds is not None:
            with log_ctx.cancellation.watch():
                await asyncio.sleep(wait_seconds)
            failures.cooled_waits.clear()
            failures.retry_after_seconds = None
            retry_resolution = await _resolve_proxy_route(route_context)
            if isinstance(retry_resolution, JSONResponse):
                return retry_resolution
            plan = retry_resolution.plan
            response = await _run_route_attempts(route_context, retry_resolution)
        if response is not None:
            is_streaming = isinstance(response, FinalizingStreamingResponse)
            return response

        return await _finalize_proxy_failure(
            protocol=protocol,
            plan=plan,
            requested_model=requested_model,
            log_ctx=log_ctx,
            failures=failures,
            is_stream_body=is_stream_body,
        )
    except PrivacyError as exc:
        await log_ctx.record_failure(
            status_code=400, error_message=str(exc), is_stream=is_stream_body
        )
        return protocol_error_response(
            protocol=protocol,
            status_code=400,
            error_type="privacy_error",
            message=str(exc),
        )
    except RequestCancelledError as exc:
        await log_ctx.record_cancelled(str(exc), is_stream=is_stream_body)
        return protocol_error_response(
            protocol=protocol,
            status_code=exc.status_code,
            error_type=exc.error_type,
            message=str(exc),
        )
    except Exception as exc:
        try:
            await _log_unexpected_proxy_error(
                log_ctx=log_ctx,
                plan=plan,
                requested_model=requested_model,
                is_stream_body=is_stream_body,
                exc=exc,
            )
        except Exception:
            logger.exception("Failed to persist the proxy failure")
        raise
    finally:
        if not is_streaming:
            app_state.active_requests.pop(log_ctx.request_log_id, None)
