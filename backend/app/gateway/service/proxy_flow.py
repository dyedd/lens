from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Mapping
from dataclasses import replace
from math import ceil
from time import perf_counter
from typing import Any

from fastapi import Response
from fastapi.responses import JSONResponse

from app.models.request_logs import RequestLogInput

from ...core.errors import RoutingError
from ...core.model_name_parser import parse_model_name
from ...models.channels import ChannelConfig
from ...models.gateway_keys import GatewayApiKey
from ...models.protocols import ProtocolKind
from ...plugins.contract import InboundRequest, PluginRejection
from ...plugins.runtime import PluginRun, begin_run, run_request_rewrite
from ..router import RouteSelection, RouteTarget, TargetKey, target_key
from ..router.failover import RetryAction, next_candidate
from .app_state import app_state
from .auth import gateway_key_allows_model
from .context_tokens import estimate_request_context_tokens
from .error_responses import protocol_error_response
from .http_handlers import apply_router_runtime_settings
from .multimodal import body_has_multimodal_content
from .payload_serialization import dump_log_json
from .proxy_attempt import (
    AttemptLog,
    AttemptRequest,
    FailureLedger,
    LogFailure,
    run_attempt,
)
from .request_logger import RequestLogger
from .routing_plan import (
    resolve_routing_plan,
)
from .runtime_types import (
    RequestDeadline,
    RouteResolution,
    RoutingPlan,
)
from .upstream_support import (
    default_lens_user_agent,
    is_generic_user_agent,
    sanitize_user_agent,
)


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
    plugin_run: PluginRun,
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
        )
    )
    return RequestLogger(
        request_log_id=request_log.id,
        protocol=protocol,
        gateway_key=gateway_key,
        started_at=started_at,
        body=body,
        request_content=request_content,
        attempts=[],
        user_agent=user_agent,
        plugin_run=plugin_run,
        requested_group_name=requested_group_name,
    )


