from __future__ import annotations

import asyncio
from collections.abc import Mapping
from time import perf_counter
from typing import Any

from fastapi import Response
from fastapi.responses import JSONResponse

from ...core.model_name_parser import parse_model_name
from ...models.channels import ChannelConfig
from ...models.gateway_keys import GatewayApiKey
from ...models.protocols import ProtocolKind
from ..router import RouteSelection
from ..router.routing import CooldownRoutingError
from ..router.types import RouteTarget
from .app_state import app_state
from .auth import _gateway_key_allows_model
from .error_responses import _protocol_error_response
from .errors import _apply_router_runtime_settings
from .multimodal import body_has_multimodal_content
from .payload_serialization import _dump_log_json
from .proxy_attempt import AttemptLog, AttemptRequest, FailureLedger, run_attempt
from .request_logger import _RequestLogger
from .routing_plan import (
    _resolve_routing_plan,
)
from .runtime_types import (
    RoutingPlan,
    _RequestDeadline,
)
from .upstream_support import (
    _default_lens_user_agent,
    _is_generic_user_agent,
    _sanitize_user_agent,
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
) -> _RequestLogger:
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
    return _RequestLogger(
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
    log_ctx: _RequestLogger,
    is_stream_body: bool,
    parsed_model: object | None = None,
    group_id: str | None = None,
    requested_group_name: str | None = None,
) -> tuple[RoutingPlan | None, RouteSelection | None, JSONResponse | None]:
    plan: RoutingPlan | None = None
    try:
        plan = await _resolve_routing_plan(
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
        await log_ctx.connecting(is_stream=is_stream_body)
        return plan, selection, None
    except CooldownRoutingError as exc:
        _log_cooldown_attempts(log_ctx, exc.cooled_targets)
        return (
            plan,
            None,
            await _routing_error_response(
                plan=plan,
                protocol=protocol,
                requested_model=requested_model,
                log_ctx=log_ctx,
                is_stream_body=is_stream_body,
                exc=exc,
            ),
        )
    except LookupError as exc:
        return (
            plan,
            None,
            await _routing_error_response(
                plan=plan,
                protocol=protocol,
                requested_model=requested_model,
                log_ctx=log_ctx,
                is_stream_body=is_stream_body,
                exc=exc,
            ),
        )


def _log_cooldown_attempts(
    log_ctx: _RequestLogger,
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
    log_ctx: _RequestLogger,
    is_stream_body: bool,
    exc: LookupError,
) -> JSONResponse:
    log_ctx.plan_route(
        requested_group_name=plan.requested_group_name if plan else requested_model,
        resolved_group_name=plan.resolved_group_name if plan else None,
    )
    await log_ctx.failed(
        status_code=503,
        error_message=str(exc),
        is_stream=is_stream_body,
    )
    return _protocol_error_response(
        protocol=protocol,
        status_code=503,
        error_type="routing_error",
        message="Gateway routing failed",
    )


async def _proxy_protocol(
    protocol: ProtocolKind,
    body: dict[str, Any],
    gateway_key: GatewayApiKey,
    inbound_user_agent: str | None = None,
    inbound_headers: Mapping[str, str] | None = None,
    path_suffix: str | None = None,
    multipart_files: list[tuple[str, tuple[str, bytes, str]]] | None = None,
) -> Response:
    started_at = perf_counter()
    channels, runtime = await asyncio.gather(
        app_state.channel_store.list_channels(),
        app_state.settings_repo.get_runtime_settings(),
    )
    deadline = _RequestDeadline(
        started_at,
        float(runtime["first_token_timeout_seconds"]),
        float(runtime["stream_idle_timeout_seconds"]),
    )
    _apply_router_runtime_settings(runtime)
    log_body_enabled = bool(runtime["relay_log_body_enabled"])
    request_content = _dump_log_json(body) if log_body_enabled else None
    inbound_ua = _sanitize_user_agent(inbound_user_agent)
    upstream_user_agent = (
        inbound_ua
        if inbound_ua and not _is_generic_user_agent(inbound_ua)
        else _default_lens_user_agent()
    )
    is_stream_body = bool(body.get("stream"))
    requested_model = body.get("model")
    if not isinstance(requested_model, str) or not requested_model.strip():
        log_ctx = await _create_pending_proxy_log_context(
            protocol=protocol,
            user_agent=upstream_user_agent,
            gateway_key=gateway_key,
            started_at=started_at,
            body=body,
            requested_group_name=None,
            is_stream=is_stream_body,
            request_content=request_content,
        )
        await log_ctx.failed(
            status_code=400,
            error_message="Request model is required",
            is_stream=is_stream_body,
            request_content=request_content,
        )
        return _protocol_error_response(
            protocol=protocol,
            status_code=400,
            error_type="missing_model",
            message="Request model is required",
        )
    requested_model = requested_model.strip()
    original_requested_model = requested_model
    try:
        parsed_model = parse_model_name(requested_model)
    except ValueError as exc:
        return _protocol_error_response(
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
    if not _gateway_key_allows_model(gateway_key, requested_model):
        error_message = "Gateway API key is not allowed to use this model"
        await log_ctx.failed(
            status_code=403,
            error_message=error_message,
            is_stream=is_stream_body,
            request_content=request_content,
        )
        return _protocol_error_response(
            protocol=protocol,
            status_code=403,
            error_type="forbidden_model",
            message=error_message,
        )
    try:
        plan, selection, routing_error = await _resolve_proxy_route(
            channels=channels,
            protocol=protocol,
            requested_model=requested_model,
            log_ctx=log_ctx,
            is_stream_body=is_stream_body,
            parsed_model=parsed_model,
            requested_group_name=original_requested_model,
        )
        if routing_error is not None:
            return routing_error
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
        route_plans = [(plan, selection)]
        seen_group_ids = {plan.resolved_group.id if plan.resolved_group else ""}
        if body_has_multimodal_content(body, protocol):
            for fallback_group_id in plan.fallback_group_ids:
                if fallback_group_id in seen_group_ids:
                    continue
                seen_group_ids.add(fallback_group_id)
                (
                    fallback_plan,
                    fallback_selection,
                    fallback_error,
                ) = await _resolve_proxy_route(
                    channels=channels,
                    protocol=protocol,
                    requested_model=requested_model,
                    log_ctx=log_ctx,
                    is_stream_body=is_stream_body,
                    parsed_model=parsed_model,
                    group_id=fallback_group_id,
                    requested_group_name=original_requested_model,
                )
                if fallback_error is not None:
                    failures.record(
                        fallback_error.body.decode(errors="replace"),
                        fallback_error.status_code,
                    )
                    continue
                if fallback_plan is not None and fallback_selection is not None:
                    route_plans.append((fallback_plan, fallback_selection))
        for current_plan, current_selection in route_plans:
            for target in [current_selection.primary, *current_selection.fallbacks]:
                if deadline.is_first_token_expired():
                    timeout_message = deadline.timeout_message(kind="first_token")
                    log_ctx.plan_route(
                        requested_group_name=current_plan.requested_group_name,
                        resolved_group_name=current_plan.resolved_group_name,
                    )
                    await log_ctx.failed(
                        status_code=504,
                        error_message=timeout_message,
                        is_stream=is_stream_body,
                    )
                    return _protocol_error_response(
                        protocol=protocol,
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

        failed_status_code, failed_error_type, failed_message = failures.final_failure()
        if not log_ctx.attempts:
            log_ctx.plan_route(
                requested_group_name=plan.requested_group_name,
                resolved_group_name=plan.resolved_group_name,
            )
            await log_ctx.failed(
                status_code=failed_status_code,
                error_message=failed_message,
                is_stream=is_stream_body,
            )
        return _protocol_error_response(
            protocol=protocol,
            status_code=failed_status_code,
            error_type=failed_error_type,
            message=failed_message,
        )
    except Exception as exc:
        log_ctx.plan_route(
            requested_group_name=plan.requested_group_name if plan else requested_model,
            resolved_group_name=plan.resolved_group_name if plan else None,
        )
        await log_ctx.failed(
            status_code=500,
            error_message=f"Unexpected proxy error: {type(exc).__name__}: {exc}",
            is_stream=is_stream_body,
        )
        raise
