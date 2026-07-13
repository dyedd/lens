from __future__ import annotations

from ..shared import (
    AsyncSession,
    ChannelStatus,
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

        normalized_items = items or []
        if not normalized_items:
            return route_group

        from ..channel_store import ChannelStore

        channel_store = ChannelStore(self._session_factory)
        all_channels = await channel_store.list_channels()
        channel_by_id = {channel.id: channel for channel in all_channels}

        channel_ids = list(dict.fromkeys(item.channel_id for item in normalized_items))
        missing_channel_ids = [
            channel_id for channel_id in channel_ids if channel_id not in channel_by_id
        ]
        if missing_channel_ids:
            raise ValueError(f"Channels not found: {', '.join(missing_channel_ids)}")

        for item in normalized_items:
            channel = channel_by_id[item.channel_id]
            credential_ids_in_channel = {key.id for key in channel.keys}
            if item.credential_id not in credential_ids_in_channel:
                raise ValueError(
                    f"Credential not found in channel {item.channel_id}: "
                    f"{item.credential_id}"
                )

        for item in normalized_items:
            if not item.enabled:
                continue
            member_channel = channel_by_id[item.channel_id]
            if member_channel.status != ChannelStatus.ENABLED:
                raise ValueError(
                    f"Channel '{member_channel.name}' is disabled; "
                    "enable the channel before enabling its members"
                )
            enabled_credential_ids = {
                key.id for key in member_channel.keys if key.enabled
            }
            if item.credential_id not in enabled_credential_ids:
                raise ValueError(
                    "Credential is disabled; enable it before enabling this member"
                )

        invalid_channel_ids = [
            channel_id
            for channel_id in channel_ids
            if not any(
                can_reach_protocol(channel_by_id[channel_id].protocol, protocol)
                for protocol in normalized_protocols
            )
        ]
        if invalid_channel_ids:
            raise ValueError(
                "Channels cannot reach any selected protocol: "
                + ", ".join(invalid_channel_ids)
            )

        item_protocols = [
            channel_by_id[item.channel_id].protocol for item in normalized_items
        ]
        for protocol in normalized_protocols:
            if not any(
                can_reach_protocol(item_protocol, protocol)
                for item_protocol in item_protocols
            ):
                raise ValueError(
                    f"Protocol {protocol.value} has no reachable channel in group items"
                )

        model_names_by_channel: dict[str, set[tuple[str, str]]] = {}
        for channel_id in channel_ids:
            channel = channel_by_id.get(channel_id)
            if channel:
                model_names_by_channel[channel_id] = {
                    (model.credential_id, model.model_name) for model in channel.models
                }

        for item in normalized_items:
            channel_models = model_names_by_channel.get(item.channel_id, set())
            target = (item.credential_id, item.model_name)
            if target not in channel_models:
                raise ValueError(
                    f"Model not found in channel {item.channel_id} credential={item.credential_id}: {item.model_name}"
                )

        return route_group