async def _resolve_proxy_route(
    *,
    channels: list[ChannelConfig],
    protocol: ProtocolKind,
    requested_model: str,
    log_ctx: RequestLogger,
    is_stream_body: bool,
    parsed_model: object | None = None,
    group_id: str | None = None,
    requested_group_name: str | None = None,
    failures: FailureLedger | None = None,
    required_context_tokens: int | None = None,
) -> RouteResolution:
    plan: RoutingPlan | None = None
    try:
        plan = await resolve_routing_plan(
            protocol,
            requested_model,
            channels,
            parsed_model=parsed_model,
            group_id=group_id,
            requested_group_name=requested_group_name,
        )
        selection = app_state.router.select(
            channels,
            protocol,
            plan.resolved_group_name,
            strategy=plan.strategy,
            route_targets=plan.route_targets,
            use_model_matching=plan.use_model_matching,
            cursor_key=plan.cursor_key,
            required_context_tokens=required_context_tokens,
        )
        log_ctx.plan_route(
            requested_group_name=plan.requested_group_name,
            resolved_group_name=plan.resolved_group_name,
        )
        await log_ctx.record_connecting(is_stream=is_stream_body)
        return RouteResolution(plan=plan, selection=selection, error=None)
    except RoutingError as exc:
        return RouteResolution(
            plan=plan,
            selection=None,
            error=await _routing_error_response(
                plan=plan,
                protocol=protocol,
                requested_model=requested_model,
                log_ctx=log_ctx,
                is_stream_body=is_stream_body,
                exc=exc,
                failures=failures,
            ),
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


async def _routing_error_response(
    *,
    plan: RoutingPlan | None,
    protocol: ProtocolKind,
    requested_model: str,
    log_ctx: RequestLogger,
    is_stream_body: bool,
    exc: Exception,
    failures: FailureLedger | None = None,
) -> JSONResponse:
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
    if failures is None:
        await failure.write(log_ctx)
    else:
        failures.last_log_failure = failure
    return protocol_error_response(
        protocol=protocol,
        status_code=503,
        error_type="routing_error",
        message=message,
    )


async def _iter_route_plans(
    *,
    initial_plan: RoutingPlan,
    initial_selection: RouteSelection,
    channels: list[ChannelConfig],
    protocol: ProtocolKind,
    requested_model: str,
    parsed_model: object,
    requested_group_name: str,
    body: dict[str, Any],
    log_ctx: RequestLogger,
    is_stream_body: bool,
    failures: FailureLedger,
    required_context_tokens: int | None,
) -> AsyncIterator[tuple[RoutingPlan, RouteSelection]]:
    """Resolve fallback groups only after the current group's attempts fail."""
    yield initial_plan, initial_selection
    if not body_has_multimodal_content(body, protocol):
        return

    seen_group_ids = {
        initial_plan.resolved_group.id if initial_plan.resolved_group else ""
    }
    for fallback_group_id in initial_plan.fallback_group_ids:
        if fallback_group_id in seen_group_ids:
            continue
        seen_group_ids.add(fallback_group_id)
        fallback_resolution = await _resolve_proxy_route(
            channels=channels,
            protocol=protocol,
            requested_model=requested_model,
            log_ctx=log_ctx,
            is_stream_body=is_stream_body,
            parsed_model=parsed_model,
            group_id=fallback_group_id,
            requested_group_name=requested_group_name,
            failures=failures,
            required_context_tokens=required_context_tokens,
        )
        if fallback_resolution.error is not None:
            failures.record(
                fallback_resolution.error.body.decode(errors="replace"),
                fallback_resolution.error.status_code,
            )
        elif (
            fallback_resolution.plan is not None
            and fallback_resolution.selection is not None
        ):
            yield fallback_resolution.plan, fallback_resolution.selection


async def _run_route_attempts(
    *,
    route_plans: AsyncIterator[tuple[RoutingPlan, RouteSelection]],
    request: AttemptRequest,
    deadline: RequestDeadline,
    log_ctx: RequestLogger,
    failures: FailureLedger,
    is_stream_body: bool,
) -> Response | None:
    """Try each available target, returning the first successful response."""
    async for current_plan, current_selection in route_plans:
        ordered = current_selection.ordered()
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
                response = await run_attempt(
                    request=request,
                    plan=current_plan,
                    target=target,
                    deadline=deadline,
                    log_ctx=log_ctx,
                    failures=failures,
                    was_probe=is_probe,
                )
            finally:
                if is_probe and not (
                    response is not None and bool(request.body.get("stream"))
                ):
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
    plugin_run: PluginRun,
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
        plugin_run=plugin_run,
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


async def _failed_request_response(
    *,
    protocol: ProtocolKind,
    log_ctx: RequestLogger,
    is_stream_body: bool,
    status_code: int,
    error_type: str,
    message: str,
) -> Response:
    """Finalize a request that never reached routing and answer in its protocol."""
    await log_ctx.record_failure(
        status_code=status_code, error_message=message, is_stream=is_stream_body
    )
    return protocol_error_response(
        protocol=protocol,
        status_code=status_code,
        error_type=error_type,
        message=message,
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
) -> tuple[list[ChannelConfig], dict[str, Any], RequestDeadline, str, bool, str | None]:
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
    apply_router_runtime_settings(runtime)
    log_body_enabled = bool(runtime["relay_log_body_enabled"])
    request_content = dump_log_json(body) if log_body_enabled else None
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
    )


