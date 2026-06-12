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
    ModelGroupItemEntity,
    ModelPriceEntity,
    ModelPriceItem,
    OverviewModelDailyStatsEntity,
    ProtocolKind,
    RequestLogDailyStatsEntity,
    RequestLogEntity,
    RequestLogLifecycleStatus,
    SETTING_MODEL_PRICE_LAST_SYNC_AT,
    SETTING_STATS_LAST_PERSIST_AT,
    SETTING_TIME_ZONE,
    SETTING_UPSTREAM_HEADERS_CONFIG,
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
    can_reach_protocol,
    datetime,
    delete,
    encode_weekdays,
    json,
    next_cronjob_run_at,
    normalize_cronjob_schedule,
    normalize_model_key,
    normalize_time_zone,
    normalize_upstream_headers_config_json,
    resolve_time_zone,
)
from .value_parsing import parse_backup_datetime, parse_optional_datetime


class BackupReplacersMixin:
    async def _replace_sites(
        self, session: AsyncSession, sites: list[SiteConfig]
    ) -> tuple[set[str], dict[str, list[ProtocolKind]], set[tuple[str, str, str]]]:
        await session.execute(delete(SiteDiscoveredModelEntity))
        await session.execute(delete(SiteProtocolConfigEntity))
        await session.execute(delete(SiteCredentialEntity))
        await session.execute(delete(SiteBaseUrlEntity))
        await session.execute(delete(SiteEntity))

        site_ids: set[str] = set()
        site_names: set[str] = set()
        protocol_config_ids: set[str] = set()
        protocols_by_config_id: dict[str, list[ProtocolKind]] = {}
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
                        supported_protocols_json=json.dumps(
                            [p.value for p in (base_url.supported_protocols or [])],
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

            for protocol_config in site.protocols:
                if protocol_config.id in protocol_config_ids:
                    raise ValueError(
                        "Duplicate protocol config id in backup: "
                        f"{protocol_config.id}"
                    )
                protocol_config_ids.add(protocol_config.id)
                if protocol_config.base_url_id not in site_base_url_ids:
                    raise ValueError(
                        "Protocol config base URL not found in backup site "
                        f"{site.name}: {protocol_config.base_url_id}"
                    )
                if (
                    protocol_config.credential_id
                    and protocol_config.credential_id not in site_credential_ids
                ):
                    raise ValueError(
                        "Protocol config credential not found in backup site "
                        f"{site.name}: {protocol_config.credential_id}"
                    )
                protocol_kinds = list(protocol_config.protocols)
                if not protocol_kinds:
                    raise ValueError(
                        "Protocol config protocols not found in backup site "
                        f"{site.name}: {protocol_config.id}"
                    )
                session.add(
                    SiteProtocolConfigEntity(
                        id=protocol_config.id,
                        site_id=site.id,
                        name=protocol_config.name,
                        protocols_json=json.dumps(
                            [p.value for p in protocol_kinds],
                            ensure_ascii=True,
                        ),
                        enabled=1 if protocol_config.enabled else 0,
                        headers_json=json.dumps(
                            protocol_config.headers, ensure_ascii=True
                        ),
                        channel_proxy=protocol_config.channel_proxy,
                        param_override=protocol_config.param_override,
                        match_regex=protocol_config.match_regex,
                        base_url_id=protocol_config.base_url_id,
                        credential_id=protocol_config.credential_id,
                    )
                )

                protocols_by_config_id[protocol_config.id] = protocol_kinds

                for model in protocol_config.models:
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
                            "Discovered model credential not found in backup site "
                            f"{site.name}: {model.credential_id}"
                        )
                    if model.protocol is None:
                        raise ValueError(
                            "Discovered model protocol not found in backup site "
                            f"{site.name}: {model.model_name}"
                        )
                    if model.protocol not in protocols_by_config_id[protocol_config.id]:
                        raise ValueError(
                            "Discovered model protocol is not enabled in backup "
                            f"protocol config {protocol_config.id}: "
                            f"{model.protocol.value}"
                        )
                    if model.enabled:
                        for protocol_kind in protocols_by_config_id[protocol_config.id]:
                            if model.protocol == protocol_kind:
                                available_model_keys.add(
                                    (
                                        _runtime_channel_id(
                                            protocol_config.id, protocol_kind
                                        ),
                                        model.credential_id,
                                        model.model_name,
                                    )
                                )
                    session.add(
                        SiteDiscoveredModelEntity(
                            id=model.id,
                            protocol_config_id=protocol_config.id,
                            credential_id=model.credential_id,
                            model_name=model.model_name,
                            enabled=1 if model.enabled else 0,
                            sort_order=model.sort_order,
                            protocol=model.protocol.value,
                        )
                    )

        return protocol_config_ids, protocols_by_config_id, available_model_keys

    async def _replace_groups(
        self,
        session: AsyncSession,
        groups: list[ModelGroup],
        *,
        available_protocol_config_ids: set[str],
        protocols_by_config_id: dict[str, list[ProtocolKind]],
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
                protocol_config_id = _extract_protocol_config_id(
                    item.channel_id, available_protocol_config_ids
                )
                if protocol_config_id not in available_protocol_config_ids:
                    raise ValueError(
                        f"Model group channel not found in backup sites: {item.channel_id}"
                    )
                resolved_channel_id = _resolve_group_item_channel_id(
                    item.channel_id,
                    known_protocol_config_ids=available_protocol_config_ids,
                    protocols_by_config_id=protocols_by_config_id,
                )
                resolved_protocol = _parse_runtime_channel_protocol(resolved_channel_id)
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
                else (
                    normalize_upstream_headers_config_json(item.value)
                    if item.key == SETTING_UPSTREAM_HEADERS_CONFIG
                    else item.value
                )
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
                    spent_cost_usd=max(item.spent_cost_usd, 0.0),
                    expires_at=parse_optional_datetime(item.expires_at),
                    created_at=parse_optional_datetime(item.created_at) or now,
                    updated_at=parse_optional_datetime(item.updated_at) or now,
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
                    created_at=parse_backup_datetime(item.created_at),
                )
            )
