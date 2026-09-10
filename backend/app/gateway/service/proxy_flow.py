from __future__ import annotations

import asyncio
from collections.abc import Mapping
from time import perf_counter
from typing import Any

from fastapi import Response
from fastapi.responses import JSONResponse

from ...core.errors import RoutingError
from ...core.model_name_parser import parse_model_name
from ...models.channels import ChannelConfig
from ...models.gateway_keys import GatewayApiKey
from ...models.protocols import ProtocolKind
from ..router import RouteSelection, RouteTarget
from ..router.routing import CooldownRoutingError
from .app_state import app_state
from .auth import gateway_key_allows_model
from .error_responses import protocol_error_response
from .http_handlers import apply_router_runtime_settings
from .multimodal import body_has_multimodal_content
from .payload_serialization import dump_log_json
from .proxy_attempt import AttemptLog, AttemptRequest, FailureLedger, run_attempt
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
) -> RequestLogger:
    request_log = await app_state.request_log_store.create_pending_request_log(
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
    return RequestLogger(
        request_log_id=request_log.id,
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
    *,
    channels: list[ChannelConfig],
    protocol: ProtocolKind,
    requested_model: str,
    log_ctx: RequestLogger,
    is_stream_body: bool,
    parsed_model: object | None = None,
    group_id: str | None = None,
    requested_group_name: str | None = None,
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
        )
        log_ctx.plan_route(
            requested_group_name=plan.requested_group_name,
            resolved_group_name=plan.resolved_group_name,
        )
        await log_ctx.record_connecting(is_stream=is_stream_body)
        return RouteResolution(plan=plan, selection=selection, error=None)
    except (CooldownRoutingError, RoutingError) as exc:
        if isinstance(exc, CooldownRoutingError):
            _log_cooldown_attempts(log_ctx, exc.cooled_targets)
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
            ),
        )


def _log_cooldown_attempts(
    log_ctx: RequestLogger,
    cooled_targets: list[tuple[RouteTarget, str]],
) -> None:
    """Record every cooled target as a skipped attempt for the chain dialog."""
    for target, reason in cooled_targets:
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
                error_message=reason,
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
) -> JSONResponse:
    log_ctx.plan_route(
        requested_group_name=plan.requested_group_name if plan else requested_model,
        resolved_group_name=plan.resolved_group_name if plan else None,
    )
    await log_ctx.record_failure(
        status_code=503,
        error_message=str(exc),
        is_stream=is_stream_body,
    )
    return protocol_error_response(
        protocol=protocol,
        status_code=503,
        error_type="routing_error",
        message="Gateway routing failed",
    )


async def _resolve_route_plans(
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
) -> list[tuple[RoutingPlan, RouteSelection]]:
    """Resolve the initial route and eligible multimodal fallback groups."""
    route_plans = [(initial_plan, initial_selection)]
    if not body_has_multimodal_content(body, protocol):
        return route_plans

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
            route_plans.append(
                (fallback_resolution.plan, fallback_resolution.selection)
            )
    return route_plans


async def _run_route_attempts(
    *,
    route_plans: list[tuple[RoutingPlan, RouteSelection]],
    request: AttemptRequest,
    deadline: RequestDeadline,
    log_ctx: RequestLogger,
    failures: FailureLedger,
    is_stream_body: bool,
) -> Response | None:
    """Try each available target, returning the first successful response."""
    for current_plan, current_selection in route_plans:
        for target in [current_selection.primary, *current_selection.fallbacks]:
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
            if not app_state.router.is_target_available(target):
                continue
            response = await run_attempt(
                request=request,
                plan=current_plan,
                target=target,
                deadline=deadline,
                log_ctx=log_ctx,
                failures=failures,
            )
            if response is not None:
                return response
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


async def _finalize_proxy_failure(
    *,
    protocol: ProtocolKind,
    plan: RoutingPlan | None,
    requested_model: str,
    log_ctx: RequestLogger,
    failures: FailureLedger,
    is_stream_body: bool,
) -> Response:
    failed_status_code, failed_error_type, failed_message = failures.final_failure()
    if not log_ctx.attempts:
        log_ctx.plan_route(
            requested_group_name=plan.requested_group_name if plan else requested_model,
            resolved_group_name=plan.resolved_group_name if plan else None,
        )
        await log_ctx.record_failure(
            status_code=failed_status_code,
            error_message=failed_message,
            is_stream=is_stream_body,
        )
    return protocol_error_response(
        protocol=protocol,
        status_code=failed_status_code,
        error_type=failed_error_type,
        message=failed_message,
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
    protocol: ProtocolKind,
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
    ) = await _prepare_proxy_context(
        body=body,
        protocol=protocol,
        inbound_user_agent=inbound_user_agent,
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
        is_stream=is_stream_body,
        request_content=request_content,
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
    try:
        route_resolution = await _resolve_proxy_route(
            channels=channels,
            protocol=protocol,
            requested_model=requested_model,
            log_ctx=log_ctx,
            is_stream_body=is_stream_body,
            parsed_model=parsed_model,
            requested_group_name=original_requested_model,
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
        route_plans = await _resolve_route_plans(
            initial_plan=plan,
            initial_selection=selection,
            channels=channels,
            protocol=protocol,
            requested_model=requested_model,
            parsed_model=parsed_model,
            requested_group_name=original_requested_model,
            body=body,
            log_ctx=log_ctx,
            is_stream_body=is_stream_body,
            failures=failures,
        )
        response = await _run_route_attempts(
            route_plans=route_plans,
            request=request,
            deadline=deadline,
            log_ctx=log_ctx,
            failures=failures,
            is_stream_body=is_stream_body,
        )
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
