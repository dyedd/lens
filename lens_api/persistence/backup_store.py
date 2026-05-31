import json
from datetime import UTC, datetime

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from ..core.model_prices import normalize_model_key
from ..core.time_zone import normalize_time_zone, resolve_time_zone
from ..gateway.converters import can_reach_protocol
from ..models import (
    ConfigBackupDump,
    ConfigBackupGatewayApiKey,
    ConfigBackupImportedStatsDaily,
    ConfigBackupImportedStatsTotal,
    ConfigBackupOverviewModelDailyStat,
    ConfigBackupRequestLog,
    ConfigBackupRequestLogDailyStat,
    ConfigBackupCronjob,
    ConfigBackupStatsSnapshot,
    ConfigImportResult,
    ModelGroup,
    ModelPriceItem,
    ProtocolKind,
    RequestLogAttempt,
    RequestLogLifecycleStatus,
    SettingItem,
    SiteConfig,
)
from .domain_store import (
    SETTING_CIRCUIT_BREAKER_COOLDOWN,
    SETTING_CIRCUIT_BREAKER_MAX_COOLDOWN,
    SETTING_CIRCUIT_BREAKER_THRESHOLD,
    SETTING_CORS_ALLOW_ORIGINS,
    SETTING_HEALTH_MIN_SAMPLES,
    SETTING_HEALTH_PENALTY_WEIGHT,
    SETTING_HEALTH_WINDOW_SECONDS,
    SETTING_MODEL_LIST_COMPAT_MODE_ENABLED,
    SETTING_PROXY_URL,
    SETTING_RELAY_LOG_KEEP_ENABLED,
    SETTING_RELAY_LOG_KEEP_PERIOD,
    SETTING_SITE_LOGO_URL,
    SETTING_SITE_NAME,
    SETTING_TIME_ZONE,
    SETTING_MODEL_PRICE_LAST_SYNC_AT,
)
from .entities import (
    GatewayApiKeyEntity,
    ImportedStatsDailyEntity,
    ImportedStatsTotalEntity,
    ModelGroupEntity,
    ModelGroupItemEntity,
    ModelPriceEntity,
    OverviewModelDailyStatsEntity,
    RequestLogDailyStatsEntity,
    RequestLogEntity,
    CronjobEntity,
    SettingEntity,
    SiteBaseUrlEntity,
    SiteCredentialEntity,
    SiteDiscoveredModelEntity,
    SiteEntity,
    SiteProtocolConfigEntity,
)
from .cronjob_store import (
    encode_weekdays,
    next_cronjob_run_at,
    normalize_cronjob_schedule,
)

BACKUP_DUMP_VERSION = 2
SETTING_STATS_LAST_PERSIST_AT = "stats_last_persist_at"


def _extract_combo_id(channel_id: str, known_combo_ids: set[str]) -> str:
    if channel_id in known_combo_ids:
        return channel_id
    for protocol in ProtocolKind:
        suffix = f"_{protocol.value}"
        if channel_id.endswith(suffix):
            candidate = channel_id[: -len(suffix)]
            if candidate in known_combo_ids:
                return candidate
    return channel_id


def _parse_channel_protocol(channel_id: str) -> ProtocolKind | None:
    for protocol in ProtocolKind:
        if channel_id.endswith(f"_{protocol.value}"):
            return protocol
    return None


def _composite_channel_id(combo_id: str, protocol: ProtocolKind) -> str:
    return f"{combo_id}_{protocol.value}"


def _resolve_group_item_channel_id(
    channel_id: str,
    group_protocols: list[ProtocolKind],
    *,
    known_combo_ids: set[str],
    combo_protocols: dict[str, list[ProtocolKind]],
) -> str:
    combo_id = _extract_combo_id(channel_id, known_combo_ids)
    if combo_id not in known_combo_ids:
        return channel_id

    parsed_protocol = _parse_channel_protocol(channel_id)
    available_protocols = combo_protocols.get(combo_id, [])
    if parsed_protocol in available_protocols:
        return _composite_channel_id(combo_id, parsed_protocol)

    for protocol in group_protocols:
        if protocol in available_protocols:
            return _composite_channel_id(combo_id, protocol)

    if available_protocols:
        return _composite_channel_id(combo_id, available_protocols[0])
    return channel_id


def _upgrade_backup_format(data: dict) -> dict:
    """将旧版备份 JSON 升级为新版格式，在 Pydantic 解析前执行。

    处理：旧版 SiteProtocolConfig 含 protocol 字段，新版改为 SiteBaseUrl.compatible_protocols。
    """
    for site in data.get("sites", []):
        url_protocols: dict[str, list[str]] = {}
        for protocol_config in site.get("protocols", []):
            if old_protocol := protocol_config.pop("protocol", None):
                base_url_id = protocol_config.get("base_url_id", "")
                if base_url_id:
                    if base_url_id not in url_protocols:
                        url_protocols[base_url_id] = []
                    if old_protocol not in url_protocols[base_url_id]:
                        url_protocols[base_url_id].append(old_protocol)
        for base_url in site.get("base_urls", []):
            buid = base_url.get("id", "")
            if not base_url.get("compatible_protocols") and buid in url_protocols:
                base_url["compatible_protocols"] = sorted(url_protocols[buid])
    for group in data.get("groups", []):
        if not isinstance(group, dict):
            continue
        old_protocol = group.pop("protocol", None)
        if "protocols" not in group and old_protocol is not None:
            group["protocols"] = [old_protocol]
        if not group.get("protocols"):
            raise ValueError(
                f"Backup model group missing protocols: {group.get('name', '')}"
            )
    return data