def _cooled_wait_seconds(
    failures: FailureLedger,
    deadline: RequestDeadline,
    runtime: Mapping[str, Any],
) -> float | None:
    """Return how long to wait for the soonest cooling target, when worth it."""
    cap = float(runtime.get("failover_cooled_wait_seconds") or 0)
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
    request_path: str = "",
) -> Response:
    (
        channels,
        runtime,
        deadline,
        upstream_user_agent,
        is_stream_body,
        request_content,
    ) = await _prepare_proxy_context(
        body=body,
        inbound_user_agent=inbound_user_agent,
    )
    started_at = deadline.started_at
    requested_model = body.get("model")
    plugin_run = begin_run(
        app_state.plugin_registry.hook_set(),
        InboundRequest(
            protocol=protocol.value,
            path=request_path,
            model=requested_model.strip() if isinstance(requested_model, str) else "",
            is_stream=is_stream_body,
            user_agent=sanitize_user_agent(inbound_user_agent),
        ),
    )
    if not isinstance(requested_model, str) or not requested_model.strip():
        return await _missing_model_response(
            protocol=protocol,
            body=body,
            gateway_key=gateway_key,
            started_at=started_at,
            user_agent=upstream_user_agent,
            is_stream_body=is_stream_body,
            request_content=request_content,
            plugin_run=plugin_run,
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
        is_stream=is_stream_body,
        request_content=request_content,
        plugin_run=plugin_run,
    )
    try:
        try:
            rewritten_body = await run_request_rewrite(plugin_run, body)
        except PluginRejection as exc:
            return await _failed_request_response(
                protocol=protocol,
                log_ctx=log_ctx,
                is_stream_body=is_stream_body,
                status_code=exc.status_code,
                error_type=exc.error_type,
                message=exc.public_message,
            )
        if rewritten_body is not body:
            # 请求日志保留客户端原始请求体；之后的检查、路由与尝试都按改写后的请求。
            body = rewritten_body
            rewritten_model = body.get("model")
            if not isinstance(rewritten_model, str) or not rewritten_model.strip():
                return await _failed_request_response(
                    protocol=protocol,
                    log_ctx=log_ctx,
                    is_stream_body=is_stream_body,
                    status_code=400,
                    error_type="missing_model",
                    message="Request model is required",
                )
            original_requested_model = rewritten_model.strip()
            try:
                parsed_model = parse_model_name(original_requested_model)
            except ValueError as exc:
                return await _failed_request_response(
                    protocol=protocol,
                    log_ctx=log_ctx,
                    is_stream_body=is_stream_body,
                    status_code=400,
                    error_type="invalid_model",
                    message=str(exc),
                )
            requested_model = parsed_model.base_model
            is_stream_body = bool(body.get("stream"))
            plugin_run.request = replace(
                plugin_run.request,
                model=original_requested_model,
                is_stream=is_stream_body,
            )
            log_ctx.plan_route(
                requested_group_name=original_requested_model,
                resolved_group_name=None,
            )
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
        required_context_tokens = estimate_request_context_tokens(body, protocol)
        route_resolution = await _resolve_proxy_route(
            channels=channels,
            protocol=protocol,
            requested_model=requested_model,
            log_ctx=log_ctx,
            is_stream_body=is_stream_body,
            parsed_model=parsed_model,
            requested_group_name=original_requested_model,
            required_context_tokens=required_context_tokens,
        )
        if route_resolution.error is not None:
            return route_resolution.error
        plan = route_resolution.plan
        selection = route_resolution.selection
        if plan is None or selection is None:
            raise RuntimeError("Routing plan was not resolved")

        failures = FailureLedger()
        request = AttemptRequest(
            protocol=protocol,
            body=body,
            runtime=runtime,
            upstream_user_agent=upstream_user_agent,
            inbound_headers=inbound_headers,
            path_suffix=path_suffix,
            multipart_files=multipart_files,
        )

        async def attempt(
            current_plan: RoutingPlan, current_selection: RouteSelection
        ) -> Response | None:
            return await _run_route_attempts(
                route_plans=_iter_route_plans(
                    initial_plan=current_plan,
                    initial_selection=current_selection,
                    channels=channels,
                    protocol=protocol,
                    requested_model=requested_model,
                    parsed_model=parsed_model,
                    requested_group_name=original_requested_model,
                    body=body,
                    log_ctx=log_ctx,
                    is_stream_body=is_stream_body,
                    failures=failures,
                    required_context_tokens=required_context_tokens,
                ),
                request=request,
                deadline=deadline,
                log_ctx=log_ctx,
                failures=failures,
                is_stream_body=is_stream_body,
            )

        response = await attempt(plan, selection)
        # 全部候选都在冷却时，先在首字预算内等最早恢复再重选一次路。
        wait_seconds = (
            None
            if response is not None
            else _cooled_wait_seconds(failures, deadline, runtime)
        )
        if wait_seconds is not None:
            await asyncio.sleep(wait_seconds)
            retry_resolution = await _resolve_proxy_route(
                channels=channels,
                protocol=protocol,
                requested_model=requested_model,
                log_ctx=log_ctx,
                is_stream_body=is_stream_body,
                parsed_model=parsed_model,
                requested_group_name=original_requested_model,
                failures=failures,
                required_context_tokens=required_context_tokens,
            )
            if retry_resolution.error is not None:
                # 重选路失败只记进了失败账本，这里才是终态写入。
                if failures.last_log_failure is not None:
                    await failures.last_log_failure.write(log_ctx)
                return retry_resolution.error
            if (
                retry_resolution.plan is not None
                and retry_resolution.selection is not None
            ):
                plan = retry_resolution.plan
                response = await attempt(plan, retry_resolution.selection)
        if response is not None:
            return response

        return await _finalize_proxy_failure(
            protocol=protocol,
            plan=plan,
            requested_model=requested_model,
            log_ctx=log_ctx,
            failures=failures,
            is_stream_body=is_stream_body,
        )
    except Exception as exc:
        await _log_unexpected_proxy_error(
            log_ctx=log_ctx,
            plan=plan if "plan" in locals() else None,
            requested_model=requested_model,
            is_stream_body=is_stream_body,
            exc=exc,
        )
        raise
