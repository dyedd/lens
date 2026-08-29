from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from time import perf_counter

from ...models.channels import ChannelConfig
from ...models.model_groups import ModelGroupItemState
from ...models.protocols import ProtocolKind, RoutingStrategy
from ..converters import can_reach_protocol
from ..router import RouteTarget
from .app_state import app_state
from .runtime_types import RoutingPlan, _GatewayTimeoutError


async def _resolve_routing_plan(
    protocol: ProtocolKind,
    requested_model: str,
    channels: list[ChannelConfig],
    *,
    parsed_model: object | None = None,
) -> RoutingPlan:
    matched_group = await app_state.group_repo.find_group_by_name(
        protocol.value, requested_model, channels=channels
    )
    if matched_group is None or protocol not in matched_group.client_protocols:
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
        if protocol not in resolved_group.client_protocols:
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
    if resolved_group.strategy == RoutingStrategy.FAILOVER:
        targets_by_site: dict[str, list[RouteTarget]] = {}
        for target in route_targets:
            targets_by_site.setdefault(target.channel.site_id, []).append(target)
        route_targets = [
            target for targets in targets_by_site.values() for target in targets
        ]
    return RoutingPlan(
        requested_group_name=matched_group.name,
        resolved_group_name=resolved_group.name,
        requested_group=matched_group,
        resolved_group=resolved_group,
        strategy=resolved_group.strategy,
        route_targets=route_targets,
        use_model_matching=False,
        cursor_key=f"{protocol.value}:{resolved_group.id}",
        parsed_model=parsed_model,
    )


def _elapsed_ms(started_at: float) -> int:
    return max(int((perf_counter() - started_at) * 1000), 0)


@asynccontextmanager
async def _gateway_timeout_scope(
    wait: float | None, *, timeout_message: str
) -> AsyncIterator[None]:
    """Bound a critical section without rewriting unrelated TimeoutError values."""
    if wait is None:
        yield
        return
    if wait <= 0:
        raise _GatewayTimeoutError(timeout_message)
    timeout_scope = asyncio.timeout(wait)
    try:
        async with timeout_scope:
            yield
    except TimeoutError as exc:
        if not timeout_scope.expired():
            raise
        raise _GatewayTimeoutError(timeout_message) from exc


def _request_body_too_large_message(size: int, limit: int) -> str | None:
    bounded_limit = max(int(limit), 0)
    if bounded_limit <= 0 or size <= bounded_limit:
        return None
    return (
        f"Request body is {size} bytes, exceeds Lens limit "
        f"{bounded_limit} bytes. Split the context or increase "
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
