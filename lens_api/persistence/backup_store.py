from __future__ import annotations

import json
from datetime import UTC, datetime
from zoneinfo import ZoneInfo

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from ..core.model_prices import normalize_model_key
from ..core.time_zone import normalize_time_zone, resolve_time_zone
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
    RequestLogAttempt,
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
    SETTING_PROXY_URL,
    SETTING_RELAY_LOG_KEEP_ENABLED,
    SETTING_RELAY_LOG_KEEP_PERIOD,
    SETTING_SITE_LOGO_URL,
    SETTING_SITE_NAME,
    SETTING_TIME_ZONE,
    SETTING_MODEL_PRICE_LAST_SYNC_AT,
    SETTING_STATS_LAST_PERSIST_AT,
    SETTING_STATS_SAVE_INTERVAL,
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
    SiteProtocolCredentialBindingEntity,
)
from .cronjob_store import (
    encode_weekdays,
    next_cronjob_run_at,
    normalize_cronjob_schedule,
)

BACKUP_DUMP_VERSION = 2

EXPORTABLE_SETTING_KEYS = (
    SETTING_PROXY_URL,
    SETTING_STATS_SAVE_INTERVAL,
    SETTING_CORS_ALLOW_ORIGINS,
    SETTING_RELAY_LOG_KEEP_ENABLED,
    SETTING_RELAY_LOG_KEEP_PERIOD,
    SETTING_CIRCUIT_BREAKER_THRESHOLD,
    SETTING_CIRCUIT_BREAKER_COOLDOWN,
    SETTING_CIRCUIT_BREAKER_MAX_COOLDOWN,
    SETTING_HEALTH_WINDOW_SECONDS,
    SETTING_HEALTH_PENALTY_WEIGHT,
    SETTING_HEALTH_MIN_SAMPLES,
    SETTING_SITE_NAME,
    SETTING_SITE_LOGO_URL,
    SETTING_TIME_ZONE,
)