EXPORTABLE_SETTING_KEYS = (
    SETTING_PROXY_URL,
    SETTING_CORS_ALLOW_ORIGINS,
    SETTING_RELAY_LOG_KEEP_ENABLED,
    SETTING_RELAY_LOG_KEEP_PERIOD,
    SETTING_CIRCUIT_BREAKER_THRESHOLD,
    SETTING_CIRCUIT_BREAKER_COOLDOWN,
    SETTING_CIRCUIT_BREAKER_MAX_COOLDOWN,
    SETTING_HEALTH_WINDOW_SECONDS,
    SETTING_HEALTH_PENALTY_WEIGHT,
    SETTING_HEALTH_MIN_SAMPLES,
    SETTING_MODEL_LIST_COMPAT_MODE_ENABLED,
    SETTING_SITE_NAME,
    SETTING_SITE_LOGO_URL,
    SETTING_TIME_ZONE,
)


class BackupStore:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    @staticmethod
    def parse_dump(payload: bytes) -> "ConfigBackupDump":
        """解析备份文件字节，在 Pydantic 验证前升级旧版格式。"""
        try:
            data = json.loads(payload)
            data = _upgrade_backup_format(data)
        except json.JSONDecodeError as exc:
            raise ValueError("Invalid backup file") from exc
        try:
            return ConfigBackupDump.model_validate(data)
        except ValueError as exc:
            raise ValueError("Invalid backup file") from exc

    async def export_dump(
        self,
        *,
        lens_version: str,
        include_request_logs: bool,
        include_gateway_api_keys: bool,
    ) -> ConfigBackupDump:
        async with self._session_factory() as session:
            settings_rows = (
                (
                    await session.execute(
                        select(SettingEntity)
                        .where(SettingEntity.key.in_(EXPORTABLE_SETTING_KEYS))
                        .order_by(SettingEntity.key.asc())
                    )
                )
                .scalars()
                .all()
            )
            sites = await self._load_sites(session)
            groups = await self._load_groups(session)
            model_prices = await self._load_model_prices(session)
            cronjobs = await self._load_cronjobs(session)
            stats = await self._load_stats(session)
            gateway_api_keys = (
                await self._load_gateway_api_keys(session)
                if include_gateway_api_keys
                else []
            )
            request_logs = (
                await self._load_request_logs(session) if include_request_logs else []
            )

        return ConfigBackupDump(
            version=BACKUP_DUMP_VERSION,
            exported_at=datetime.now(UTC).isoformat(),
            lens_version=lens_version,
            include_request_logs=include_request_logs,
            include_gateway_api_keys=include_gateway_api_keys,
            settings=[
                SettingItem(key=item.key, value=item.value) for item in settings_rows
            ],
            sites=sites,
            groups=groups,
            model_prices=model_prices,
            cronjobs=cronjobs,
            stats=stats,
            gateway_api_keys=gateway_api_keys,
            request_logs=request_logs,
        )

    async def import_dump(self, dump: ConfigBackupDump) -> ConfigImportResult:
        if dump.version != BACKUP_DUMP_VERSION:
            raise ValueError(f"Unsupported backup version: {dump.version}")

        async with self._session_factory() as session:
            rows_affected: dict[str, int] = {}

            channel_ids, channel_protocols, available_model_keys = (
                await self._replace_sites(session, dump.sites)
            )
            rows_affected["sites"] = len(dump.sites)
            rows_affected["site_base_urls"] = sum(
                len(site.base_urls) for site in dump.sites
            )
            rows_affected["site_credentials"] = sum(
                len(site.credentials) for site in dump.sites
            )
            rows_affected["site_protocol_configs"] = sum(
                len(site.protocols) for site in dump.sites
            )
            rows_affected["site_models"] = sum(
                len(protocol.models)
                for site in dump.sites
                for protocol in site.protocols
            )

            await self._replace_groups(
                session,
                dump.groups,
                available_channel_ids=channel_ids,
                available_channel_protocols=channel_protocols,
                available_model_keys=available_model_keys,
            )
            rows_affected["model_groups"] = len(dump.groups)
            rows_affected["model_group_items"] = sum(
                len(group.items) for group in dump.groups
            )

            await self._replace_model_prices(session, dump.model_prices)
            rows_affected["model_prices"] = len(dump.model_prices)

            await self._replace_settings(session, dump.settings)
            rows_affected["settings"] = len(dump.settings)

            await self._replace_cronjobs(session, dump.cronjobs)
            rows_affected["cronjobs"] = len(dump.cronjobs)

            await self._replace_stats(session, dump.stats)
            rows_affected["imported_stats_total"] = (
                1 if dump.stats.imported_total is not None else 0
            )
            rows_affected["imported_stats_daily"] = len(dump.stats.imported_daily)
            rows_affected["request_log_daily_stats"] = len(dump.stats.request_daily)
            rows_affected["overview_model_daily_stats"] = len(dump.stats.model_daily)

            if dump.include_gateway_api_keys:
                await self._replace_gateway_api_keys(session, dump.gateway_api_keys)
                rows_affected["gateway_api_keys"] = len(dump.gateway_api_keys)

            if dump.include_request_logs:
                await self._replace_request_logs(session, dump.request_logs)
                rows_affected["request_logs"] = len(dump.request_logs)

            await session.commit()

        return ConfigImportResult(rows_affected=rows_affected)

    async def _replace_sites(
        self, session: AsyncSession, sites: list[SiteConfig]
    ) -> tuple[set[str], dict[str, list[ProtocolKind]], set[tuple[str, str, str]]]:
        # 旧备份兼容：若地址没有 compatible_protocols 但协议配置有 protocol，则反推
        for site in sites:
            url_protocols: dict[str, set] = {}
            for protocol_config in site.protocols:
                protocol_value = getattr(protocol_config, "protocol", None)
                if protocol_value is not None:
                    url_protocols.setdefault(protocol_config.base_url_id, set()).add(
                        protocol_value
                    )
            for base_url in site.base_urls:
                if not base_url.compatible_protocols and base_url.id in url_protocols:
                    base_url.compatible_protocols = sorted(
                        url_protocols[base_url.id], key=lambda p: p.value
                    )

        await session.execute(delete(SiteDiscoveredModelEntity))
        await session.execute(delete(SiteProtocolConfigEntity))
        await session.execute(delete(SiteCredentialEntity))
        await session.execute(delete(SiteBaseUrlEntity))
        await session.execute(delete(SiteEntity))

        site_ids: set[str] = set()
        site_names: set[str] = set()
        channel_ids: set[str] = set()
        channel_protocols: dict[str, list[ProtocolKind]] = {}
        credential_ids: set[str] = set()
        available_model_keys: set[tuple[str, str, str]] = set()
        base_url_ids: set[str] = set()
        model_ids: set[str] = set()

        for site in sites:
            if site.id in site_ids:
                raise ValueError(f"Duplicate site id in backup: {site.id}")
            if site.name in site_names:
                raise ValueError(f"Duplicate site name in backup: {site.name}")
            site_ids.add(site.id)
            site_names.add(site.name)

            session.add(SiteEntity(id=site.id, name=site.name))
            site_base_url_ids: set[str] = set()
            site_credential_ids: set[str] = set()

            for base_url in site.base_urls:
                if base_url.id in base_url_ids:
                    raise ValueError(f"Duplicate base url id in backup: {base_url.id}")
                base_url_ids.add(base_url.id)
                site_base_url_ids.add(base_url.id)
                session.add(
                    SiteBaseUrlEntity(
                        id=base_url.id,
                        site_id=site.id,
                        url=str(base_url.url),
                        name=base_url.name,
                        enabled=1 if base_url.enabled else 0,
                        sort_order=base_url.sort_order,
                        compatible_protocols_json=json.dumps(
                            [p.value for p in (base_url.compatible_protocols or [])],
                            ensure_ascii=True,
                        ),
                    )
                )

            for credential in site.credentials:
                if credential.id in credential_ids:
                    raise ValueError(
                        f"Duplicate credential id in backup: {credential.id}"
                    )
                credential_ids.add(credential.id)
                site_credential_ids.add(credential.id)
                session.add(
                    SiteCredentialEntity(
                        id=credential.id,
                        site_id=site.id,
                        name=credential.name,
                        api_key=credential.api_key,
                        enabled=1 if credential.enabled else 0,
                        sort_order=credential.sort_order,
                    )
                )

            for protocol in site.protocols:
                if protocol.id in channel_ids:
                    raise ValueError(f"Duplicate channel id in backup: {protocol.id}")
                channel_ids.add(protocol.id)
                if protocol.base_url_id not in site_base_url_ids:
                    raise ValueError(
                        f"Channel base url not found in backup site {site.name}: {protocol.base_url_id}"
                    )
                if (
                    protocol.credential_id
                    and protocol.credential_id not in site_credential_ids
                ):
                    raise ValueError(
                        f"Channel credential not found in backup site {site.name}: {protocol.credential_id}"
                    )
                session.add(
                    SiteProtocolConfigEntity(
                        id=protocol.id,
                        site_id=site.id,
                        name=protocol.name,
                        enabled=1 if protocol.enabled else 0,
                        headers_json=json.dumps(protocol.headers, ensure_ascii=True),
                        channel_proxy=protocol.channel_proxy,
                        param_override=protocol.param_override,
                        match_regex=protocol.match_regex,
                        base_url_id=protocol.base_url_id,
                        credential_id=protocol.credential_id,
                    )
                )

                base_url_protocols = next(
                    (
                        base_url.compatible_protocols
                        for base_url in site.base_urls
                        if base_url.id == protocol.base_url_id
                    ),
                    [],
                )
                channel_protocols[protocol.id] = list(base_url_protocols)

                for model in protocol.models:
                    if model.id in model_ids:
                        raise ValueError(
                            f"Duplicate discovered model id in backup: {model.id}"
                        )
                    model_ids.add(model.id)
                    if (
                        not model.credential_id
                        or model.credential_id not in site_credential_ids
                    ):
                        raise ValueError(
                            f"Discovered model credential not found in backup site {site.name}: {model.credential_id}"
                        )
                    if model.enabled:
                        for protocol_kind in channel_protocols[protocol.id]:
                            if model.protocol is None or model.protocol == protocol_kind:
                                available_model_keys.add(
                                    (
                                        _composite_channel_id(
                                            protocol.id, protocol_kind
                                        ),
                                        model.credential_id,
                                        model.model_name,
                                    )
                                )
                    session.add(
                        SiteDiscoveredModelEntity(
                            id=model.id,
                            protocol_config_id=protocol.id,
                            credential_id=model.credential_id,
                            model_name=model.model_name,
                            enabled=1 if model.enabled else 0,
                            sort_order=model.sort_order,
                            protocol=(model.protocol.value if model.protocol else None),
                        )
                    )

        return channel_ids, channel_protocols, available_model_keys

    async def _replace_groups(
        self,
        session: AsyncSession,
        groups: list[ModelGroup],
        *,
        available_channel_ids: set[str],
        available_channel_protocols: dict[str, list[ProtocolKind]],
        available_model_keys: set[tuple[str, str, str]],
    ) -> None:
        await session.execute(delete(ModelGroupItemEntity))
        await session.execute(delete(ModelGroupEntity))

        group_ids = {group.id for group in groups}
        seen_group_names: set[str] = set()
        seen_group_ids: set[str] = set()

        groups_by_id = {group.id: group for group in groups}
        for group in groups:
            if group.id in seen_group_ids:
                raise ValueError(f"Duplicate group id in backup: {group.id}")
            seen_group_ids.add(group.id)

            if group.name in seen_group_names:
                raise ValueError(f"Duplicate model group name in backup: {group.name}")
            seen_group_names.add(group.name)

            if not group.protocols:
                raise ValueError(f"Backup model group missing protocols: {group.name}")

            if group.route_group_id and group.route_group_id not in group_ids:
                raise ValueError(
                    f"Referenced route group not found: {group.route_group_id}"
                )
            if group.route_group_id:
                route_group = groups_by_id[group.route_group_id]
                route_protocols = set(route_group.protocols)
                missing_protocols = [
                    protocol
                    for protocol in group.protocols
                    if protocol not in route_protocols
                ]
                if missing_protocols:
                    missing = ", ".join(
                        protocol.value for protocol in missing_protocols
                    )
                    raise ValueError(
                        f"Route target protocols must cover source protocols: {missing}"
                    )
                if route_group.route_group_id:
                    raise ValueError(
                        f"Route target must be an execution group: {route_group.name}"
                    )

            resolved_items: list[tuple[int, object, str, ProtocolKind]] = []

            for index, item in enumerate(group.items):
                combo_id = _extract_combo_id(item.channel_id, available_channel_ids)
                if combo_id not in available_channel_ids:
                    raise ValueError(
                        f"Model group channel not found in backup sites: {item.channel_id}"
                    )
                resolved_channel_id = _resolve_group_item_channel_id(
                    item.channel_id,
                    group.protocols,
                    known_combo_ids=available_channel_ids,
                    combo_protocols=available_channel_protocols,
                )
                resolved_protocol = _parse_channel_protocol(resolved_channel_id)
                if resolved_protocol is None:
                    raise ValueError(
                        f"Model group channel not found in backup sites: {item.channel_id}"
                    )
                target = (resolved_channel_id, item.credential_id, item.model_name)
                if target not in available_model_keys:
                    raise ValueError(
                        f"Model group model not found in backup channel {item.channel_id} credential={item.credential_id}: {item.model_name}"
                    )
                resolved_items.append(
                    (index, item, resolved_channel_id, resolved_protocol)
                )

            if group.items and not group.route_group_id:
                for protocol in group.protocols:
                    if not any(
                        can_reach_protocol(item_protocol, protocol)
                        for _, _, _, item_protocol in resolved_items
                    ):
                        raise ValueError(
                            f"Protocol {protocol.value} has no reachable channel in group items"
                        )

            session.add(
                ModelGroupEntity(
                    id=group.id,
                    name=group.name,
                    protocols_json=json.dumps(
                        [protocol.value for protocol in group.protocols],
                        ensure_ascii=True,
                    ),
                    strategy=group.strategy.value,
                    route_group_id=group.route_group_id,
                    sync_filter_mode=group.sync_filter_mode.value,
                    sync_filter_query=group.sync_filter_query,
                )
            )

            for index, item, resolved_channel_id, _ in resolved_items:
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

    async def _replace_model_prices(
        self, session: AsyncSession, model_prices: list[ModelPriceItem]
    ) -> None:
        await session.execute(delete(ModelPriceEntity))
        await session.execute(
            delete(SettingEntity).where(
                SettingEntity.key == SETTING_MODEL_PRICE_LAST_SYNC_AT
            )
        )
        model_keys: set[str] = set()
        for item in model_prices:
            model_key = normalize_model_key(item.model_key)
            if not model_key:
                continue
            if model_key in model_keys:
                raise ValueError(f"Duplicate model price key in backup: {model_key}")
            model_keys.add(model_key)
            session.add(
                ModelPriceEntity(
                    model_key=model_key,
                    display_name=item.display_name or model_key,
                    input_price_per_million=item.input_price_per_million,
                    output_price_per_million=item.output_price_per_million,
                    cache_read_price_per_million=item.cache_read_price_per_million,
                    cache_write_price_per_million=item.cache_write_price_per_million,
                )
            )

    async def _replace_stats(
        self, session: AsyncSession, stats: ConfigBackupStatsSnapshot
    ) -> None:
        await session.execute(delete(ImportedStatsDailyEntity))
        await session.execute(delete(ImportedStatsTotalEntity))
        await session.execute(delete(RequestLogDailyStatsEntity))
        await session.execute(delete(OverviewModelDailyStatsEntity))
        await session.execute(
            delete(SettingEntity).where(
                SettingEntity.key == SETTING_STATS_LAST_PERSIST_AT
            )
        )

        if stats.imported_total is not None:
            session.add(
                ImportedStatsTotalEntity(
                    id=1,
                    input_token=stats.imported_total.input_token,
                    output_token=stats.imported_total.output_token,
                    input_cost=stats.imported_total.input_cost,
                    output_cost=stats.imported_total.output_cost,
                    wait_time=stats.imported_total.wait_time,
                    request_success=stats.imported_total.request_success,
                    request_failed=stats.imported_total.request_failed,
                )
            )

        imported_daily_dates: set[str] = set()
        for item in stats.imported_daily:
            if item.date in imported_daily_dates:
                raise ValueError(
                    f"Duplicate imported stats date in backup: {item.date}"
                )
            imported_daily_dates.add(item.date)
            session.add(
                ImportedStatsDailyEntity(
                    date=item.date,
                    input_token=item.input_token,
                    output_token=item.output_token,
                    input_cost=item.input_cost,
                    output_cost=item.output_cost,
                    wait_time=item.wait_time,
                    request_success=item.request_success,
                    request_failed=item.request_failed,
                )
            )

        request_daily_dates: set[str] = set()
        for item in stats.request_daily:
            if item.date in request_daily_dates:
                raise ValueError(f"Duplicate request stats date in backup: {item.date}")
            request_daily_dates.add(item.date)
            session.add(
                RequestLogDailyStatsEntity(
                    date=item.date,
                    request_count=item.request_count,
                    successful_requests=item.successful_requests,
                    failed_requests=item.failed_requests,
                    wait_time_ms=item.wait_time_ms,
                    input_tokens=item.input_tokens,
                    cache_read_input_tokens=item.cache_read_input_tokens,
                    cache_write_input_tokens=item.cache_write_input_tokens,
                    output_tokens=item.output_tokens,
                    total_tokens=item.total_tokens,
                    input_cost_usd=item.input_cost_usd,
                    output_cost_usd=item.output_cost_usd,
                    total_cost_usd=item.total_cost_usd,
                )
            )

        model_daily_keys: set[tuple[str, str]] = set()
        for item in stats.model_daily:
            key = (item.date, item.model)
            if key in model_daily_keys:
                raise ValueError(
                    f"Duplicate model stats row in backup: {item.date} {item.model}"
                )
            model_daily_keys.add(key)
            session.add(
                OverviewModelDailyStatsEntity(
                    date=item.date,
                    model=item.model,
                    requests=item.requests,
                    total_tokens=item.total_tokens,
                    total_cost_usd=item.total_cost_usd,
                )
            )

    async def _replace_settings(
        self, session: AsyncSession, settings: list[SettingItem]
    ) -> None:
        await session.execute(
            delete(SettingEntity).where(SettingEntity.key.in_(EXPORTABLE_SETTING_KEYS))
        )
        setting_keys: set[str] = set()
        for item in settings:
            if item.key not in EXPORTABLE_SETTING_KEYS:
                continue
            if item.key in setting_keys:
                raise ValueError(f"Duplicate setting key in backup: {item.key}")
            setting_keys.add(item.key)
            value = (
                normalize_time_zone(item.value)
                if item.key == SETTING_TIME_ZONE
                else item.value
            )
            session.add(SettingEntity(key=item.key, value=value))

    async def _replace_cronjobs(
        self, session: AsyncSession, cronjobs: list[ConfigBackupCronjob]
    ) -> None:
        task_ids: set[str] = set()
        now = datetime.now(UTC).replace(tzinfo=None)
        time_zone_setting = await session.get(SettingEntity, SETTING_TIME_ZONE)
        time_zone = resolve_time_zone(
            time_zone_setting.value if time_zone_setting is not None else None
        )
        for item in cronjobs:
            task_id = item.id.strip()
            if not task_id:
                continue
            if task_id in task_ids:
                raise ValueError(f"Duplicate cron job id in backup: {task_id}")
            task_ids.add(task_id)
            schedule = normalize_cronjob_schedule(
                schedule_type=item.schedule_type.value,
                interval_hours=item.interval_hours,
                run_at_time=item.run_at_time,
                weekdays=item.weekdays,
            )
            next_run_at = (
                next_cronjob_run_at(schedule, now=now, time_zone=time_zone)
                if item.enabled
                else None
            )

            entity = await session.get(CronjobEntity, task_id)
            if entity is None:
                session.add(
                    CronjobEntity(
                        id=task_id,
                        enabled=1 if item.enabled else 0,
                        schedule_type=schedule.schedule_type,
                        interval_hours=schedule.interval_hours,
                        run_at_time=schedule.run_at_time,
                        weekdays_json=encode_weekdays(schedule.weekdays),
                        status="idle" if item.enabled else "disabled",
                        last_error="",
                        next_run_at=next_run_at,
                        lease_owner="",
                        created_at=now,
                        updated_at=now,
                    )
                )
                continue

            entity.enabled = 1 if item.enabled else 0
            entity.schedule_type = schedule.schedule_type
            entity.interval_hours = schedule.interval_hours
            entity.run_at_time = schedule.run_at_time
            entity.weekdays_json = encode_weekdays(schedule.weekdays)
            entity.next_run_at = next_run_at
            if not entity.lease_owner:
                entity.status = "idle" if item.enabled else "disabled"
            entity.updated_at = now

    async def _replace_gateway_api_keys(
        self, session: AsyncSession, gateway_api_keys: list[ConfigBackupGatewayApiKey]
    ) -> None:
        await session.execute(delete(GatewayApiKeyEntity))
        seen_ids: set[str] = set()
        seen_keys: set[str] = set()
        now = datetime.now(UTC).replace(tzinfo=None)

        for item in gateway_api_keys:
            key_id = item.id.strip()
            api_key = item.api_key.strip()
            if not key_id:
                raise ValueError("Gateway API key id is required")
            if not api_key:
                raise ValueError("Gateway API key secret is required")
            if key_id in seen_ids:
                raise ValueError(f"Duplicate gateway API key id in backup: {key_id}")
            if api_key in seen_keys:
                raise ValueError("Duplicate gateway API key secret in backup")
            seen_ids.add(key_id)
            seen_keys.add(api_key)

            session.add(
                GatewayApiKeyEntity(
                    id=key_id,
                    remark=item.remark.strip(),
                    api_key=api_key,
                    enabled=1 if item.enabled else 0,
                    allowed_models_json=json.dumps(
                        item.allowed_models,
                        ensure_ascii=True,
                        separators=(",", ":"),
                    ),
                    max_cost_usd=max(item.max_cost_usd, 0.0),
                    expires_at=self._parse_optional_datetime(item.expires_at),
                    created_at=self._parse_optional_datetime(item.created_at) or now,
                    updated_at=self._parse_optional_datetime(item.updated_at) or now,
                )
            )

    async def _replace_request_logs(
        self, session: AsyncSession, request_logs: list[ConfigBackupRequestLog]
    ) -> None:
        await session.execute(delete(RequestLogEntity))

        for item in request_logs:
            session.add(
                RequestLogEntity(
                    protocol=item.protocol.value,
                    user_agent=item.user_agent.strip()[:300],
                    requested_group_name=item.requested_group_name,
                    resolved_group_name=item.resolved_group_name,
                    upstream_model_name=item.upstream_model_name,
                    channel_id=item.channel_id,
                    channel_name=item.channel_name,
                    gateway_key_id=item.gateway_key_id,
                    status_code=item.status_code,
                    success=1 if item.success else 0,
                    lifecycle_status=(
                        item.lifecycle_status or RequestLogLifecycleStatus.FAILED
                    ).value,
                    is_stream=1 if item.is_stream else 0,
                    first_token_latency_ms=max(item.first_token_latency_ms, 0),
                    latency_ms=max(item.latency_ms, 0),
                    input_tokens=max(item.input_tokens, 0),
                    cache_read_input_tokens=max(item.cache_read_input_tokens, 0),
                    cache_write_input_tokens=max(item.cache_write_input_tokens, 0),
                    output_tokens=max(item.output_tokens, 0),
                    total_tokens=max(item.total_tokens, 0),
                    input_cost_usd=max(item.input_cost_usd, 0.0),
                    output_cost_usd=max(item.output_cost_usd, 0.0),
                    total_cost_usd=max(item.total_cost_usd, 0.0),
                    request_content=item.request_content,
                    response_content=item.response_content,
                    attempts_json=json.dumps(
                        [attempt.model_dump(mode="json") for attempt in item.attempts],
                        ensure_ascii=True,
                    ),
                    error_message=item.error_message,
                    stats_archived=1 if item.stats_archived else 0,
                    created_at=self._parse_backup_datetime(item.created_at),
                )
            )

    async def _load_sites(self, session: AsyncSession) -> list[SiteConfig]:
        site_rows = (
            (await session.execute(select(SiteEntity).order_by(SiteEntity.name.asc())))
            .scalars()
            .all()
        )
        if not site_rows:
            return []

        site_ids = [item.id for item in site_rows]
        base_url_rows = (
            (
                await session.execute(
                    select(SiteBaseUrlEntity)
                    .where(SiteBaseUrlEntity.site_id.in_(site_ids))
                    .order_by(
                        SiteBaseUrlEntity.site_id.asc(),
                        SiteBaseUrlEntity.sort_order.asc(),
                        SiteBaseUrlEntity.id.asc(),
                    )
                )
            )
            .scalars()
            .all()
        )
        credential_rows = (
            (
                await session.execute(
                    select(SiteCredentialEntity)
                    .where(SiteCredentialEntity.site_id.in_(site_ids))
                    .order_by(
                        SiteCredentialEntity.site_id.asc(),
                        SiteCredentialEntity.sort_order.asc(),
                        SiteCredentialEntity.id.asc(),
                    )
                )
            )
            .scalars()
            .all()
        )
        protocol_rows = (
            (
                await session.execute(
                    select(SiteProtocolConfigEntity)
                    .where(SiteProtocolConfigEntity.site_id.in_(site_ids))
                    .order_by(
                        SiteProtocolConfigEntity.site_id.asc(),
                        SiteProtocolConfigEntity.id.asc(),
                    )
                )
            )
            .scalars()
            .all()
        )
        protocol_ids = [item.id for item in protocol_rows]
        model_rows = []
        if protocol_ids:
            model_rows = (
                (
                    await session.execute(
                        select(SiteDiscoveredModelEntity)
                        .where(
                            SiteDiscoveredModelEntity.protocol_config_id.in_(
                                protocol_ids
                            )
                        )
                        .order_by(
                            SiteDiscoveredModelEntity.protocol_config_id.asc(),
                            SiteDiscoveredModelEntity.sort_order.asc(),
                            SiteDiscoveredModelEntity.id.asc(),
                        )
                    )
                )
                .scalars()
                .all()
            )

        valid_protocol_values = {pk.value for pk in ProtocolKind}
        base_urls_by_site: dict[str, list[dict[str, object]]] = {}
        for row in base_url_rows:
            base_urls_by_site.setdefault(row.site_id, []).append(
                {
                    "id": row.id,
                    "url": row.url,
                    "name": row.name,
                    "enabled": bool(row.enabled),
                    "sort_order": row.sort_order,
                    "compatible_protocols": [
                        p
                        for p in json.loads(row.compatible_protocols_json or "[]")
                        if p in valid_protocol_values
                    ],
                }
            )

        credentials_by_site: dict[str, list[dict[str, object]]] = {}
        credentials_by_id: dict[str, dict[str, object]] = {}
        for row in credential_rows:
            item = {
                "id": row.id,
                "name": row.name,
                "api_key": row.api_key,
                "enabled": bool(row.enabled),
                "sort_order": row.sort_order,
            }
            credentials_by_site.setdefault(row.site_id, []).append(item)
            credentials_by_id[row.id] = item

        models_by_protocol: dict[str, list[dict[str, object]]] = {}
        for row in model_rows:
            credential_name = str(
                credentials_by_id.get(row.credential_id, {}).get("name", "")
            )
            models_by_protocol.setdefault(row.protocol_config_id, []).append(
                {
                    "id": row.id,
                    "credential_id": row.credential_id,
                    "credential_name": credential_name,
                    "model_name": row.model_name,
                    "enabled": bool(row.enabled),
                    "sort_order": row.sort_order,
                    "protocol": (
                        row.protocol
                        if row.protocol in valid_protocol_values
                        else None
                    ),
                }
            )

        protocols_by_site: dict[str, list[dict[str, object]]] = {}
        for row in protocol_rows:
            raw_headers = json.loads(row.headers_json)
            if not isinstance(raw_headers, dict):
                raise ValueError(f"Invalid headers JSON for protocol config {row.id}")
            headers = {str(key): str(value) for key, value in raw_headers.items()}

            protocols_by_site.setdefault(row.site_id, []).append(
                {
                    "id": row.id,
                    "name": row.name,
                    "enabled": bool(row.enabled),
                    "headers": headers,
                    "channel_proxy": row.channel_proxy,
                    "param_override": row.param_override,
                    "match_regex": row.match_regex,
                    "base_url_id": row.base_url_id,
                    "credential_id": row.credential_id,
                    "models": models_by_protocol.get(row.id, []),
                }
            )

        return [
            SiteConfig.model_validate(
                {
                    "id": row.id,
                    "name": row.name,
                    "base_urls": base_urls_by_site.get(row.id, []),
                    "credentials": credentials_by_site.get(row.id, []),
                    "protocols": protocols_by_site.get(row.id, []),
                }
            )
            for row in site_rows
        ]

    async def _load_groups(self, session: AsyncSession) -> list[ModelGroup]:
        group_rows = (
            (
                await session.execute(
                    select(ModelGroupEntity).order_by(ModelGroupEntity.name)
                )
            )
            .scalars()
            .all()
        )
        if not group_rows:
            return []

        group_ids = [item.id for item in group_rows]
        item_rows = (
            (
                await session.execute(
                    select(ModelGroupItemEntity)
                    .where(ModelGroupItemEntity.group_id.in_(group_ids))
                    .order_by(
                        ModelGroupItemEntity.group_id.asc(),
                        ModelGroupItemEntity.sort_order.asc(),
                        ModelGroupItemEntity.id.asc(),
                    )
                )
            )
            .scalars()
            .all()
        )

        site_names = {
            row.id: row.name
            for row in (
                await session.execute(select(SiteEntity.id, SiteEntity.name))
            ).all()
        }
        credential_names = {
            row.id: row.name
            for row in (
                await session.execute(
                    select(SiteCredentialEntity.id, SiteCredentialEntity.name)
                )
            ).all()
        }
        route_group_names = {
            row.id: row.name
            for row in (
                await session.execute(
                    select(ModelGroupEntity.id, ModelGroupEntity.name)
                )
            ).all()
        }
        channel_site_ids = {
            row.id: row.site_id
            for row in (
                await session.execute(
                    select(
                        SiteProtocolConfigEntity.id, SiteProtocolConfigEntity.site_id
                    )
                )
            ).all()
        }

        items_by_group: dict[str, list[dict[str, object]]] = {}
        for row in item_rows:
            items_by_group.setdefault(row.group_id, []).append(
                {
                    "channel_id": row.channel_id,
                    "channel_name": site_names.get(
                        channel_site_ids.get(row.channel_id, ""), ""
                    ),
                    "credential_id": row.credential_id,
                    "credential_name": credential_names.get(row.credential_id, ""),
                    "model_name": row.model_name,
                    "enabled": bool(row.enabled),
                    "sort_order": row.sort_order,
                }
            )

        price_rows = (await session.execute(select(ModelPriceEntity))).scalars().all()
        prices_by_key = {row.model_key: row for row in price_rows}

        groups: list[ModelGroup] = []
        for row in group_rows:
            price_key = normalize_model_key(row.name)
            price = prices_by_key.get(price_key)
            groups.append(
                ModelGroup.model_validate(
                    {
                        "id": row.id,
                        "name": row.name,
                        "protocols": json.loads(row.protocols_json),
                        "strategy": row.strategy,
                        "route_group_id": row.route_group_id,
                        "route_group_name": route_group_names.get(
                            row.route_group_id, ""
                        ),
                        "sync_filter_mode": row.sync_filter_mode,
                        "sync_filter_query": row.sync_filter_query,
                        "input_price_per_million": (
                            price.input_price_per_million if price is not None else 0.0
                        ),
                        "output_price_per_million": (
                            price.output_price_per_million if price is not None else 0.0
                        ),
                        "cache_read_price_per_million": (
                            price.cache_read_price_per_million
                            if price is not None
                            else 0.0
                        ),
                        "cache_write_price_per_million": (
                            price.cache_write_price_per_million
                            if price is not None
                            else 0.0
                        ),
                        "items": items_by_group.get(row.id, []),
                    }
                )
            )
        return groups

    async def _load_model_prices(self, session: AsyncSession) -> list[ModelPriceItem]:
        rows = (
            (
                await session.execute(
                    select(ModelPriceEntity).order_by(
                        ModelPriceEntity.display_name.asc(),
                        ModelPriceEntity.model_key.asc(),
                    )
                )
            )
            .scalars()
            .all()
        )
        return [
            ModelPriceItem(
                model_key=row.model_key,
                display_name=row.display_name,
                protocols=[],
                input_price_per_million=row.input_price_per_million,
                output_price_per_million=row.output_price_per_million,
                cache_read_price_per_million=row.cache_read_price_per_million,
                cache_write_price_per_million=row.cache_write_price_per_million,
            )
            for row in rows
        ]

    async def _load_stats(self, session: AsyncSession) -> ConfigBackupStatsSnapshot:
        imported_total_row = await session.get(ImportedStatsTotalEntity, 1)
        imported_daily_rows = (
            (
                await session.execute(
                    select(ImportedStatsDailyEntity).order_by(
                        ImportedStatsDailyEntity.date.asc()
                    )
                )
            )
            .scalars()
            .all()
        )
        request_daily_rows = (
            (
                await session.execute(
                    select(RequestLogDailyStatsEntity).order_by(
                        RequestLogDailyStatsEntity.date.asc()
                    )
                )
            )
            .scalars()
            .all()
        )
        model_daily_rows = (
            (
                await session.execute(
                    select(OverviewModelDailyStatsEntity).order_by(
                        OverviewModelDailyStatsEntity.date.asc(),
                        OverviewModelDailyStatsEntity.model.asc(),
                    )
                )
            )
            .scalars()
            .all()
        )

        imported_total = None
        if imported_total_row is not None:
            imported_total = ConfigBackupImportedStatsTotal(
                input_token=imported_total_row.input_token,
                output_token=imported_total_row.output_token,
                input_cost=imported_total_row.input_cost,
                output_cost=imported_total_row.output_cost,
                wait_time=imported_total_row.wait_time,
                request_success=imported_total_row.request_success,
                request_failed=imported_total_row.request_failed,
            )

        return ConfigBackupStatsSnapshot(
            imported_total=imported_total,
            imported_daily=[
                ConfigBackupImportedStatsDaily(
                    date=row.date,
                    input_token=row.input_token,
                    output_token=row.output_token,
                    input_cost=row.input_cost,
                    output_cost=row.output_cost,
                    wait_time=row.wait_time,
                    request_success=row.request_success,
                    request_failed=row.request_failed,
                )
                for row in imported_daily_rows
            ],
            request_daily=[
                ConfigBackupRequestLogDailyStat(
                    date=row.date,
                    request_count=row.request_count,
                    successful_requests=row.successful_requests,
                    failed_requests=row.failed_requests,
                    wait_time_ms=row.wait_time_ms,
                    input_tokens=row.input_tokens,
                    cache_read_input_tokens=row.cache_read_input_tokens,
                    cache_write_input_tokens=row.cache_write_input_tokens,
                    output_tokens=row.output_tokens,
                    total_tokens=row.total_tokens,
                    input_cost_usd=row.input_cost_usd,
                    output_cost_usd=row.output_cost_usd,
                    total_cost_usd=row.total_cost_usd,
                )
                for row in request_daily_rows
            ],
            model_daily=[
                ConfigBackupOverviewModelDailyStat(
                    date=row.date,
                    model=row.model,
                    requests=row.requests,
                    total_tokens=row.total_tokens,
                    total_cost_usd=row.total_cost_usd,
                )
                for row in model_daily_rows
            ],
        )

    async def _load_gateway_api_keys(
        self, session: AsyncSession
    ) -> list[ConfigBackupGatewayApiKey]:
        rows = (
            (
                await session.execute(
                    select(GatewayApiKeyEntity).order_by(
                        GatewayApiKeyEntity.created_at.asc(),
                        GatewayApiKeyEntity.id.asc(),
                    )
                )
            )
            .scalars()
            .all()
        )
        return [
            ConfigBackupGatewayApiKey(
                id=row.id,
                remark=row.remark,
                api_key=row.api_key,
                enabled=bool(row.enabled),
                allowed_models=self._load_allowed_models(row.allowed_models_json),
                max_cost_usd=max(row.max_cost_usd, 0.0),
                expires_at=self._format_optional_datetime(row.expires_at),
                created_at=self._format_optional_datetime(row.created_at),
                updated_at=self._format_optional_datetime(row.updated_at),
            )
            for row in rows
        ]

    async def _load_cronjobs(self, session: AsyncSession) -> list[ConfigBackupCronjob]:
        rows = (
            (
                await session.execute(
                    select(CronjobEntity).order_by(CronjobEntity.id.asc())
                )
            )
            .scalars()
            .all()
        )
        return [
            ConfigBackupCronjob(
                id=row.id,
                enabled=bool(row.enabled),
                schedule_type=row.schedule_type,
                interval_hours=max(row.interval_hours, 1),
                run_at_time=row.run_at_time,
                weekdays=self._load_weekdays(row.weekdays_json),
            )
            for row in rows
        ]

    async def _load_request_logs(
        self, session: AsyncSession
    ) -> list[ConfigBackupRequestLog]:
        rows = (
            (
                await session.execute(
                    select(RequestLogEntity).order_by(
                        RequestLogEntity.created_at.asc(),
                        RequestLogEntity.id.asc(),
                    )
                )
            )
            .scalars()
            .all()
        )
        logs: list[ConfigBackupRequestLog] = []
        for row in rows:
            attempts = self._parse_attempts(row.attempts_json)
            logs.append(
                ConfigBackupRequestLog(
                    protocol=row.protocol,
                    user_agent=row.user_agent,
                    requested_group_name=row.requested_group_name,
                    resolved_group_name=row.resolved_group_name,
                    upstream_model_name=row.upstream_model_name,
                    channel_id=row.channel_id,
                    channel_name=row.channel_name,
                    gateway_key_id=row.gateway_key_id,
                    status_code=row.status_code,
                    success=bool(row.success),
                    lifecycle_status=(
                        row.lifecycle_status
                        if row.lifecycle_status
                        in RequestLogLifecycleStatus._value2member_map_
                        else (
                            RequestLogLifecycleStatus.SUCCEEDED.value
                            if row.success
                            else RequestLogLifecycleStatus.FAILED.value
                        )
                    ),
                    is_stream=bool(row.is_stream),
                    first_token_latency_ms=row.first_token_latency_ms,
                    latency_ms=row.latency_ms,
                    input_tokens=row.input_tokens,
                    cache_read_input_tokens=row.cache_read_input_tokens,
                    cache_write_input_tokens=row.cache_write_input_tokens,
                    output_tokens=row.output_tokens,
                    total_tokens=row.total_tokens,
                    input_cost_usd=row.input_cost_usd,
                    output_cost_usd=row.output_cost_usd,
                    total_cost_usd=row.total_cost_usd,
                    error_message=row.error_message,
                    created_at=row.created_at.replace(tzinfo=UTC).isoformat(),
                    stats_archived=bool(row.stats_archived),
                    request_content=row.request_content,
                    response_content=row.response_content,
                    attempts=attempts,
                )
            )
        return logs

    @staticmethod
    def _parse_backup_datetime(value: str) -> datetime:
        normalized = value.strip()
        if normalized.endswith("Z"):
            normalized = normalized[:-1] + "+00:00"
        parsed = datetime.fromisoformat(normalized)
        if parsed.tzinfo is None:
            return parsed
        return parsed.astimezone(UTC).replace(tzinfo=None)

    @classmethod
    def _parse_optional_datetime(cls, value: str | None) -> datetime | None:
        if value is None or not value.strip():
            return None
        return cls._parse_backup_datetime(value)

    @staticmethod
    def _format_optional_datetime(value: datetime | None) -> str | None:
        if value is None:
            return None
        return value.replace(tzinfo=UTC).isoformat()

    @staticmethod
    def _load_allowed_models(raw_value: str | None) -> list[str]:
        if not raw_value:
            return []
        payload = json.loads(raw_value)
        if not isinstance(payload, list):
            raise ValueError("Invalid gateway API key allowed models JSON")
        models: list[str] = []
        seen: set[str] = set()
        for item in payload:
            normalized = str(item).strip()
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            models.append(normalized)
        return models

    @staticmethod
    def _load_weekdays(raw_value: str | None) -> list[int]:
        if not raw_value:
            return []
        payload = json.loads(raw_value)
        if not isinstance(payload, list):
            raise ValueError("Invalid cronjob weekdays JSON")
        weekdays: list[int] = []
        seen: set[int] = set()
        for item in payload:
            try:
                weekday = int(item)
            except (TypeError, ValueError):
                continue
            if weekday < 1 or weekday > 7 or weekday in seen:
                continue
            seen.add(weekday)
            weekdays.append(weekday)
        return sorted(weekdays)

    @staticmethod
    def _parse_attempts(raw_value: str | None) -> list[RequestLogAttempt]:
        if not raw_value:
            return []
        payload = json.loads(raw_value)
        if not isinstance(payload, list):
            raise ValueError("Invalid request log attempts JSON")
        attempts: list[RequestLogAttempt] = []
        for item in payload:
            attempts.append(RequestLogAttempt.model_validate(item))
        return attempts
