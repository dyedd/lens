from __future__ import annotations

from ....core.errors import ResourceNotFoundError, RoutingError
from ....core.model_name_parser import ParsedModelName
from ....models.channels import ChannelConfig
from ....models.model_groups import ModelGroupItemState
from ....models.protocols import ProtocolKind
from ....persistence.repositories.groups_repository import ModelGroupRepository
from ...converters import can_reach_protocol
from ...router import RouteTarget
from ..runtime_types import RoutingPlan


async def resolve_routing_plan(
    protocol: ProtocolKind,
    requested_model: str,
    channels: list[ChannelConfig],
    *,
    group_repo: ModelGroupRepository,
    parsed_model: ParsedModelName | None = None,
    group_id: str | None = None,
    requested_group_name: str | None = None,
) -> RoutingPlan:
    matched_group = (
        await group_repo.get_group(group_id, channels=channels)
        if group_id is not None
        else await group_repo.find_group_by_name(
            protocol.value, requested_model, channels=channels
        )
    )
    if matched_group is None or protocol not in matched_group.client_protocols:
        raise RoutingError(f"No model group matched {requested_model}")

    resolved_group = matched_group
    if matched_group.route_group_id.strip():
        try:
            resolved_group = await group_repo.get_group(
                matched_group.route_group_id, channels=channels
            )
        except ResourceNotFoundError as exc:
            raise RoutingError(
                f"Route target model group not found: {matched_group.route_group_id}"
            ) from exc
        if resolved_group.route_group_id.strip():
            raise RoutingError(
                f"Route target must be an execution group: {resolved_group.name}"
            )
        if protocol not in resolved_group.client_protocols:
            raise RoutingError(f"No model group matched {requested_model}")

    channel_map = {channel.id: channel for channel in channels}
    # The group default only covers members without a channel model value.
    group_context_window = resolved_group.context_window
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
                context_window=(
                    item.context_window
                    if item.context_window is not None
                    else group_context_window
                ),
            )
        )
    return RoutingPlan(
        requested_group_name=requested_group_name or matched_group.name,
        resolved_group_name=resolved_group.name,
        requested_group=matched_group,
        resolved_group=resolved_group,
        strategy=resolved_group.strategy,
        route_targets=route_targets,
        use_model_matching=False,
        cursor_key=f"{protocol.value}:{resolved_group.id}",
        parsed_model=parsed_model,
        fallback_group_ids=list(resolved_group.fallback_group_ids),
    )
