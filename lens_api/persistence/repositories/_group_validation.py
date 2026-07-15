from __future__ import annotations

from ...core.model_group_status import (
    build_model_group_channel_lookups,
    evaluate_model_group_item,
    model_group_item_key,
)
from ...models import (
    ModelGroupItemReason,
    ModelGroupItemState,
    ModelGroupItemView,
)
from ..shared import (
    AsyncSession,
    ChannelConfig,
    ModelGroupEntity,
    ModelGroupItemInput,
    ProtocolKind,
    _normalize_group_protocols,
    _parse_group_protocols,
    can_reach_protocol,
    select,
)


class _GroupValidationMixin:
    async def _validate_group_payload(
        self,
        session: AsyncSession,
        name: str,
        protocols: list[ProtocolKind],
        route_group_id: str = "",
        items: list[ModelGroupItemInput] | None = None,
        exclude_group_id: str | None = None,
        *,
        channels: list[ChannelConfig],
        existing_items: list[ModelGroupItemView] | None = None,
        existing_protocols: list[ProtocolKind] | None = None,
    ) -> ModelGroupEntity | None:
        normalized_name = name.strip()
        if not normalized_name:
            raise ValueError("Model group name is required")
        normalized_protocols = _normalize_group_protocols(protocols)

        result = await session.execute(
            select(ModelGroupEntity.id)
            .where(ModelGroupEntity.name == normalized_name)
            .limit(1)
        )
        existing_id = result.scalar_one_or_none()
        if existing_id is not None and existing_id != exclude_group_id:
            raise ValueError(f"Model group already exists: {normalized_name}")

        normalized_route_group_id = route_group_id.strip()
        route_group: ModelGroupEntity | None = None
        if normalized_route_group_id:
            if (
                exclude_group_id is not None
                and normalized_route_group_id == exclude_group_id
            ):
                raise ValueError("Model group cannot route to itself")
            route_group = await session.get(ModelGroupEntity, normalized_route_group_id)
            if route_group is None:
                raise ValueError(
                    f"Route target model group not found: {normalized_route_group_id}"
                )
            route_group_protocols = set(_parse_group_protocols(route_group))
            missing_protocols = [
                protocol
                for protocol in normalized_protocols
                if protocol not in route_group_protocols
            ]
            if missing_protocols:
                missing = ", ".join(protocol.value for protocol in missing_protocols)
                raise ValueError(
                    f"Route target protocols must cover source protocols: {missing}"
                )
            if route_group.route_group_id.strip():
                raise ValueError(
                    f"Route target must be an execution group: {route_group.name}"
                )

        if items is None:
            return route_group

        seen_keys: set[tuple[str, str, str]] = set()
        for item in items:
            item_key = model_group_item_key(item)
            if item_key in seen_keys:
                raise ValueError(
                    "Duplicate model group member: "
                    f"channel={item.channel_id} credential={item.credential_id} "
                    f"model={item.model_name}"
                )
            seen_keys.add(item_key)

        channels_by_id = build_model_group_channel_lookups(channels)
        previous_by_key = {
            model_group_item_key(item): item for item in existing_items or []
        }
        evaluated_items = [
            (
                item,
                evaluate_model_group_item(item, channels_by_id, normalized_protocols),
            )
            for item in items
        ]

        for item, evaluation in evaluated_items:
            previous = previous_by_key.get(model_group_item_key(item))
            is_new = previous is None
            is_being_enabled = bool(
                item.enabled and previous is not None and not previous.enabled
            )
            if not is_new and not is_being_enabled:
                continue
            blocking_reason = next(
                (
                    reason
                    for reason in evaluation.reasons
                    if reason != ModelGroupItemReason.MANUAL_DISABLED
                ),
                None,
            )
            if blocking_reason is not None:
                self._raise_group_item_error(item, blocking_reason)

        previous_enabled_by_key = {
            model_group_item_key(item): item.enabled for item in existing_items or []
        }
        next_enabled_by_key = {
            model_group_item_key(item): item.enabled for item, _ in evaluated_items
        }
        should_validate_coverage = (
            existing_protocols is None
            or set(normalized_protocols) != set(existing_protocols)
            or next_enabled_by_key != previous_enabled_by_key
        )
        has_enabled_items = any(item.enabled for item, _ in evaluated_items)
        enabled_evaluations = [
            evaluation
            for item, evaluation in evaluated_items
            if item.enabled and evaluation.state != ModelGroupItemState.INVALID
        ]
        if should_validate_coverage and has_enabled_items:
            for protocol in normalized_protocols:
                if not any(
                    evaluation.protocol is not None
                    and can_reach_protocol(evaluation.protocol, protocol)
                    for evaluation in enabled_evaluations
                ):
                    raise ValueError(
                        f"Protocol {protocol.value} has no reachable channel "
                        "in group items"
                    )

        return route_group

    @staticmethod
    def _raise_group_item_error(
        item: ModelGroupItemInput, reason: ModelGroupItemReason
    ) -> None:
        reason_label = f"{reason.value}: "
        if reason == ModelGroupItemReason.CHANNEL_NOT_FOUND:
            raise ValueError(f"{reason_label}Channels not found: {item.channel_id}")
        if reason == ModelGroupItemReason.PROTOCOL_UNREACHABLE:
            raise ValueError(
                f"{reason_label}Channels cannot reach any selected protocol: "
                f"{item.channel_id}"
            )
        if reason == ModelGroupItemReason.CHANNEL_DISABLED:
            raise ValueError(
                f"{reason_label}Channel '{item.channel_id}' is disabled; "
                "enable it before "
                "adding this member"
            )
        if reason == ModelGroupItemReason.CREDENTIAL_NOT_FOUND:
            raise ValueError(
                f"{reason_label}Credential not found in channel {item.channel_id}: "
                f"{item.credential_id}"
            )
        if reason == ModelGroupItemReason.CREDENTIAL_DISABLED:
            raise ValueError(
                f"{reason_label}Credential is disabled; enable it before "
                "adding this member"
            )
        if reason == ModelGroupItemReason.MODEL_NOT_FOUND:
            raise ValueError(
                f"{reason_label}Model not found in channel {item.channel_id} "
                f"credential={item.credential_id}: {item.model_name}"
            )
        if reason == ModelGroupItemReason.MODEL_DISABLED:
            raise ValueError(
                f"{reason_label}Model is disabled in channel {item.channel_id} "
                f"credential={item.credential_id}: {item.model_name}"
            )
