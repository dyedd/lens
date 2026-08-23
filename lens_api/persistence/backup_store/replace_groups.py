from __future__ import annotations

from .shared import (
    AsyncSession,
    ConfigBackupCronjob,
    ConfigBackupGatewayApiKey,
    ConfigBackupRequestLog,
    ConfigBackupStatsSnapshot,
    CronjobEntity,
    EXPORTABLE_SETTING_KEYS,
    GatewayApiKeyEntity,
    ImportedStatsDailyEntity,
    ImportedStatsTotalEntity,
    ModelGroup,
    ModelGroupEntity,
    ModelGroupItem,
    ModelGroupItemEntity,
    ModelPriceEntity,
    ModelPriceItem,
    OverviewModelDailyStatsEntity,
    ProtocolKind,
    RequestLogDailyStatsEntity,
    RequestLogEntity,
    RequestLogLifecycleStatus,
    SETTING_MODEL_PRICE_LAST_SYNC_AT,
    SETTING_TIME_ZONE,
    SettingEntity,
    SettingItem,
    SiteBaseUrlEntity,
    SiteConfig,
    SiteCredentialEntity,
    SiteDiscoveredModelEntity,
    SiteEntity,
    SiteProtocolConfigEntity,
    UTC,
    _extract_protocol_config_id,
    _parse_runtime_channel_protocol,
    _resolve_group_item_channel_id,
    _runtime_channel_id,
    datetime,
    delete,
    encode_weekdays,
    json,
    next_cronjob_run_at,
    normalize_cronjob_schedule,
    normalize_model_key,
    resolve_time_zone,
)
from .value_parsing import parse_backup_datetime, parse_optional_datetime


async def _replace_groups(
    self,
    session: AsyncSession,
    groups: list[ModelGroup],
    *,
    available_protocol_config_ids: set[str],
    protocols_by_config_id: dict[str, list[ProtocolKind]],
    model_keys: set[tuple[str, str, str]],
) -> None:
    await session.execute(delete(ModelGroupItemEntity))
    await session.execute(delete(ModelGroupEntity))

    group_ids = {group.id for group in groups}
    seen_group_names: set[str] = set()
    seen_group_ids: set[str] = set()

    groups_by_id = {group.id: group for group in groups}
    for group in groups:
        is_synced_group = bool(group.sync_filter_mode.value)
        if group.id in seen_group_ids:
            raise ValueError(f"Duplicate group id in backup: {group.id}")
        seen_group_ids.add(group.id)

        if group.name in seen_group_names:
            raise ValueError(f"Duplicate model group name in backup: {group.name}")
        seen_group_names.add(group.name)

        if group.route_group_id and group.route_group_id not in group_ids:
            raise ValueError(
                f"Referenced route group not found: {group.route_group_id}"
            )
        if group.route_group_id:
            route_group = groups_by_id[group.route_group_id]
            if route_group.route_group_id:
                raise ValueError(
                    f"Route target must be an execution group: {route_group.name}"
                )

        resolved_items: list[tuple[int, ModelGroupItem, str]] = []
        resolved_item_keys: set[tuple[str, str, str]] = set()

        for index, item in enumerate(group.items):
            protocol_config_id = _extract_protocol_config_id(
                item.channel_id, available_protocol_config_ids
            )
            if (
                is_synced_group
                and protocol_config_id not in available_protocol_config_ids
            ):
                raise ValueError(
                    f"Model group channel not found in backup sites: {item.channel_id}"
                )
            resolved_channel_id = (
                _resolve_group_item_channel_id(
                    item.channel_id,
                    known_protocol_config_ids=available_protocol_config_ids,
                    protocols_by_config_id=protocols_by_config_id,
                )
                if protocol_config_id in available_protocol_config_ids
                else item.channel_id
            )
            if _parse_runtime_channel_protocol(resolved_channel_id) is None:
                raise ValueError(
                    f"Model group channel not found in backup sites: {item.channel_id}"
                )
            target = (resolved_channel_id, item.credential_id, item.model_name)
            if target in resolved_item_keys:
                raise ValueError(
                    "Duplicate model group member in backup "
                    f"{group.name}: channel={resolved_channel_id} "
                    f"credential={item.credential_id} model={item.model_name}"
                )
            resolved_item_keys.add(target)
            if is_synced_group and target not in model_keys:
                raise ValueError(
                    f"Model group model not found in backup channel {item.channel_id} credential={item.credential_id}: {item.model_name}"
                )
            resolved_items.append((index, item, resolved_channel_id))

        session.add(
            ModelGroupEntity(
                id=group.id,
                name=group.name,
                strategy=group.strategy.value,
                route_group_id=group.route_group_id,
                sync_filter_mode=group.sync_filter_mode.value,
                sync_filter_query=group.sync_filter_query,
                param_override=group.param_override,
                headers_json=json.dumps(group.headers, ensure_ascii=True),
            )
        )

        for index, item, resolved_channel_id in resolved_items:
            session.add(
                ModelGroupItemEntity(
                    group_id=group.id,
                    channel_id=resolved_channel_id,
                    credential_id=item.credential_id,
                    model_name=item.model_name,
                    enabled=1 if item.enabled else 0,
                    sort_order=item.sort_order if item.sort_order >= 0 else index,
                )
            )
