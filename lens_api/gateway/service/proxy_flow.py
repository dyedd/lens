from __future__ import annotations

import asyncio
from collections.abc import Mapping
from time import perf_counter
from typing import Any

from fastapi import Response
from fastapi.responses import JSONResponse

from ...models import (
    ChannelConfig,
    GatewayApiKey,
    ProtocolKind,
    RequestLogLifecycleStatus,
)
from ..router import RouteSelection
from .runtime_types import (
    RoutingPlan,
    _RequestDeadline,
)
from .app_state import app_state
from .auth import _gateway_key_allows_model
from .error_responses import _protocol_error_response
from .errors import _apply_router_runtime_settings
from .upstream_support import (
    _default_lens_user_agent,
    _is_generic_user_agent,
    _normalize_user_agent,
)
from .payload_serialization import _dump_log_json
from .proxy_attempt import _try_target
from .request_logger import _RequestLogger
from .routing_plan import (
    _final_upstream_failure,
    _resolve_routing_plan,
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
    )


async def _resolve_proxy_route(
    *,
    channels: list[ChannelConfig],
    protocol: ProtocolKind,
    requested_model: str,
    log_ctx: _RequestLogger,
    upstream_user_agent: str,
    is_stream_body: bool,
) -> tuple[RoutingPlan | None, RouteSelection | None, JSONResponse | None]:
    plan: RoutingPlan | None = None
    try:
        plan = await _resolve_routing_plan(protocol, requested_model, channels)
        selection = app_state.router.select(
            channels,
            protocol,
            plan.resolved_group_name,
            strategy=plan.strategy,
            route_targets=plan.route_targets,
            use_model_matching=plan.use_model_matching,
            cursor_key=plan.cursor_key,
        )
        await log_ctx.update(
            requested_group_name=plan.requested_group_name,
            resolved_group_name=plan.resolved_group_name,
            upstream_model_name=None,
            channel=None,
            user_agent=upstream_user_agent,
            lifecycle_status=RequestLogLifecycleStatus.CONNECTING,
            status_code=None,
            success=False,
            is_stream=is_stream_body,
        )
        return plan, selection, None
    except LookupError as exc:
        return (
            plan,
            None,
            await _routing_error_response(
                plan=plan,
                protocol=protocol,
                requested_model=requested_model,
                log_ctx=log_ctx,
                upstream_user_agent=upstream_user_agent,
                is_stream_body=is_stream_body,
                exc=exc,
            ),
        )


async def _routing_error_response(
    *,
    plan: RoutingPlan | None,
    protocol: ProtocolKind,
    requested_model: str,
    log_ctx: _RequestLogger,
    upstream_user_agent: str,
    is_stream_body: bool,
    exc: LookupError,
) -> JSONResponse:
    await log_ctx.update(
        requested_group_name=plan.requested_group_name if plan else requested_model,
        resolved_group_name=plan.resolved_group_name if plan else None,
        upstream_model_name=None,
        channel=None,
        user_agent=upstream_user_agent,
        lifecycle_status=RequestLogLifecycleStatus.FAILED,
        status_code=503,
        success=False,
        is_stream=is_stream_body,
        error_message=str(exc),
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
    inbound_ua = _normalize_user_agent(inbound_user_agent)
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
        await log_ctx.update(
            requested_group_name=None,
            resolved_group_name=None,
            upstream_model_name=None,
            channel=None,
            user_agent=upstream_user_agent,
            lifecycle_status=RequestLogLifecycleStatus.FAILED,
            status_code=400,
            success=False,
            is_stream=is_stream_body,
            first_token_latency_ms=0,
            request_content=request_content,
            error_message="Request model is required",
        )
        return _protocol_error_response(
            protocol=protocol,
            status_code=400,
            error_type="missing_model",
            message="Request model is required",
        )
    requested_model = requested_model.strip()
    plan: RoutingPlan | None = None
    log_ctx = await _create_pending_proxy_log_context(
        protocol=protocol,
        user_agent=upstream_user_agent,
        gateway_key=gateway_key,
        started_at=started_at,
        body=body,
        requested_group_name=requested_model,
        is_stream=is_stream_body,
        request_content=request_content,
    )
    if not _gateway_key_allows_model(gateway_key, requested_model):
        error_message = "Gateway API key is not allowed to use this model"
        await log_ctx.update(
            requested_group_name=requested_model,
            resolved_group_name=None,
            upstream_model_name=None,
            channel=None,
            user_agent=upstream_user_agent,
            lifecycle_status=RequestLogLifecycleStatus.FAILED,
            status_code=403,
            success=False,
            is_stream=is_stream_body,
            first_token_latency_ms=0,
            request_content=request_content,
            error_message=error_message,
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
            upstream_user_agent=upstream_user_agent,
            is_stream_body=is_stream_body,
        )
        if routing_error is not None:
            return routing_error
        if plan is None or selection is None:
            raise RuntimeError("Routing plan was not resolved")

        errors: list[str] = []
        failure_status_codes: list[int | None] = []
        for target in [selection.primary, *selection.fallbacks]:
            if deadline.is_first_token_expired():
                timeout_message = deadline.timeout_message(kind="first_token")
                await log_ctx.update(
                    requested_group_name=plan.requested_group_name,
                    resolved_group_name=plan.resolved_group_name,
                    upstream_model_name=None,
                    channel=None,
                    user_agent=upstream_user_agent,
                    lifecycle_status=RequestLogLifecycleStatus.FAILED,
                    status_code=504,
                    success=False,
                    is_stream=is_stream_body,
                    error_message=timeout_message,
                )
                return _protocol_error_response(
                    protocol=protocol,
                    status_code=504,
                    error_type="gateway_timeout",
                    message=timeout_message,
                )
            if not app_state.router.is_target_available(target):
                continue
            response = await _try_target(
                target=target,
                protocol=protocol,
                body=body,
                runtime=runtime,
                upstream_user_agent=upstream_user_agent,
                inbound_headers=inbound_headers,
                plan=plan,
                log_ctx=log_ctx,
                errors=errors,
                failure_status_codes=failure_status_codes,
                deadline=deadline,
                path_suffix=path_suffix,
                multipart_files=multipart_files,
            )
            if response is not None:
                return response

        failed_status_code, failed_error_type, failed_message = _final_upstream_failure(
            errors, failure_status_codes
        )
        return _protocol_error_response(
            protocol=protocol,
            status_code=failed_status_code,
            error_type=failed_error_type,
            message=failed_message,
        )
    except Exception as exc:
        await log_ctx.update(
            requested_group_name=plan.requested_group_name if plan else requested_model,
            resolved_group_name=plan.resolved_group_name if plan else None,
            upstream_model_name=None,
            channel=None,
            user_agent=upstream_user_agent,
            lifecycle_status=RequestLogLifecycleStatus.FAILED,
            status_code=500,
            success=False,
            is_stream=is_stream_body,
            error_message=f"Unexpected proxy error: {type(exc).__name__}: {exc}",
        )
        raise
