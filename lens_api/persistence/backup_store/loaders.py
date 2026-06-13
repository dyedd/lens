from __future__ import annotations

from .shared import (
    AsyncSession,
    ConfigBackupCronjob,
    ConfigBackupGatewayApiKey,
    ConfigBackupImportedStatsDaily,
    ConfigBackupImportedStatsTotal,
    ConfigBackupOverviewModelDailyStat,
    ConfigBackupRequestLog,
    ConfigBackupRequestLogDailyStat,
    ConfigBackupStatsSnapshot,
    CronjobEntity,
    GatewayApiKeyEntity,
    ImportedStatsDailyEntity,
    ImportedStatsTotalEntity,
    ModelGroup,
    ModelGroupEntity,
    ModelGroupItemEntity,
    ModelPriceEntity,
    ModelPriceItem,
    OverviewModelDailyStatsEntity,
    ProtocolKind,
    RequestLogDailyStatsEntity,
    RequestLogEntity,
    RequestLogLifecycleStatus,
    SiteConfig,
    SiteCredentialEntity,
    SiteEntity,
    SiteProtocolConfigEntity,
    UTC,
    _extract_protocol_config_id,
    json,
    normalize_model_key,
    select,
)
from .value_parsing import (
    format_optional_datetime,
    load_allowed_models,
    load_weekdays,
    parse_attempts,
)
from ..site_loader import fetch_site_rows


class BackupLoadersMixin:
    async def _load_sites(self, session: AsyncSession) -> list[SiteConfig]:
        (
            site_rows,
            base_url_rows,
            credential_rows,
            protocol_rows,
            model_rows,
        ) = await fetch_site_rows(session)
        if not site_rows:
            return []

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
                    "supported_protocols": [
                        p
                        for p in json.loads(row.supported_protocols_json or "[]")
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

        models_by_protocol_config: dict[str, list[dict[str, object]]] = {}
        for row in model_rows:
            credential_name = str(
                credentials_by_id.get(row.credential_id, {}).get("name", "")
            )
            models_by_protocol_config.setdefault(row.protocol_config_id, []).append(
                {
                    "id": row.id,
                    "credential_id": row.credential_id,
                    "credential_name": credential_name,
                    "model_name": row.model_name,
                    "enabled": bool(row.enabled),
                    "sort_order": row.sort_order,
                    "protocol": (
                        row.protocol if row.protocol in valid_protocol_values else None
                    ),
                }
            )

        protocol_configs_by_site: dict[str, list[dict[str, object]]] = {}
        for row in protocol_rows:
            raw_headers = json.loads(row.headers_json)
            if not isinstance(raw_headers, dict):
                raise ValueError(f"Invalid headers JSON for protocol config {row.id}")
            headers = {str(key): str(value) for key, value in raw_headers.items()}

            protocol_configs_by_site.setdefault(row.site_id, []).append(
                {
                    "id": row.id,
                    "name": row.name,
                    "protocols": [
                        p
                        for p in json.loads(row.protocols_json or "[]")
                        if p in valid_protocol_values
                    ],
                    "enabled": bool(row.enabled),
                    "headers": headers,
                    "proxy_mode": row.proxy_mode,
                    "channel_proxy": row.channel_proxy,
                    "param_override": row.param_override,
                    "match_regex": row.match_regex,
                    "base_url_id": row.base_url_id,
                    "credential_id": row.credential_id,
                    "models": models_by_protocol_config.get(row.id, []),
                }
            )

        return [
            SiteConfig.model_validate(
                {
                    "id": row.id,
                    "name": row.name,
                    "base_urls": base_urls_by_site.get(row.id, []),
                    "credentials": credentials_by_site.get(row.id, []),
                    "protocols": protocol_configs_by_site.get(row.id, []),
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
        protocol_config_ids = set(channel_site_ids)

        items_by_group: dict[str, list[dict[str, object]]] = {}
        for row in item_rows:
            protocol_config_id = _extract_protocol_config_id(
                row.channel_id, protocol_config_ids
            )
            items_by_group.setdefault(row.group_id, []).append(
                {
                    "channel_id": row.channel_id,
                    "channel_name": site_names.get(
                        channel_site_ids.get(protocol_config_id, ""), ""
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
                allowed_models=load_allowed_models(row.allowed_models_json),
                max_cost_usd=max(row.max_cost_usd, 0.0),
                spent_cost_usd=max(row.spent_cost_usd, 0.0),
                expires_at=format_optional_datetime(row.expires_at),
                created_at=format_optional_datetime(row.created_at),
                updated_at=format_optional_datetime(row.updated_at),
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
                weekdays=load_weekdays(row.weekdays_json),
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
            attempts = parse_attempts(row.attempts_json)
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
