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


def _effective_user_agent_from_headers(
    headers: Mapping[str, str], fallback: str
) -> str:
    for name, value in headers.items():
        if name.lower() == "user-agent":
            return _normalize_user_agent(value)
    return fallback
