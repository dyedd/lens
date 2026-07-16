from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from time import perf_counter

from ...models import ChannelConfig, ModelGroupItemState, ProtocolKind
from ..converters import can_reach_protocol
from ..router import RouteTarget
from .app_state import app_state
from .routing_request import (
    _apply_deepseek_thinking_compat,
    _apply_global_param_override,
    _apply_param_override,
    _extract_request_reasoning_effort,
    _is_deepseek_thinking_target,
    _prepare_upstream_body,
)
from .runtime_types import RoutingPlan, _RequestDeadline


async def _resolve_routing_plan(
    protocol: ProtocolKind, requested_model: str, channels: list[ChannelConfig]
) -> RoutingPlan:
    matched_group = await app_state.group_repo.find_group_by_name(
        protocol.value, requested_model, channels=channels
    )
    if matched_group is None or protocol not in matched_group.protocols:
        raise LookupError(f"No model group matched {requested_model}")

    resolved_group = matched_group
    if matched_group.route_group_id.strip():
        try:
            resolved_group = await app_state.group_repo.get_group(
                matched_group.route_group_id, channels=channels
            )
        except KeyError as exc:
            raise LookupError(
                f"Route target model group not found: {matched_group.route_group_id}"
            ) from exc
        if resolved_group.route_group_id.strip():
            raise LookupError(
                f"Route target must be an execution group: {resolved_group.name}"
            )
        if protocol not in resolved_group.protocols:
            raise LookupError(f"No model group matched {requested_model}")

    channel_map = {channel.id: channel for channel in channels}
    route_targets: list[RouteTarget] = []
    for item in resolved_group.items:
        if (
            item.state != ModelGroupItemState.READY
            or item.protocol is None
            or not can_reach_protocol(item.protocol, protocol)
        ):
            continue
        channel = channel_map.get(item.channel_id)
        if channel is None:
            continue
        route_targets.append(
            RouteTarget(
                channel=channel,
                model_name=item.model_name,
                credential_id=item.credential_id,
                credential_name=item.credential_name or None,
            )
        )
    return RoutingPlan(
        requested_group_name=matched_group.name,
        resolved_group_name=resolved_group.name,
        requested_group=matched_group,
        resolved_group=resolved_group,
        strategy=resolved_group.strategy,
        route_targets=route_targets,
        use_model_matching=False,
        cursor_key=f"{protocol.value}:{resolved_group.id}",
    )


def _elapsed_ms(started_at: float) -> int:
    return max(int((perf_counter() - started_at) * 1000), 0)


@asynccontextmanager
async def _deadline_scope(deadline: _RequestDeadline) -> AsyncIterator[None]:
    remaining = deadline.remaining_seconds()
    if remaining is None:
        yield
        return
    if remaining <= 0:
        raise TimeoutError(deadline.timeout_message())
    async with asyncio.timeout(remaining):
        yield


def _request_body_too_large_message(size: int, limit: int) -> str | None:
    normalized_limit = max(int(limit), 0)
    if normalized_limit <= 0 or size <= normalized_limit:
        return None
    return (
        f"Request body is {size} bytes, exceeds Lens limit "
        f"{normalized_limit} bytes. Split the context or increase "
        "the maximum request body size in Settings."
    )


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
    return 502, "upstream_error", "All upstream channels failed"


def _is_request_too_large_error(status_code: int | None, message: str) -> bool:
    if status_code != 413:
        return False
    normalized = message.lower()
    return (
        "request body exceeds" in normalized
        or "request_too_large" in normalized
        or "too large" in normalized
        or "exceeds lens limit" in normalized
    )