class BackupStore:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def export_dump(
        self,
        *,
        lens_version: str,
        include_request_logs: bool,
        include_gateway_api_keys: bool,
    ) -> ConfigBackupDump:
        async with self._session_factory() as session:
            settings_rows = (
                await session.execute(
                    select(SettingEntity)
                    .where(SettingEntity.key.in_(EXPORTABLE_SETTING_KEYS))
                    .order_by(SettingEntity.key.asc())
                )
            ).scalars().all()
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
                await self._load_request_logs(session)
                if include_request_logs
                else []
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

            channel_ids, credential_ids = await self._replace_sites(session, dump.sites)
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
            rows_affected["site_protocol_bindings"] = sum(
                len(protocol.bindings)
                for site in dump.sites
                for protocol in site.protocols
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
                available_credential_ids=credential_ids,
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
                await self._replace_gateway_api_keys(
                    session, dump.gateway_api_keys
                )
                rows_affected["gateway_api_keys"] = len(dump.gateway_api_keys)

            if dump.include_request_logs:
                await self._replace_request_logs(session, dump.request_logs)
                rows_affected["request_logs"] = len(dump.request_logs)

            await session.commit()

        return ConfigImportResult(rows_affected=rows_affected)

    async def _replace_sites(
        self, session: AsyncSession, sites: list[SiteConfig]
    ) -> tuple[set[str], set[str]]:
        await session.execute(delete(SiteDiscoveredModelEntity))
        await session.execute(delete(SiteProtocolCredentialBindingEntity))
        await session.execute(delete(SiteProtocolConfigEntity))
        await session.execute(delete(SiteCredentialEntity))
        await session.execute(delete(SiteBaseUrlEntity))
        await session.execute(delete(SiteEntity))

        site_ids: set[str] = set()
        site_names: set[str] = set()
        channel_ids: set[str] = set()
        credential_ids: set[str] = set()
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
                    raise ValueError(
                        f"Duplicate base url id in backup: {base_url.id}"
                    )
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
                    raise ValueError(
                        f"Duplicate channel id in backup: {protocol.id}"
                    )
                channel_ids.add(protocol.id)
                if (
                    protocol.base_url_id
                    and protocol.base_url_id not in site_base_url_ids
                ):
                    raise ValueError(
                        f"Channel base url not found in backup site {site.name}: {protocol.base_url_id}"
                    )
                session.add(
                    SiteProtocolConfigEntity(
                        id=protocol.id,
                        site_id=site.id,
                        protocol=protocol.protocol.value,
                        enabled=1 if protocol.enabled else 0,
                        headers_json=json.dumps(protocol.headers, ensure_ascii=True),
                        channel_proxy=protocol.channel_proxy,
                        param_override=protocol.param_override,
                        match_regex=protocol.match_regex,
                        base_url_id=protocol.base_url_id,
                    )
                )

                seen_binding_credentials: set[str] = set()
                for binding in protocol.bindings:
                    if binding.credential_id not in site_credential_ids:
                        raise ValueError(
                            f"Channel binding credential not found in backup site {site.name}: {binding.credential_id}"
                        )
                    if binding.credential_id in seen_binding_credentials:
                        raise ValueError(
                            f"Duplicate channel binding credential in backup channel {protocol.id}: {binding.credential_id}"
                        )
                    seen_binding_credentials.add(binding.credential_id)
                    session.add(
                        SiteProtocolCredentialBindingEntity(
                            id=f"{protocol.id}:{binding.credential_id}",
                            protocol_config_id=protocol.id,
                            credential_id=binding.credential_id,
                            enabled=1 if binding.enabled else 0,
                            sort_order=binding.sort_order,
                        )
                    )

                for model in protocol.models:
                    if model.id in model_ids:
                        raise ValueError(
                            f"Duplicate discovered model id in backup: {model.id}"
                        )
                    model_ids.add(model.id)
                    if (
                        model.credential_id
                        and model.credential_id not in site_credential_ids
                    ):
                        raise ValueError(
                            f"Discovered model credential not found in backup site {site.name}: {model.credential_id}"
                        )
                    session.add(
                        SiteDiscoveredModelEntity(
                            id=model.id,
                            protocol_config_id=protocol.id,
                            credential_id=model.credential_id,
                            model_name=model.model_name,
                            enabled=1 if model.enabled else 0,
                            sort_order=model.sort_order,
                        )
                    )

        return channel_ids, credential_ids

    async def _replace_groups(
        self,
        session: AsyncSession,
        groups: list[ModelGroup],
        *,
        available_channel_ids: set[str],
        available_credential_ids: set[str],
    ) -> None:
        await session.execute(delete(ModelGroupItemEntity))
        await session.execute(delete(ModelGroupEntity))

        group_ids = {group.id for group in groups}
        seen_protocol_name: set[tuple[str, str]] = set()
        seen_group_ids: set[str] = set()

        for group in groups:
            if group.id in seen_group_ids:
                raise ValueError(f"Duplicate group id in backup: {group.id}")
            seen_group_ids.add(group.id)

            protocol_name_key = (group.protocol.value, group.name)
            if protocol_name_key in seen_protocol_name:
                raise ValueError(
                    f"Duplicate model group name in backup: {group.name}"
                )
            seen_protocol_name.add(protocol_name_key)

            if group.route_group_id and group.route_group_id not in group_ids:
                raise ValueError(
                    f"Referenced route group not found: {group.route_group_id}"
                )

            session.add(
                ModelGroupEntity(
                    id=group.id,
                    name=group.name,
                    protocol=group.protocol.value,
                    strategy=group.strategy.value,
                    route_group_id=group.route_group_id,
                )
            )

            for index, item in enumerate(group.items):
                if item.channel_id not in available_channel_ids:
                    raise ValueError(
                        f"Model group channel not found in backup sites: {item.channel_id}"
                    )
                if item.credential_id and item.credential_id not in available_credential_ids:
                    raise ValueError(
                        f"Model group credential not found in backup sites: {item.credential_id}"
                    )
                session.add(
                    ModelGroupItemEntity(
                        group_id=group.id,
                        channel_id=item.channel_id,
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
                    input_price_per_million=float(item.input_price_per_million),
                    output_price_per_million=float(item.output_price_per_million),
                    cache_read_price_per_million=float(
                        item.cache_read_price_per_million
                    ),
                    cache_write_price_per_million=float(
                        item.cache_write_price_per_million
                    ),
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
                    input_cost=float(stats.imported_total.input_cost),
                    output_cost=float(stats.imported_total.output_cost),
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
                    input_cost=float(item.input_cost),
                    output_cost=float(item.output_cost),
                    wait_time=item.wait_time,
                    request_success=item.request_success,
                    request_failed=item.request_failed,
                )
            )

        request_daily_dates: set[str] = set()
        for item in stats.request_daily:
            if item.date in request_daily_dates:
                raise ValueError(
                    f"Duplicate request stats date in backup: {item.date}"
                )
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
                    input_cost_usd=float(item.input_cost_usd),
                    output_cost_usd=float(item.output_cost_usd),
                    total_cost_usd=float(item.total_cost_usd),
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
                    total_cost_usd=float(item.total_cost_usd),
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
            value = normalize_time_zone(item.value) if item.key == SETTING_TIME_ZONE else item.value
            session.add(SettingEntity(key=item.key, value=value))

    async def _replace_cronjobs(
        self, session: AsyncSession, cronjobs: list[ConfigBackupCronjob]
    ) -> None:
        task_ids: set[str] = set()
        now = datetime.now(UTC).replace(tzinfo=None)
        time_zone = await self._runtime_time_zone(session)
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
                    max_cost_usd=max(float(item.max_cost_usd), 0.0),
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
                    requested_group_name=item.requested_group_name,
                    resolved_group_name=item.resolved_group_name,
                    upstream_model_name=item.upstream_model_name,
                    channel_id=item.channel_id,
                    channel_name=item.channel_name,
                    gateway_key_id=item.gateway_key_id,
                    status_code=item.status_code,
                    success=1 if item.success else 0,
                    is_stream=1 if item.is_stream else 0,
                    first_token_latency_ms=max(item.first_token_latency_ms, 0),
                    latency_ms=max(item.latency_ms, 0),
                    input_tokens=max(item.input_tokens, 0),
                    cache_read_input_tokens=max(item.cache_read_input_tokens, 0),
                    cache_write_input_tokens=max(item.cache_write_input_tokens, 0),
                    output_tokens=max(item.output_tokens, 0),
                    total_tokens=max(item.total_tokens, 0),
                    input_cost_usd=max(float(item.input_cost_usd), 0.0),
                    output_cost_usd=max(float(item.output_cost_usd), 0.0),
                    total_cost_usd=max(float(item.total_cost_usd), 0.0),
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
            await session.execute(select(SiteEntity).order_by(SiteEntity.name.asc()))
        ).scalars().all()
        if not site_rows:
            return []

        site_ids = [item.id for item in site_rows]
        base_url_rows = (
            await session.execute(
                select(SiteBaseUrlEntity)
                .where(SiteBaseUrlEntity.site_id.in_(site_ids))
                .order_by(
                    SiteBaseUrlEntity.site_id.asc(),
                    SiteBaseUrlEntity.sort_order.asc(),
                    SiteBaseUrlEntity.id.asc(),
                )
            )
        ).scalars().all()
        credential_rows = (
            await session.execute(
                select(SiteCredentialEntity)
                .where(SiteCredentialEntity.site_id.in_(site_ids))
                .order_by(
                    SiteCredentialEntity.site_id.asc(),
                    SiteCredentialEntity.sort_order.asc(),
                    SiteCredentialEntity.id.asc(),
                )
            )
        ).scalars().all()
        protocol_rows = (
            await session.execute(
                select(SiteProtocolConfigEntity)
                .where(SiteProtocolConfigEntity.site_id.in_(site_ids))
                .order_by(
                    SiteProtocolConfigEntity.site_id.asc(),
                    SiteProtocolConfigEntity.protocol.asc(),
                    SiteProtocolConfigEntity.id.asc(),
                )
            )
        ).scalars().all()
        protocol_ids = [item.id for item in protocol_rows]
        binding_rows = []
        model_rows = []
        if protocol_ids:
            binding_rows = (
                await session.execute(
                    select(SiteProtocolCredentialBindingEntity)
                    .where(
                        SiteProtocolCredentialBindingEntity.protocol_config_id.in_(
                            protocol_ids
                        )
                    )
                    .order_by(
                        SiteProtocolCredentialBindingEntity.protocol_config_id.asc(),
                        SiteProtocolCredentialBindingEntity.sort_order.asc(),
                        SiteProtocolCredentialBindingEntity.id.asc(),
                    )
                )
            ).scalars().all()
            model_rows = (
                await session.execute(
                    select(SiteDiscoveredModelEntity)
                    .where(
                        SiteDiscoveredModelEntity.protocol_config_id.in_(protocol_ids)
                    )
                    .order_by(
                        SiteDiscoveredModelEntity.protocol_config_id.asc(),
                        SiteDiscoveredModelEntity.sort_order.asc(),
                        SiteDiscoveredModelEntity.id.asc(),
                    )
                )
            ).scalars().all()

        base_urls_by_site: dict[str, list[dict[str, object]]] = {}
        for row in base_url_rows:
            base_urls_by_site.setdefault(row.site_id, []).append(
                {
                    "id": row.id,
                    "url": row.url,
                    "name": row.name,
                    "enabled": bool(row.enabled),
                    "sort_order": row.sort_order,
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

        bindings_by_protocol: dict[str, list[dict[str, object]]] = {}
        for row in binding_rows:
            credential_name = str(
                credentials_by_id.get(row.credential_id, {}).get("name", "")
            )
            bindings_by_protocol.setdefault(row.protocol_config_id, []).append(
                {
                    "credential_id": row.credential_id,
                    "credential_name": credential_name,
                    "enabled": bool(row.enabled),
                    "sort_order": row.sort_order,
                }
            )

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
                }
            )

        protocols_by_site: dict[str, list[dict[str, object]]] = {}
        for row in protocol_rows:
            headers: dict[str, str] = {}
            try:
                raw_headers = json.loads(row.headers_json)
                if isinstance(raw_headers, dict):
                    headers = {
                        str(key): str(value) for key, value in raw_headers.items()
                    }
            except json.JSONDecodeError:
                headers = {}

            protocols_by_site.setdefault(row.site_id, []).append(
                {
                    "id": row.id,
                    "protocol": row.protocol,
                    "enabled": bool(row.enabled),
                    "headers": headers,
                    "channel_proxy": row.channel_proxy,
                    "param_override": row.param_override,
                    "match_regex": row.match_regex,
                    "base_url_id": row.base_url_id,
                    "bindings": bindings_by_protocol.get(row.id, []),
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
            await session.execute(select(ModelGroupEntity).order_by(ModelGroupEntity.name))
        ).scalars().all()
        if not group_rows:
            return []

        group_ids = [item.id for item in group_rows]
        item_rows = (
            await session.execute(
                select(ModelGroupItemEntity)
                .where(ModelGroupItemEntity.group_id.in_(group_ids))
                .order_by(
                    ModelGroupItemEntity.group_id.asc(),
                    ModelGroupItemEntity.sort_order.asc(),
                    ModelGroupItemEntity.id.asc(),
                )
            )
        ).scalars().all()

        site_names = {
            row.id: row.name
            for row in (
                await session.execute(select(SiteEntity.id, SiteEntity.name))
            ).all()
        }
        credential_names = {
            row.id: row.name
            for row in (
                await session.execute(select(SiteCredentialEntity.id, SiteCredentialEntity.name))
            ).all()
        }
        route_group_names = {
            row.id: row.name
            for row in (
                await session.execute(select(ModelGroupEntity.id, ModelGroupEntity.name))
            ).all()
        }
        channel_site_ids = {
            row.id: row.site_id
            for row in (
                await session.execute(
                    select(SiteProtocolConfigEntity.id, SiteProtocolConfigEntity.site_id)
                )
            ).all()
        }

        items_by_group: dict[str, list[dict[str, object]]] = {}
        for row in item_rows:
            items_by_group.setdefault(row.group_id, []).append(
                {
                    "channel_id": row.channel_id,
                    "channel_name": site_names.get(
                        str(channel_site_ids.get(row.channel_id, "")), ""
                    ),
                    "credential_id": row.credential_id,
                    "credential_name": credential_names.get(row.credential_id, ""),
                    "model_name": row.model_name,
                    "enabled": bool(row.enabled),
                    "sort_order": row.sort_order,
                }
            )

        price_rows = (
            await session.execute(select(ModelPriceEntity))
        ).scalars().all()
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
                        "protocol": row.protocol,
                        "strategy": row.strategy,
                        "route_group_id": row.route_group_id,
                        "route_group_name": route_group_names.get(row.route_group_id, ""),
                        "input_price_per_million": float(price.input_price_per_million) if price is not None else 0.0,
                        "output_price_per_million": float(price.output_price_per_million) if price is not None else 0.0,
                        "cache_read_price_per_million": float(price.cache_read_price_per_million) if price is not None else 0.0,
                        "cache_write_price_per_million": float(price.cache_write_price_per_million) if price is not None else 0.0,
                        "items": items_by_group.get(row.id, []),
                    }
                )
            )
        return groups

    async def _load_model_prices(
        self, session: AsyncSession
    ) -> list[ModelPriceItem]:
        rows = (
            await session.execute(
                select(ModelPriceEntity).order_by(
                    ModelPriceEntity.display_name.asc(),
                    ModelPriceEntity.model_key.asc(),
                )
            )
        ).scalars().all()
        return [
            ModelPriceItem(
                model_key=row.model_key,
                display_name=row.display_name,
                protocols=[],
                input_price_per_million=float(row.input_price_per_million),
                output_price_per_million=float(row.output_price_per_million),
                cache_read_price_per_million=float(row.cache_read_price_per_million),
                cache_write_price_per_million=float(row.cache_write_price_per_million),
            )
            for row in rows
        ]

    async def _load_stats(
        self, session: AsyncSession
    ) -> ConfigBackupStatsSnapshot:
        imported_total_row = await session.get(ImportedStatsTotalEntity, 1)
        imported_daily_rows = (
            await session.execute(
                select(ImportedStatsDailyEntity).order_by(
                    ImportedStatsDailyEntity.date.asc()
                )
            )
        ).scalars().all()
        request_daily_rows = (
            await session.execute(
                select(RequestLogDailyStatsEntity).order_by(
                    RequestLogDailyStatsEntity.date.asc()
                )
            )
        ).scalars().all()
        model_daily_rows = (
            await session.execute(
                select(OverviewModelDailyStatsEntity).order_by(
                    OverviewModelDailyStatsEntity.date.asc(),
                    OverviewModelDailyStatsEntity.model.asc(),
                )
            )
        ).scalars().all()

        imported_total = None
        if imported_total_row is not None:
            imported_total = ConfigBackupImportedStatsTotal(
                input_token=imported_total_row.input_token,
                output_token=imported_total_row.output_token,
                input_cost=float(imported_total_row.input_cost),
                output_cost=float(imported_total_row.output_cost),
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
                    input_cost=float(row.input_cost),
                    output_cost=float(row.output_cost),
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
                    input_cost_usd=float(row.input_cost_usd),
                    output_cost_usd=float(row.output_cost_usd),
                    total_cost_usd=float(row.total_cost_usd),
                )
                for row in request_daily_rows
            ],
            model_daily=[
                ConfigBackupOverviewModelDailyStat(
                    date=row.date,
                    model=row.model,
                    requests=row.requests,
                    total_tokens=row.total_tokens,
                    total_cost_usd=float(row.total_cost_usd),
                )
                for row in model_daily_rows
            ],
        )

    async def _load_gateway_api_keys(
        self, session: AsyncSession
    ) -> list[ConfigBackupGatewayApiKey]:
        rows = (
            await session.execute(
                select(GatewayApiKeyEntity).order_by(
                    GatewayApiKeyEntity.created_at.asc(),
                    GatewayApiKeyEntity.id.asc(),
                )
            )
        ).scalars().all()
        return [
            ConfigBackupGatewayApiKey(
                id=row.id,
                remark=row.remark,
                api_key=row.api_key,
                enabled=bool(row.enabled),
                allowed_models=self._load_allowed_models(row.allowed_models_json),
                max_cost_usd=max(float(row.max_cost_usd or 0.0), 0.0),
                expires_at=self._format_optional_datetime(row.expires_at),
                created_at=self._format_optional_datetime(row.created_at),
                updated_at=self._format_optional_datetime(row.updated_at),
            )
            for row in rows
        ]

    async def _load_cronjobs(
        self, session: AsyncSession
    ) -> list[ConfigBackupCronjob]:
        rows = (
            await session.execute(select(CronjobEntity).order_by(CronjobEntity.id.asc()))
        ).scalars().all()
        return [
            ConfigBackupCronjob(
                id=row.id,
                enabled=bool(row.enabled),
                schedule_type=row.schedule_type,
                interval_hours=max(int(row.interval_hours), 1),
                run_at_time=row.run_at_time,
                weekdays=list(self._load_weekdays(row.weekdays_json)),
            )
            for row in rows
        ]

    async def _load_request_logs(
        self, session: AsyncSession
    ) -> list[ConfigBackupRequestLog]:
        rows = (
            await session.execute(
                select(RequestLogEntity).order_by(
                    RequestLogEntity.created_at.asc(),
                    RequestLogEntity.id.asc(),
                )
            )
        ).scalars().all()
        logs: list[ConfigBackupRequestLog] = []
        for row in rows:
            attempts = self._parse_attempts(row.attempts_json)
            logs.append(
                ConfigBackupRequestLog(
                    protocol=row.protocol,
                    requested_group_name=row.requested_group_name,
                    resolved_group_name=row.resolved_group_name,
                    upstream_model_name=row.upstream_model_name,
                    channel_id=row.channel_id,
                    channel_name=row.channel_name,
                    gateway_key_id=row.gateway_key_id,
                    status_code=row.status_code,
                    success=bool(row.success),
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
        try:
            payload = json.loads(raw_value)
        except json.JSONDecodeError:
            return []
        if not isinstance(payload, list):
            return []
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
        try:
            payload = json.loads(raw_value)
        except json.JSONDecodeError:
            return []
        if not isinstance(payload, list):
            return []
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
    async def _runtime_time_zone(session: AsyncSession) -> ZoneInfo:
        setting = await session.get(SettingEntity, SETTING_TIME_ZONE)
        return resolve_time_zone(setting.value if setting is not None else None)

    @staticmethod
    def _parse_attempts(raw_value: str | None) -> list[RequestLogAttempt]:
        if not raw_value:
            return []
        try:
            payload = json.loads(raw_value)
        except json.JSONDecodeError:
            return []
        if not isinstance(payload, list):
            return []
        attempts: list[RequestLogAttempt] = []
        for item in payload:
            if not isinstance(item, dict):
                continue
            try:
                attempts.append(RequestLogAttempt.model_validate(item))
            except Exception:
                continue
        return attempts
