from __future__ import annotations

import asyncio
import json
import uuid
from datetime import UTC, datetime, timedelta
from time import monotonic
from typing import Any

from sqlalchemy import delete, func, select, update
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from ..core.model_prices import normalize_model_key
from ..models import ModelGroup, ModelGroupCandidateItem, ModelGroupCandidatesRequest, ModelGroupCandidatesResponse, ModelGroupCreate, ModelGroupItem, ModelGroupItemInput, ModelGroupStats, ModelGroupUpdate, ModelPriceItem, ModelPriceListResponse, ModelPriceUpdate, OverviewDailyPoint, OverviewMetrics, OverviewModelAnalytics, OverviewModelMetricPoint, OverviewModelTrendPoint, OverviewSummary, OverviewSummaryMetric, ProtocolKind, RequestLogAttempt, RequestLogDetail, RequestLogItem, RequestLogPage, SettingItem, SiteRuntimeSummary
from .entities import ImportedStatsDailyEntity, ImportedStatsTotalEntity, ModelGroupEntity, ModelGroupItemEntity, ModelPriceEntity, OverviewModelDailyStatsEntity, RequestLogDailyStatsEntity, RequestLogEntity, SettingEntity, SiteCredentialEntity, SiteDiscoveredModelEntity, SiteEntity, SiteProtocolConfigEntity, SiteProtocolCredentialBindingEntity


SETTING_GATEWAY_API_KEYS = "gateway_api_keys"
SETTING_GATEWAY_API_KEY_HINT = "gateway_api_key_hint"
SETTING_MODEL_PRICE_LAST_SYNC_AT = "model_price_last_sync_at"
SETTING_PROXY_URL = "proxy_url"
SETTING_STATS_SAVE_INTERVAL = "stats_save_interval"
SETTING_STATS_LAST_PERSIST_AT = "stats_last_persist_at"
SETTING_CORS_ALLOW_ORIGINS = "cors_allow_origins"
SETTING_RELAY_LOG_KEEP_ENABLED = "relay_log_keep_enabled"
SETTING_RELAY_LOG_KEEP_PERIOD = "relay_log_keep_period"
SETTING_CIRCUIT_BREAKER_THRESHOLD = "circuit_breaker_threshold"
SETTING_CIRCUIT_BREAKER_COOLDOWN = "circuit_breaker_cooldown"
SETTING_CIRCUIT_BREAKER_MAX_COOLDOWN = "circuit_breaker_max_cooldown"
SETTING_HEALTH_WINDOW_SECONDS = "health_window_seconds"
SETTING_HEALTH_PENALTY_WEIGHT = "health_penalty_weight"
SETTING_HEALTH_MIN_SAMPLES = "health_min_samples"
SETTING_SITE_NAME = "site_name"
SETTING_SITE_LOGO_URL = "site_logo_url"


class DomainStore:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory
        self._settings_cache: list[SettingItem] | None = None
        self._settings_cache_at = 0.0
        self._settings_cache_ttl_seconds = 2.0
        self._settings_cache_lock = asyncio.Lock()

    def _clone_settings_items(self, items: list[SettingItem]) -> list[SettingItem]:
        return [SettingItem(key=item.key, value=item.value) for item in items]

    def _store_settings_cache(self, items: list[SettingItem]) -> list[SettingItem]:
        self._settings_cache = self._clone_settings_items(items)
        self._settings_cache_at = monotonic()
        return self._clone_settings_items(items)

    def _clear_settings_cache(self) -> None:
        self._settings_cache = None
        self._settings_cache_at = 0.0

    @staticmethod
    def _is_missing_sqlite_table(exc: OperationalError, table_name: str) -> bool:
        message = str(getattr(exc, "orig", exc)).lower()
        return f"no such table: {table_name}" in message

    async def replace_imported_stats(
        self,
        *,
        total: dict[str, int | float] | list[dict[str, int | float]] | None,
        daily: list[dict[str, int | float | str]],
        model_prices: list[dict[str, int | float | str]],
    ) -> None:
        async with self._session_factory() as session:
            await session.execute(delete(ImportedStatsDailyEntity))
            await session.execute(delete(ImportedStatsTotalEntity))
            await session.execute(delete(RequestLogDailyStatsEntity))
            await session.execute(delete(OverviewModelDailyStatsEntity))
            await session.execute(delete(ModelPriceEntity))
            await session.execute(update(RequestLogEntity).values(stats_archived=0))

            total_item = self._normalize_total_payload(total)

            if total_item is not None:
                session.add(
                    ImportedStatsTotalEntity(
                        id=1,
                        input_token=int(total_item.get("input_token") or 0),
                        output_token=int(total_item.get("output_token") or 0),
                        input_cost=float(total_item.get("input_cost") or 0.0),
                        output_cost=float(total_item.get("output_cost") or 0.0),
                        wait_time=int(total_item.get("wait_time") or 0),
                        request_success=int(total_item.get("request_success") or 0),
                        request_failed=int(total_item.get("request_failed") or 0),
                    )
                )

            for item in daily:
                date_value = str(item.get("date") or "")
                if len(date_value) != 8:
                    continue
                session.add(
                    ImportedStatsDailyEntity(
                        date=date_value,
                        input_token=int(item.get("input_token") or 0),
                        output_token=int(item.get("output_token") or 0),
                        input_cost=float(item.get("input_cost") or 0.0),
                        output_cost=float(item.get("output_cost") or 0.0),
                        wait_time=int(item.get("wait_time") or 0),
                        request_success=int(item.get("request_success") or 0),
                        request_failed=int(item.get("request_failed") or 0),
                    )
                )

            for item in model_prices:
                key = str(item.get("model_key") or "").strip().lower()
                if not key:
                    continue
                session.add(
                    ModelPriceEntity(
                        model_key=key,
                        display_name=str(item.get("display_name") or key),
                        input_price_per_million=float(item.get("input_price_per_million") or 0.0),
                        output_price_per_million=float(item.get("output_price_per_million") or 0.0),
                        cache_read_price_per_million=float(item.get("cache_read_price_per_million") or 0.0),
                        cache_write_price_per_million=float(item.get("cache_write_price_per_million") or 0.0),
                    )
                )

            await session.commit()

    async def list_group_names(self, *, include_routed: bool = False) -> list[str]:
        async with self._session_factory() as session:
            query = select(ModelGroupEntity.name).order_by(ModelGroupEntity.name.asc())
            if not include_routed:
                query = query.where(ModelGroupEntity.route_group_id == "")
            rows = await session.execute(query)
            return [str(item) for item in rows.scalars().all() if str(item).strip()]

    async def prune_model_prices_to_groups(self, *, include_routed: bool = False) -> None:
        group_names = await self.list_group_names(include_routed=include_routed)
        normalized_keys = {normalize_model_key(item) for item in group_names if normalize_model_key(item)}
        async with self._session_factory() as session:
            if normalized_keys:
                await session.execute(delete(ModelPriceEntity).where(ModelPriceEntity.model_key.not_in(normalized_keys)))
            else:
                await session.execute(delete(ModelPriceEntity))
            await session.commit()

    async def replace_model_prices(self, model_prices: list[dict[str, int | float | str]]) -> None:
        async with self._session_factory() as session:
            await session.execute(delete(ModelPriceEntity))
            for item in model_prices:
                key = normalize_model_key(str(item.get("model_key") or ""))
                if not key:
                    continue
                session.add(
                    ModelPriceEntity(
                        model_key=key,
                        display_name=str(item.get("display_name") or key),
                        input_price_per_million=float(item.get("input_price_per_million") or 0.0),
                        output_price_per_million=float(item.get("output_price_per_million") or 0.0),
                        cache_read_price_per_million=float(item.get("cache_read_price_per_million") or 0.0),
                        cache_write_price_per_million=float(item.get("cache_write_price_per_million") or 0.0),
                    )
                )
            await session.commit()

    async def sync_model_prices(
        self,
        model_prices: list[dict[str, int | float | str]],
        *,
        overwrite_existing: bool,
        allowed_keys: list[str] | None = None,
    ) -> None:
        async with self._session_factory() as session:
            existing_rows = (
                await session.execute(select(ModelPriceEntity))
            ).scalars().all()
            entities_by_key = {item.model_key: item for item in existing_rows}

            for item in model_prices:
                key = normalize_model_key(str(item.get("model_key") or ""))
                if not key:
                    continue
                entity = entities_by_key.get(key)
                if entity is None:
                    session.add(
                        ModelPriceEntity(
                            model_key=key,
                            display_name=str(item.get("display_name") or key),
                            input_price_per_million=float(item.get("input_price_per_million") or 0.0),
                            output_price_per_million=float(item.get("output_price_per_million") or 0.0),
                            cache_read_price_per_million=float(item.get("cache_read_price_per_million") or 0.0),
                            cache_write_price_per_million=float(item.get("cache_write_price_per_million") or 0.0),
                        )
                    )
                    continue
                if overwrite_existing:
                    entity.display_name = str(item.get("display_name") or entity.display_name or key)
                    entity.input_price_per_million = float(item.get("input_price_per_million") or 0.0)
                    entity.output_price_per_million = float(item.get("output_price_per_million") or 0.0)
                    entity.cache_read_price_per_million = float(item.get("cache_read_price_per_million") or 0.0)
                    entity.cache_write_price_per_million = float(item.get("cache_write_price_per_million") or 0.0)

            if allowed_keys is not None:
                normalized_allowed_keys = {normalize_model_key(item) for item in allowed_keys if normalize_model_key(item)}
                if normalized_allowed_keys:
                    await session.execute(delete(ModelPriceEntity).where(ModelPriceEntity.model_key.not_in(normalized_allowed_keys)))
                else:
                    await session.execute(delete(ModelPriceEntity))

            await session.commit()

    async def list_model_prices(self) -> ModelPriceListResponse:
        async with self._session_factory() as session:
            price_rows = (
                await session.execute(select(ModelPriceEntity).order_by(ModelPriceEntity.display_name.asc(), ModelPriceEntity.model_key.asc()))
            ).scalars().all()
            group_rows = (
                await session.execute(
                    select(ModelGroupEntity.name, ModelGroupEntity.protocol)
                    .where(ModelGroupEntity.route_group_id == "")
                    .order_by(ModelGroupEntity.name.asc())
                )
            ).all()
            last_synced_at = await session.get(SettingEntity, SETTING_MODEL_PRICE_LAST_SYNC_AT)

        prices_by_key = {item.model_key: item for item in price_rows}
        protocols_by_key: dict[str, set[ProtocolKind]] = {}
        display_names_by_key: dict[str, str] = {}
        for name, protocol in group_rows:
            key = normalize_model_key(str(name))
            if not key:
                continue
            protocols_by_key.setdefault(key, set()).add(ProtocolKind(str(protocol)))
            display_names_by_key.setdefault(key, str(name))

        for key, price_entity in prices_by_key.items():
            if key not in display_names_by_key:
                display_names_by_key[key] = str(price_entity.display_name or key)

        items: list[ModelPriceItem] = []
        for key in sorted(display_names_by_key, key=lambda item: display_names_by_key[item].lower()):
            price_entity = prices_by_key.get(key)
            items.append(
                ModelPriceItem(
                    model_key=key,
                    display_name=display_names_by_key[key],
                    protocols=sorted(protocols_by_key.get(key, set()), key=lambda value: value.value),
                    input_price_per_million=float(price_entity.input_price_per_million) if price_entity is not None else 0.0,
                    output_price_per_million=float(price_entity.output_price_per_million) if price_entity is not None else 0.0,
                    cache_read_price_per_million=float(price_entity.cache_read_price_per_million) if price_entity is not None else 0.0,
                    cache_write_price_per_million=float(price_entity.cache_write_price_per_million) if price_entity is not None else 0.0,
                )
            )

        return ModelPriceListResponse(
            items=items,
            last_synced_at=last_synced_at.value if last_synced_at is not None and last_synced_at.value.strip() else None,
        )

    async def upsert_model_price(self, payload: ModelPriceUpdate) -> ModelPriceItem:
        model_key = normalize_model_key(payload.model_key)
        if not model_key:
            raise ValueError('Model key is required')

        async with self._session_factory() as session:
            group_rows = (
                await session.execute(
                    select(ModelGroupEntity.name, ModelGroupEntity.protocol)
                    .where(ModelGroupEntity.route_group_id == "")
                )
            ).all()
            matched_groups = [
                (str(name), ProtocolKind(str(protocol)))
                for name, protocol in group_rows
                if normalize_model_key(str(name)) == model_key
            ]
            if not matched_groups:
                raise ValueError('Model price can only be maintained for existing model groups')

            entity = await session.get(ModelPriceEntity, model_key)
            display_name = payload.display_name.strip() or matched_groups[0][0]
            if entity is None:
                entity = ModelPriceEntity(
                    model_key=model_key,
                    display_name=display_name,
                    input_price_per_million=float(payload.input_price_per_million),
                    output_price_per_million=float(payload.output_price_per_million),
                    cache_read_price_per_million=float(payload.cache_read_price_per_million),
                    cache_write_price_per_million=float(payload.cache_write_price_per_million),
                )
                session.add(entity)
            else:
                entity.display_name = display_name
                entity.input_price_per_million = float(payload.input_price_per_million)
                entity.output_price_per_million = float(payload.output_price_per_million)
                entity.cache_read_price_per_million = float(payload.cache_read_price_per_million)
                entity.cache_write_price_per_million = float(payload.cache_write_price_per_million)

            await session.commit()

        protocols = sorted({protocol for _, protocol in matched_groups}, key=lambda value: value.value)

        return ModelPriceItem(
            model_key=model_key,
            display_name=display_name,
            protocols=protocols,
            input_price_per_million=float(payload.input_price_per_million),
            output_price_per_million=float(payload.output_price_per_million),
            cache_read_price_per_million=float(payload.cache_read_price_per_million),
            cache_write_price_per_million=float(payload.cache_write_price_per_million),
        )

    async def set_model_price_sync_time(self, value: str) -> None:
        async with self._session_factory() as session:
            entity = await session.get(SettingEntity, SETTING_MODEL_PRICE_LAST_SYNC_AT)
            if entity is None:
                session.add(SettingEntity(key=SETTING_MODEL_PRICE_LAST_SYNC_AT, value=value))
            else:
                entity.value = value
            await session.commit()

    async def list_groups(self) -> list[ModelGroup]:
        async with self._session_factory() as session:
            entities = (
                await session.execute(select(ModelGroupEntity).order_by(ModelGroupEntity.name))
            ).scalars().all()
            return await self._hydrate_groups(session, entities)

    async def get_group(self, group_id: str) -> ModelGroup:
        async with self._session_factory() as session:
            entity = await session.get(ModelGroupEntity, group_id)
            if entity is None:
                raise KeyError(group_id)
            hydrated = await self._hydrate_groups(session, [entity])
            return hydrated[0]

    async def find_group_by_name(self, protocol: str, name: str | None) -> ModelGroup | None:
        if not name:
            return None

        async with self._session_factory() as session:
            result = await session.execute(
                select(ModelGroupEntity)
                .where(ModelGroupEntity.protocol == protocol)
                .where(ModelGroupEntity.name == name)
                .limit(1)
            )
            entity = result.scalar_one_or_none()
            if entity is None:
                return None
            hydrated = await self._hydrate_groups(session, [entity])
            return hydrated[0]

    async def list_group_candidates(self, payload: ModelGroupCandidatesRequest) -> ModelGroupCandidatesResponse:
        async with self._session_factory() as session:
            query = select(SiteProtocolConfigEntity).order_by(SiteProtocolConfigEntity.protocol.asc(), SiteProtocolConfigEntity.id.asc())
            if payload.protocol is not None:
                query = query.where(SiteProtocolConfigEntity.protocol == payload.protocol.value)
            channels = (await session.execute(query)).scalars().all()
            channel_ids = [item.id for item in channels]
            discovered_models = []
            if channel_ids:
                discovered_models = (
                    await session.execute(
                        select(SiteDiscoveredModelEntity)
                        .where(SiteDiscoveredModelEntity.protocol_config_id.in_(channel_ids))
                        .where(SiteDiscoveredModelEntity.enabled == 1)
                        .order_by(SiteDiscoveredModelEntity.protocol_config_id.asc(), SiteDiscoveredModelEntity.sort_order.asc(), SiteDiscoveredModelEntity.id.asc())
                    )
                ).scalars().all()
            channel_rows = []
            if channel_ids:
                from .entities import SiteBaseUrlEntity
                channel_rows = (
                    await session.execute(
                        select(SiteProtocolConfigEntity.id, SiteEntity.name, SiteEntity.id.label("site_id"))
                        .join(SiteEntity, SiteEntity.id == SiteProtocolConfigEntity.site_id)
                        .where(SiteProtocolConfigEntity.id.in_(channel_ids))
                    )
                ).all()
                site_ids_for_urls = sorted({row.site_id for row in channel_rows})
                base_url_rows = (
                    await session.execute(
                        select(SiteBaseUrlEntity)
                        .where(SiteBaseUrlEntity.site_id.in_(site_ids_for_urls), SiteBaseUrlEntity.enabled == 1)
                        .order_by(SiteBaseUrlEntity.site_id.asc(), SiteBaseUrlEntity.sort_order.asc())
                    )
                ).scalars().all() if site_ids_for_urls else []
                first_url_by_site: dict[str, str] = {}
                for row in base_url_rows:
                    if row.site_id not in first_url_by_site:
                        first_url_by_site[row.site_id] = row.url

        candidates: list[ModelGroupCandidateItem] = []
        seen: set[tuple[str, str, str]] = set()
        excluded = {(item.channel_id, item.credential_id, item.model_name) for item in payload.exclude_items}
        credential_rows = []
        credential_ids = sorted({item.credential_id for item in discovered_models if item.credential_id})
        if credential_ids:
            async with self._session_factory() as session:
                credential_rows = (
                    await session.execute(select(SiteCredentialEntity).where(SiteCredentialEntity.id.in_(credential_ids)))
                ).scalars().all()
        credential_names = {item.id: item.name for item in credential_rows}

        models_by_channel: dict[str, list[tuple[str, str]]] = {}
        for item in discovered_models:
            models_by_channel.setdefault(item.protocol_config_id, []).append((item.credential_id, item.model_name))

        channel_meta_by_id = {
            channel_id: {
                "name": site_name,
                "base_url": first_url_by_site.get(site_id, ""),
            }
            for channel_id, site_name, site_id in channel_rows
        }

        for channel in channels:
            channel_items = list(dict.fromkeys(models_by_channel.get(channel.id, [])))
            for credential_id, model_name in channel_items:
                candidate_key = (channel.id, credential_id, model_name)
                wildcard_key = (channel.id, "", model_name)
                if candidate_key in seen or candidate_key in excluded or wildcard_key in excluded:
                    continue
                seen.add(candidate_key)
                meta = channel_meta_by_id.get(channel.id, {})
                candidates.append(
                    ModelGroupCandidateItem(
                        channel_id=channel.id,
                        channel_name=str(meta.get("name") or channel.protocol),
                        credential_id=credential_id,
                        credential_name=credential_names.get(credential_id, ""),
                        base_url=str(meta.get("base_url") or ""),
                        model_name=model_name,
                    )
                )

        return ModelGroupCandidatesResponse(candidates=candidates)

    async def list_group_stats(self) -> list[ModelGroupStats]:
        async with self._session_factory() as session:
            groups = (
                await session.execute(select(ModelGroupEntity).order_by(ModelGroupEntity.name))
            ).scalars().all()
            grouped_rows = (
                await session.execute(
                    select(
                        RequestLogEntity.resolved_group_name,
                        func.count(RequestLogEntity.id),
                        func.sum(RequestLogEntity.success),
                        func.sum(RequestLogEntity.total_tokens),
                        func.sum(RequestLogEntity.total_cost_usd),
                        func.avg(RequestLogEntity.latency_ms),
                    )
                    .where(RequestLogEntity.resolved_group_name.is_not(None))
                    .group_by(RequestLogEntity.resolved_group_name)
                )
            ).all()

            last_model_rows = (
                await session.execute(
                    select(
                        RequestLogEntity.resolved_group_name,
                        RequestLogEntity.upstream_model_name,
                    )
                    .where(RequestLogEntity.resolved_group_name.is_not(None))
                    .where(RequestLogEntity.upstream_model_name.is_not(None))
                    .order_by(RequestLogEntity.created_at.desc(), RequestLogEntity.id.desc())
                )
            ).all()

        aggregates = {
            str(name): {
                "request_count": int(request_count or 0),
                "success_count": int(success_count or 0),
                "total_tokens": int(total_tokens or 0),
                "total_cost_usd": float(total_cost_usd or 0.0),
                "avg_latency_ms": int(avg_latency_ms or 0),
            }
            for name, request_count, success_count, total_tokens, total_cost_usd, avg_latency_ms in grouped_rows
            if name
        }

        last_models: dict[str, str] = {}
        for group_name, upstream_model_name in last_model_rows:
            if not group_name or not upstream_model_name:
                continue
            key = str(group_name)
            if key not in last_models:
                last_models[key] = str(upstream_model_name)

        items: list[ModelGroupStats] = []
        for group in groups:
            aggregate = aggregates.get(group.name, {})
            request_count = int(aggregate.get("request_count", 0))
            success_count = int(aggregate.get("success_count", 0))
            items.append(
                ModelGroupStats(
                    name=group.name,
                    request_count=request_count,
                    success_count=success_count,
                    failed_count=max(request_count - success_count, 0),
                    total_tokens=int(aggregate.get("total_tokens", 0)),
                    total_cost_usd=round(float(aggregate.get("total_cost_usd", 0.0)), 6),
                    avg_latency_ms=int(aggregate.get("avg_latency_ms", 0)),
                    last_resolved_model=last_models.get(group.name),
                )
            )
        return items

    async def create_group(self, payload: ModelGroupCreate) -> ModelGroup:
        async with self._session_factory() as session:
            route_group, channels_by_id, channel_site_names = await self._validate_group_payload(
                session,
                payload.protocol.value,
                payload.name,
                payload.items,
                payload.route_group_id,
            )
            entity = ModelGroupEntity(
                id=str(uuid.uuid4()),
                name=payload.name.strip(),
                protocol=payload.protocol.value,
                strategy=payload.strategy.value,
                route_group_id=route_group.id if route_group is not None else "",
            )
            session.add(entity)
            await session.flush()
            await self._replace_group_items(session, entity.id, payload.items, channels_by_id, channel_site_names)
            await session.commit()
            await session.refresh(entity)
            hydrated = await self._hydrate_groups(session, [entity])
            return hydrated[0]

    async def update_group(self, group_id: str, payload: ModelGroupUpdate) -> ModelGroup:
        async with self._session_factory() as session:
            entity = await session.get(ModelGroupEntity, group_id)
            if entity is None:
                raise KeyError(group_id)

            next_protocol = payload.protocol.value if payload.protocol is not None else entity.protocol
            next_name = payload.name if payload.name is not None else entity.name
            next_route_group_id = payload.route_group_id if payload.route_group_id is not None else entity.route_group_id
            inbound_route_group_result = await session.execute(
                select(ModelGroupEntity.id)
                .where(ModelGroupEntity.route_group_id == group_id)
                .where(ModelGroupEntity.id != group_id)
                .limit(1)
            )
            has_inbound_route_group = (
                inbound_route_group_result.scalar_one_or_none() is not None
            )
            if next_protocol != entity.protocol and has_inbound_route_group:
                raise ValueError('Execution groups referenced by route groups cannot change protocol')
            if next_route_group_id and has_inbound_route_group:
                raise ValueError('Execution groups referenced by route groups cannot become route groups')
            current_items = await self._load_group_items(session, [group_id])
            next_items = (
                payload.items if payload.items is not None else [
                    ModelGroupItemInput(channel_id=item.channel_id, credential_id=item.credential_id, model_name=item.model_name, enabled=item.enabled)
                    for item in current_items.get(group_id, [])
                ]
            )
            route_group, channels_by_id, channel_site_names = await self._validate_group_payload(
                session,
                next_protocol,
                next_name,
                next_items,
                next_route_group_id,
                exclude_group_id=group_id,
            )

            changes = payload.model_dump(exclude_unset=True)
            for key, value in changes.items():
                if key == "protocol" and value is not None:
                    entity.protocol = value.value
                elif key == "strategy" and value is not None:
                    entity.strategy = value.value
                elif key == "items" and value is not None:
                    continue
                elif key == "route_group_id":
                    entity.route_group_id = route_group.id if route_group is not None else ""
                else:
                    setattr(entity, key, value)

            if payload.items is not None or payload.protocol is not None:
                await session.execute(delete(ModelGroupItemEntity).where(ModelGroupItemEntity.group_id == group_id))
                await self._replace_group_items(session, group_id, next_items, channels_by_id, channel_site_names)

            await session.commit()
            await session.refresh(entity)
            hydrated = await self._hydrate_groups(session, [entity])
            return hydrated[0]

    async def delete_group(self, group_id: str) -> None:
        async with self._session_factory() as session:
            entity = await session.get(ModelGroupEntity, group_id)
            if entity is None:
                raise KeyError(group_id)
            inbound_route_group = await session.execute(
                select(ModelGroupEntity.id)
                .where(ModelGroupEntity.route_group_id == group_id)
                .where(ModelGroupEntity.id != group_id)
                .limit(1)
            )
            if inbound_route_group.scalar_one_or_none() is not None:
                raise ValueError('Model group is still referenced by route groups')
            await session.execute(delete(ModelGroupItemEntity).where(ModelGroupItemEntity.group_id == group_id))
            await session.delete(entity)
            await session.commit()

    async def _validate_group_payload(
        self,
        session: AsyncSession,
        protocol: str,
        name: str,
        items: list[ModelGroupItemInput],
        route_group_id: str = "",
        exclude_group_id: str | None = None,
    ) -> tuple[ModelGroupEntity | None, dict[str, SiteProtocolConfigEntity], dict[str, str]]:
        normalized_name = name.strip()
        if not normalized_name:
            raise ValueError('Model group name is required')

        result = await session.execute(
            select(ModelGroupEntity.id)
            .where(ModelGroupEntity.protocol == protocol)
            .where(ModelGroupEntity.name == normalized_name)
            .limit(1)
        )
        existing_id = result.scalar_one_or_none()
        if existing_id is not None and existing_id != exclude_group_id:
            raise ValueError(f'Model group already exists for protocol={protocol}: {normalized_name}')

        normalized_route_group_id = route_group_id.strip()
        route_group: ModelGroupEntity | None = None
        if normalized_route_group_id:
            if exclude_group_id is not None and normalized_route_group_id == exclude_group_id:
                raise ValueError('Model group cannot route to itself')
            route_group = await session.get(ModelGroupEntity, normalized_route_group_id)
            if route_group is None:
                raise ValueError(f'Route target model group not found: {normalized_route_group_id}')
            if route_group.protocol != protocol:
                raise ValueError(f'Route target protocol mismatch: {route_group.name}')
            if route_group.route_group_id.strip():
                raise ValueError(f'Route target must be an execution group: {route_group.name}')

        if not items:
            return route_group, {}, {}

        channel_ids = list(dict.fromkeys(item.channel_id for item in items))
        channel_result = await session.execute(select(SiteProtocolConfigEntity).where(SiteProtocolConfigEntity.id.in_(channel_ids)))
        channel_rows = channel_result.scalars().all()
        channels_by_id = {row.id: row for row in channel_rows}
        channel_site_names = {}
        site_rows = (
            await session.execute(
                select(SiteProtocolConfigEntity.id, SiteEntity.name)
                .join(SiteEntity, SiteEntity.id == SiteProtocolConfigEntity.site_id)
                .where(SiteProtocolConfigEntity.id.in_(channel_ids))
            )
        ).all()
        channel_site_names = {channel_id: site_name for channel_id, site_name in site_rows}
        existing_channel_ids = set(channels_by_id)
        missing_channel_ids = [channel_id for channel_id in channel_ids if channel_id not in existing_channel_ids]
        if missing_channel_ids:
            raise ValueError(f'Channels not found: {", ".join(missing_channel_ids)}')

        from ..gateway.converters import can_reach_protocol
        from ..models import ProtocolKind
        invalid_channel_ids = [
            channel.id for channel in channel_rows
            if not can_reach_protocol(ProtocolKind(channel.protocol), ProtocolKind(protocol))
        ]
        if invalid_channel_ids:
            raise ValueError(f'Channels cannot reach protocol={protocol}: {", ".join(invalid_channel_ids)}')

        model_rows = (
            await session.execute(
                select(SiteDiscoveredModelEntity)
                .where(SiteDiscoveredModelEntity.protocol_config_id.in_(channel_ids))
                .where(SiteDiscoveredModelEntity.enabled == 1)
            )
        ).scalars().all()
        model_names_by_channel: dict[str, set[tuple[str, str]]] = {}
        for row in model_rows:
            model_names_by_channel.setdefault(row.protocol_config_id, set()).add((row.credential_id, row.model_name))

        for item in items:
            channel_models = model_names_by_channel.get(item.channel_id, set())
            target = (item.credential_id, item.model_name) if item.credential_id else None
            if target is not None:
                if target not in channel_models:
                    raise ValueError(f'Model not found in channel {item.channel_id} credential={item.credential_id}: {item.model_name}')
            elif not any(model_name == item.model_name for _, model_name in channel_models):
                raise ValueError(f'Model not found in channel {item.channel_id}: {item.model_name}')

        return route_group, channels_by_id, channel_site_names

    async def _hydrate_groups(self, session: AsyncSession, entities: list[ModelGroupEntity]) -> list[ModelGroup]:
        if not entities:
            return []
        items_by_group = await self._load_group_items(session, [item.id for item in entities])
        route_group_ids = [item.route_group_id for item in entities if item.route_group_id.strip()]
        route_name_by_id: dict[str, str] = {}
        if route_group_ids:
            route_rows = (
                await session.execute(
                    select(ModelGroupEntity.id, ModelGroupEntity.name)
                    .where(ModelGroupEntity.id.in_(sorted(set(route_group_ids))))
                )
            ).all()
            route_name_by_id = {str(group_id): str(group_name) for group_id, group_name in route_rows}
        prices_by_key = await self._load_model_prices_by_keys(
            session, [normalize_model_key(item.name) for item in entities]
        )
        return [
            self._to_group(
                item,
                items_by_group.get(item.id, []),
                prices_by_key.get(normalize_model_key(item.name)),
                route_name_by_id.get(item.route_group_id, ""),
            )
            for item in entities
        ]

    async def _load_model_prices_by_keys(
        self, session: AsyncSession, keys: list[str]
    ) -> dict[str, ModelPriceEntity]:
        normalized_keys = [key for key in dict.fromkeys(keys) if key]
        if not normalized_keys:
            return {}

        rows = (
            await session.execute(
                select(ModelPriceEntity).where(ModelPriceEntity.model_key.in_(normalized_keys))
            )
        ).scalars().all()
        return {row.model_key: row for row in rows}

    async def _load_group_items(self, session: AsyncSession, group_ids: list[str]) -> dict[str, list[ModelGroupItem]]:
        if not group_ids:
            return {}

        rows = (
            await session.execute(
                select(ModelGroupItemEntity)
                .where(ModelGroupItemEntity.group_id.in_(group_ids))
                .order_by(ModelGroupItemEntity.group_id.asc(), ModelGroupItemEntity.sort_order.asc(), ModelGroupItemEntity.id.asc())
            )
        ).scalars().all()

        items_by_group: dict[str, list[ModelGroupItem]] = {group_id: [] for group_id in group_ids}
        channel_ids = list({row.channel_id for row in rows})
        channel_site_names = await self._load_channel_site_names(session, channel_ids)
        credential_names_by_channel = await self._load_credential_names_by_channel(session, channel_ids)
        for row in rows:
            items_by_group.setdefault(row.group_id, []).append(
                ModelGroupItem(
                    channel_id=row.channel_id,
                    channel_name=channel_site_names.get(row.channel_id, ''),
                    credential_id=row.credential_id,
                    credential_name=credential_names_by_channel.get(row.channel_id, {}).get(row.credential_id, ''),
                    model_name=row.model_name,
                    enabled=bool(row.enabled),
                    sort_order=row.sort_order,
                )
            )
        return items_by_group

    async def _replace_group_items(
        self,
        session: AsyncSession,
        group_id: str,
        items: list[ModelGroupItemInput],
        channels_by_id: dict[str, SiteProtocolConfigEntity],
        channel_site_names: dict[str, str],
    ) -> None:
        for index, item in enumerate(items):
            session.add(
                ModelGroupItemEntity(
                    group_id=group_id,
                    channel_id=item.channel_id,
                    credential_id=item.credential_id,
                    model_name=item.model_name,
                    enabled=1 if item.enabled else 0,
                    sort_order=index,
                )
            )

    async def _load_channel_site_names(self, session: AsyncSession, channel_ids: list[str]) -> dict[str, str]:
        if not channel_ids:
            return {}
        rows = (
            await session.execute(
                select(SiteProtocolConfigEntity.id, SiteEntity.name)
                .join(SiteEntity, SiteEntity.id == SiteProtocolConfigEntity.site_id)
                .where(SiteProtocolConfigEntity.id.in_(channel_ids))
            )
        ).all()
        return {channel_id: site_name for channel_id, site_name in rows}

    async def _load_credential_names_by_channel(self, session: AsyncSession, channel_ids: list[str]) -> dict[str, dict[str, str]]:
        if not channel_ids:
            return {}
        rows = await session.execute(
            select(
                SiteProtocolCredentialBindingEntity.protocol_config_id,
                SiteProtocolCredentialBindingEntity.credential_id,
                SiteCredentialEntity.name,
            )
            .join(
                SiteCredentialEntity,
                SiteCredentialEntity.id == SiteProtocolCredentialBindingEntity.credential_id,
            )
            .where(SiteProtocolCredentialBindingEntity.protocol_config_id.in_(channel_ids))
        )
        credential_names_by_channel: dict[str, dict[str, str]] = {}
        for protocol_config_id, credential_id, credential_name in rows.all():
            credential_names_by_channel.setdefault(protocol_config_id, {})[credential_id] = credential_name
        return credential_names_by_channel

    async def get_gateway_auth_config(self) -> dict[str, Any]:
        items = await self.list_settings()
        mapping = {item.key: item.value for item in items}
        keys = self._split_gateway_keys(mapping.get(SETTING_GATEWAY_API_KEYS, ""))
        require_api_key = bool(keys)
        return {
            "keys": keys,
            "require_api_key": require_api_key,
            "hint": mapping.get(SETTING_GATEWAY_API_KEY_HINT, ""),
        }

    async def get_runtime_settings(self) -> dict[str, Any]:
        items = await self.list_settings()
        mapping = {item.key: item.value for item in items}
        cors_allow_origins = self._split_comma_lines(mapping.get(SETTING_CORS_ALLOW_ORIGINS, ""))
        return {
            "proxy_url": mapping.get(SETTING_PROXY_URL, "").strip(),
            "stats_save_interval": self._parse_int(mapping.get(SETTING_STATS_SAVE_INTERVAL), default=60),
            "cors_allow_origins": cors_allow_origins or ["*"],
            "relay_log_keep_enabled": self._parse_bool(mapping.get(SETTING_RELAY_LOG_KEEP_ENABLED), default=True),
            "relay_log_keep_period": self._parse_int(mapping.get(SETTING_RELAY_LOG_KEEP_PERIOD), default=7),
            "circuit_breaker_threshold": self._parse_int(mapping.get(SETTING_CIRCUIT_BREAKER_THRESHOLD), default=3),
            "circuit_breaker_cooldown": self._parse_int(mapping.get(SETTING_CIRCUIT_BREAKER_COOLDOWN), default=60),
            "circuit_breaker_max_cooldown": self._parse_int(mapping.get(SETTING_CIRCUIT_BREAKER_MAX_COOLDOWN), default=600),
            "health_window_seconds": self._parse_int(mapping.get(SETTING_HEALTH_WINDOW_SECONDS), default=300),
            "health_penalty_weight": self._parse_float(mapping.get(SETTING_HEALTH_PENALTY_WEIGHT), default=0.5),
            "health_min_samples": self._parse_int(mapping.get(SETTING_HEALTH_MIN_SAMPLES), default=10),
            "site_name": mapping.get(SETTING_SITE_NAME, "Lens").strip() or "Lens",
            "site_logo_url": mapping.get(SETTING_SITE_LOGO_URL, "").strip(),
        }

    async def get_branding_settings(self) -> dict[str, str]:
        runtime = await self.get_runtime_settings()
        return {
            "site_name": str(runtime["site_name"]),
            "site_logo_url": str(runtime["site_logo_url"]),
        }

    async def list_settings(self) -> list[SettingItem]:
        cached = self._settings_cache
        if cached is not None and (monotonic() - self._settings_cache_at) < self._settings_cache_ttl_seconds:
            return self._clone_settings_items(cached)

        async with self._settings_cache_lock:
            cached = self._settings_cache
            if cached is not None and (monotonic() - self._settings_cache_at) < self._settings_cache_ttl_seconds:
                return self._clone_settings_items(cached)

            async with self._session_factory() as session:
                result = await session.execute(select(SettingEntity).order_by(SettingEntity.key))
                items = [SettingItem(key=item.key, value=item.value) for item in result.scalars().all()]
            return self._store_settings_cache(items)

    async def upsert_settings(self, items: list[SettingItem]) -> list[SettingItem]:
        async with self._session_factory() as session:
            for item in items:
                entity = await session.get(SettingEntity, item.key)
                if entity is None:
                    session.add(SettingEntity(key=item.key, value=item.value))
                else:
                    entity.value = item.value
            await session.commit()
            result = await session.execute(select(SettingEntity).order_by(SettingEntity.key))
            stored_items = [SettingItem(key=item.key, value=item.value) for item in result.scalars().all()]
        return self._store_settings_cache(stored_items)

    async def persist_request_log_stats(self, *, force: bool = False) -> None:
        runtime = await self.get_runtime_settings()
        interval_seconds = max(int(runtime["stats_save_interval"]), 1)
        now = datetime.now(UTC).replace(tzinfo=None)
        today_key = now.strftime("%Y%m%d")

        async with self._session_factory() as session:
            try:
                await session.execute(select(RequestLogDailyStatsEntity.date).limit(1))
                await session.execute(select(OverviewModelDailyStatsEntity.date).limit(1))
            except OperationalError as exc:
                if self._is_missing_sqlite_table(exc, "request_log_daily_stats") or self._is_missing_sqlite_table(exc, "overview_model_daily_stats"):
                    return
                raise

            if not force:
                last_persist_setting = await session.get(SettingEntity, SETTING_STATS_LAST_PERSIST_AT)
                if last_persist_setting is None:
                    session.add(SettingEntity(key=SETTING_STATS_LAST_PERSIST_AT, value=now.isoformat()))
                    await session.commit()
                    return
                try:
                    last_persist_at = datetime.fromisoformat(last_persist_setting.value.strip()) if last_persist_setting.value.strip() else None
                except ValueError:
                    last_persist_setting.value = now.isoformat()
                    await session.commit()
                    return
                if last_persist_at is None or (now - last_persist_at).total_seconds() < interval_seconds:
                    return

                await session.execute(
                    delete(RequestLogDailyStatsEntity).where(RequestLogDailyStatsEntity.date == today_key)
                )
                await session.execute(
                    delete(OverviewModelDailyStatsEntity).where(OverviewModelDailyStatsEntity.date == today_key)
                )
                await session.execute(
                    update(RequestLogEntity)
                    .where(RequestLogEntity.stats_archived == 1)
                    .where(func.strftime('%Y%m%d', RequestLogEntity.created_at) == today_key)
                    .values(stats_archived=0)
                )

            date_expr = func.strftime('%Y%m%d', RequestLogEntity.created_at)
            unarchived_stmt = (
                select(
                    date_expr.label('date'),
                    func.count().label('request_count'),
                    func.sum(RequestLogEntity.success).label('successful_requests'),
                    (func.count() - func.sum(RequestLogEntity.success)).label('failed_requests'),
                    func.sum(RequestLogEntity.latency_ms).label('wait_time_ms'),
                    func.sum(RequestLogEntity.input_tokens).label('input_tokens'),
                    func.sum(RequestLogEntity.output_tokens).label('output_tokens'),
                    func.sum(RequestLogEntity.total_tokens).label('total_tokens'),
                    func.sum(RequestLogEntity.input_cost_usd).label('input_cost_usd'),
                    func.sum(RequestLogEntity.output_cost_usd).label('output_cost_usd'),
                    func.sum(RequestLogEntity.total_cost_usd).label('total_cost_usd'),
                )
                .where(RequestLogEntity.stats_archived == 0)
                .group_by(date_expr)
            )
            if not force:
                unarchived_stmt = unarchived_stmt.where(date_expr < today_key)
            daily_rows = (await session.execute(unarchived_stmt)).all()

            model_expr = func.coalesce(RequestLogEntity.resolved_group_name, RequestLogEntity.requested_group_name)
            model_stmt = (
                select(
                    date_expr.label('date'),
                    model_expr.label('model'),
                    func.sum(RequestLogEntity.success).label('requests'),
                    func.sum(RequestLogEntity.total_tokens).label('total_tokens'),
                    func.sum(RequestLogEntity.total_cost_usd).label('total_cost_usd'),
                )
                .where(RequestLogEntity.stats_archived == 0)
                .where(RequestLogEntity.success == 1)
                .where(model_expr.is_not(None))
                .group_by(date_expr, model_expr)
            )
            if not force:
                model_stmt = model_stmt.where(date_expr < today_key)
            model_rows = (await session.execute(model_stmt)).all()

            for row in daily_rows:
                entity = await session.get(RequestLogDailyStatsEntity, str(row.date))
                if entity is None:
                    entity = RequestLogDailyStatsEntity(
                        date=str(row.date),
                        request_count=0,
                        successful_requests=0,
                        failed_requests=0,
                        wait_time_ms=0,
                        input_tokens=0,
                        output_tokens=0,
                        total_tokens=0,
                        input_cost_usd=0.0,
                        output_cost_usd=0.0,
                        total_cost_usd=0.0,
                    )
                    session.add(entity)
                entity.request_count += int(row.request_count or 0)
                entity.successful_requests += int(row.successful_requests or 0)
                entity.failed_requests += int(row.failed_requests or 0)
                entity.wait_time_ms += int(row.wait_time_ms or 0)
                entity.input_tokens += int(row.input_tokens or 0)
                entity.output_tokens += int(row.output_tokens or 0)
                entity.total_tokens += int(row.total_tokens or 0)
                entity.input_cost_usd += float(row.input_cost_usd or 0.0)
                entity.output_cost_usd += float(row.output_cost_usd or 0.0)
                entity.total_cost_usd += float(row.total_cost_usd or 0.0)

            for row in model_rows:
                key = {"date": str(row.date), "model": str(row.model)}
                entity = await session.get(OverviewModelDailyStatsEntity, key)
                if entity is None:
                    entity = OverviewModelDailyStatsEntity(**key, requests=0, total_tokens=0, total_cost_usd=0.0)
                    session.add(entity)
                entity.requests += int(row.requests or 0)
                entity.total_tokens += int(row.total_tokens or 0)
                entity.total_cost_usd += float(row.total_cost_usd or 0.0)

            if daily_rows or model_rows:
                archive_stmt = update(RequestLogEntity).where(RequestLogEntity.stats_archived == 0)
                if not force:
                    archive_stmt = archive_stmt.where(date_expr < today_key)
                await session.execute(archive_stmt.values(stats_archived=1))

            last_persist_setting = await session.get(SettingEntity, SETTING_STATS_LAST_PERSIST_AT)
            if last_persist_setting is None:
                session.add(SettingEntity(key=SETTING_STATS_LAST_PERSIST_AT, value=now.isoformat()))
            else:
                last_persist_setting.value = now.isoformat()

            await session.commit()

    async def create_request_log(
        self,
        *,
        protocol: str,
        requested_group_name: str | None,
        resolved_group_name: str | None,
        upstream_model_name: str | None,
        channel_id: str | None,
        channel_name: str | None,
        gateway_key_id: str | None,
        status_code: int,
        success: bool,
        is_stream: bool,
        first_token_latency_ms: int,
        latency_ms: int,
        input_tokens: int,
        output_tokens: int,
        total_tokens: int,
        input_cost_usd: float,
        output_cost_usd: float,
        total_cost_usd: float,
        cache_read_input_tokens: int = 0,
        cache_write_input_tokens: int = 0,
        request_content: str | None = None,
        response_content: str | None = None,
        attempts: list[dict[str, Any]] | None = None,
        error_message: str | None = None,
    ) -> RequestLogItem:
        item: RequestLogItem
        async with self._session_factory() as session:
            entity = RequestLogEntity(
                protocol=protocol,
                requested_group_name=requested_group_name,
                resolved_group_name=resolved_group_name,
                upstream_model_name=upstream_model_name,
                channel_id=channel_id,
                channel_name=channel_name,
                gateway_key_id=gateway_key_id,
                status_code=status_code,
                success=1 if success else 0,
                is_stream=1 if is_stream else 0,
                first_token_latency_ms=max(first_token_latency_ms, 0),
                latency_ms=latency_ms,
                input_tokens=max(input_tokens, 0),
                cache_read_input_tokens=max(cache_read_input_tokens, 0),
                cache_write_input_tokens=max(cache_write_input_tokens, 0),
                output_tokens=max(output_tokens, 0),
                total_tokens=max(total_tokens, 0),
                input_cost_usd=max(input_cost_usd, 0.0),
                output_cost_usd=max(output_cost_usd, 0.0),
                total_cost_usd=max(total_cost_usd, 0.0),
                request_content=request_content,
                response_content=response_content,
                attempts_json=json.dumps(attempts or [], ensure_ascii=True),
                error_message=error_message,
                stats_archived=0,
            )
            session.add(entity)
            await session.commit()
            await session.refresh(entity)
            item = self._to_request_log(entity)
        await self.persist_request_log_stats()
        return item

    async def list_request_logs(self, limit: int = 100, days: int = 0, offset: int = 0) -> list[RequestLogItem]:
        async with self._session_factory() as session:
            stmt = (
                select(RequestLogEntity)
                .order_by(RequestLogEntity.created_at.desc(), RequestLogEntity.id.desc())
                .offset(offset)
                .limit(limit)
            )
            stmt = self._apply_request_log_window(stmt, days=days)
            result = await session.execute(stmt)
            return [self._to_request_log(item) for item in result.scalars().all()]

    async def list_request_log_page(self, limit: int = 100, days: int = 0, offset: int = 0) -> RequestLogPage:
        async with self._session_factory() as session:
            items_stmt = (
                select(RequestLogEntity)
                .order_by(RequestLogEntity.created_at.desc(), RequestLogEntity.id.desc())
                .offset(offset)
                .limit(limit)
            )
            items_stmt = self._apply_request_log_window(items_stmt, days=days)

            total_stmt = select(func.count()).select_from(RequestLogEntity)
            total_stmt = self._apply_request_log_window(total_stmt, days=days)

            items_result = await session.execute(items_stmt)
            total = await session.scalar(total_stmt)

            return RequestLogPage(
                items=[self._to_request_log(item) for item in items_result.scalars().all()],
                total=int(total or 0),
                limit=limit,
                offset=offset,
            )

    async def list_site_runtime_summaries(self) -> list[SiteRuntimeSummary]:
        async with self._session_factory() as session:
            site_rows = (
                await session.execute(select(SiteEntity).order_by(SiteEntity.name.asc()))
            ).scalars().all()
            if not site_rows:
                return []

            recent_request_logs = (
                select(RequestLogEntity.channel_id.label("channel_id"))
                .where(RequestLogEntity.channel_id.is_not(None))
                .order_by(RequestLogEntity.created_at.desc(), RequestLogEntity.id.desc())
                .limit(100)
                .subquery()
            )
            recent_count_rows = await session.execute(
                select(
                    SiteProtocolConfigEntity.site_id.label("site_id"),
                    func.count().label("recent_request_count"),
                )
                .select_from(recent_request_logs)
                .join(
                    SiteProtocolConfigEntity,
                    SiteProtocolConfigEntity.id == recent_request_logs.c.channel_id,
                )
                .group_by(SiteProtocolConfigEntity.site_id)
            )
            recent_request_count_by_site = {
                str(row.site_id): int(row.recent_request_count or 0)
                for row in recent_count_rows.all()
            }

            ranked_logs = (
                select(
                    SiteProtocolConfigEntity.site_id.label("site_id"),
                    RequestLogEntity.channel_id.label("channel_id"),
                    RequestLogEntity.channel_name.label("channel_name"),
                    RequestLogEntity.status_code.label("status_code"),
                    RequestLogEntity.success.label("success"),
                    RequestLogEntity.error_message.label("error_message"),
                    RequestLogEntity.created_at.label("created_at"),
                    func.row_number().over(
                        partition_by=SiteProtocolConfigEntity.site_id,
                        order_by=(RequestLogEntity.created_at.desc(), RequestLogEntity.id.desc()),
                    ).label("row_number"),
                )
                .join(
                    SiteProtocolConfigEntity,
                    SiteProtocolConfigEntity.id == RequestLogEntity.channel_id,
                )
                .subquery()
            )

            latest_rows = await session.execute(
                select(
                    ranked_logs.c.site_id,
                    ranked_logs.c.channel_id,
                    ranked_logs.c.channel_name,
                    ranked_logs.c.status_code,
                    ranked_logs.c.success,
                    ranked_logs.c.error_message,
                    ranked_logs.c.created_at,
                ).where(ranked_logs.c.row_number == 1)
            )
            latest_by_site = {
                str(row.site_id): row
                for row in latest_rows.all()
            }

            items: list[SiteRuntimeSummary] = []
            for site in site_rows:
                latest = latest_by_site.get(site.id)
                items.append(
                    SiteRuntimeSummary(
                        site_id=site.id,
                        site_name=site.name,
                        recent_request_count=recent_request_count_by_site.get(site.id, 0),
                        latest_request_at=(
                            latest.created_at.replace(tzinfo=UTC).isoformat()
                            if latest is not None and latest.created_at is not None
                            else None
                        ),
                        latest_success=(
                            bool(latest.success) if latest is not None and latest.success is not None else None
                        ),
                        latest_status_code=(
                            int(latest.status_code)
                            if latest is not None and latest.status_code is not None
                            else None
                        ),
                        latest_error_message=(
                            str(latest.error_message)
                            if latest is not None and latest.error_message is not None
                            else None
                        ),
                        latest_channel_id=(
                            str(latest.channel_id)
                            if latest is not None and latest.channel_id is not None
                            else None
                        ),
                        latest_channel_name=(
                            str(latest.channel_name)
                            if latest is not None and latest.channel_name is not None
                            else None
                        ),
                    )
                )
            return items

    async def get_request_log(self, log_id: int) -> RequestLogDetail:
        async with self._session_factory() as session:
            entity = await session.get(RequestLogEntity, log_id)
            if entity is None:
                raise KeyError(log_id)
            return self._to_request_log_detail(entity)

    async def clear_request_logs(self) -> None:
        await self.persist_request_log_stats(force=True)
        async with self._session_factory() as session:
            await session.execute(delete(RequestLogEntity))
            await session.commit()

    async def prune_request_logs(self) -> None:
        runtime = await self.get_runtime_settings()
        if not runtime["relay_log_keep_enabled"]:
            return
        await self.persist_request_log_stats(force=True)
        keep_days = max(int(runtime["relay_log_keep_period"]), 1)
        cutoff = datetime.utcnow() - timedelta(days=keep_days)
        async with self._session_factory() as session:
            await session.execute(delete(RequestLogEntity).where(RequestLogEntity.created_at < cutoff))
            await session.commit()

    async def get_overview_metrics(self) -> OverviewMetrics:
        async with self._session_factory() as session:
            imported_total = await session.get(ImportedStatsTotalEntity, 1)
            if imported_total is not None:
                extra_totals = await self._request_log_totals_excluding_imported_days(session)
                total_value = int(imported_total.request_success + imported_total.request_failed + extra_totals["request_count"])
                success_value = int(imported_total.request_success + extra_totals["successful_requests"])
                total_wait_time = int(imported_total.wait_time + extra_totals["wait_time_ms"])
                avg_latency = int(total_wait_time / total_value) if total_value else 0
            else:
                archived_totals = await self._archived_period_totals(session, days=0)
                live_totals = await self._request_log_period_totals(session, days=0)
                total_value = int(archived_totals["request_count"] + live_totals["request_count"])
                success_value = int(archived_totals["successful_requests"] + live_totals["successful_requests"])
                total_wait_time = int(archived_totals["wait_time_ms"] + live_totals["wait_time_ms"])
                avg_latency = int(total_wait_time / total_value) if total_value else 0

            enabled_groups = await session.scalar(select(func.count()).select_from(ModelGroupEntity))

        gateway_auth = await self.get_gateway_auth_config()

        return OverviewMetrics(
            total_requests=total_value,
            successful_requests=success_value,
            failed_requests=max(total_value - success_value, 0),
            avg_latency_ms=avg_latency,
            active_gateway_keys=len(gateway_auth["keys"]),
            enabled_groups=int(enabled_groups or 0),
            enabled_channels=0,
        )

    async def get_overview_summary(self, days: int = 7) -> OverviewSummary:
        async with self._session_factory() as session:
            if days != 0:
                comparison_offset = 1 if days == -1 else days
                recent = await self._merged_period_totals(session, days=days)
                previous = await self._merged_period_totals(session, days=days, offset_days=comparison_offset)
            else:
                recent = await self._merged_period_totals(session, days=0)
                previous = self._zero_totals()

        request_count = int(recent["request_count"])
        wait_time_ms = int(recent["wait_time_ms"])
        input_tokens = int(recent["input_tokens"])
        output_tokens = int(recent["output_tokens"])
        total_cost_usd = float(recent["total_cost_usd"])
        input_cost_usd = float(recent["input_cost_usd"])
        output_cost_usd = float(recent["output_cost_usd"])

        return OverviewSummary(
            request_count=OverviewSummaryMetric(value=request_count, delta=self._delta_percent(request_count, previous["request_count"])),
            wait_time_ms=OverviewSummaryMetric(value=wait_time_ms, delta=self._delta_percent(wait_time_ms, previous["wait_time_ms"])),
            total_tokens=OverviewSummaryMetric(value=input_tokens + output_tokens, delta=self._delta_percent(input_tokens + output_tokens, previous["input_tokens"] + previous["output_tokens"])),
            total_cost_usd=OverviewSummaryMetric(value=total_cost_usd, delta=self._delta_percent(total_cost_usd, previous["total_cost_usd"])),
            input_tokens=OverviewSummaryMetric(value=input_tokens, delta=self._delta_percent(input_tokens, previous["input_tokens"])),
            input_cost_usd=OverviewSummaryMetric(value=input_cost_usd, delta=self._delta_percent(input_cost_usd, previous["input_cost_usd"])),
            output_tokens=OverviewSummaryMetric(value=output_tokens, delta=self._delta_percent(output_tokens, previous["output_tokens"])),
            output_cost_usd=OverviewSummaryMetric(value=output_cost_usd, delta=self._delta_percent(output_cost_usd, previous["output_cost_usd"])),
        )

    async def list_overview_daily(self, days: int = 0) -> list[OverviewDailyPoint]:
        async with self._session_factory() as session:
            return await self._merged_daily_points(session, days=days)

    async def get_model_analytics(self, days: int = 7) -> OverviewModelAnalytics:
        async with self._session_factory() as session:
            if days == -1:
                archived_model_rows = []
                live_model_rows = await self._request_log_model_hourly_rows(session, days=days)
            else:
                window_start, window_end = self._resolve_imported_date_window(days)
                archived_model_rows = await self._overview_model_daily_rows(
                    session,
                    start_at=window_start,
                    end_at=window_end,
                )
                live_model_rows = await self._request_log_model_daily_rows(session, days=days)

        merged_rows: dict[tuple[str, str], dict[str, float | str]] = {}
        for date_value, model, requests, total_tokens, total_cost in [*archived_model_rows, *live_model_rows]:
            if not model:
                continue
            key = (str(date_value), str(model))
            current = merged_rows.get(key)
            if current is None:
                merged_rows[key] = {
                    "date": str(date_value),
                    "model": str(model),
                    "requests": float(requests or 0),
                    "total_tokens": float(total_tokens or 0),
                    "total_cost_usd": float(total_cost or 0.0),
                }
                continue
            current["requests"] = float(current["requests"]) + float(requests or 0)
            current["total_tokens"] = float(current["total_tokens"]) + float(total_tokens or 0)
            current["total_cost_usd"] = float(current["total_cost_usd"]) + float(total_cost or 0.0)

        trend_rows = sorted(merged_rows.values(), key=lambda item: (str(item["date"]), str(item["model"])))

        model_rows: dict[str, dict[str, float | str]] = {}
        for item in merged_rows.values():
            model_key = str(item["model"])
            current = model_rows.get(model_key)
            if current is None:
                model_rows[model_key] = {
                    "model": model_key,
                    "requests": float(item["requests"]),
                    "total_tokens": float(item["total_tokens"]),
                    "total_cost_usd": float(item["total_cost_usd"]),
                }
                continue
            current["requests"] = float(current["requests"]) + float(item["requests"])
            current["total_tokens"] = float(current["total_tokens"]) + float(item["total_tokens"])
            current["total_cost_usd"] = float(current["total_cost_usd"]) + float(item["total_cost_usd"])

        aggregated_models = list(model_rows.values())
        distribution_rows = sorted(aggregated_models, key=lambda item: (-float(item["total_cost_usd"]), -float(item["requests"])))
        ranking_rows = sorted(aggregated_models, key=lambda item: (-float(item["requests"]), -float(item["total_cost_usd"])))

        distribution = [
            OverviewModelMetricPoint(
                model=str(item["model"]),
                requests=int(item["requests"]),
                total_tokens=int(item["total_tokens"]),
                total_cost_usd=float(item["total_cost_usd"]),
            )
            for item in distribution_rows[:12]
        ]

        ranking = [
            OverviewModelMetricPoint(
                model=str(item["model"]),
                requests=int(item["requests"]),
                total_tokens=int(item["total_tokens"]),
                total_cost_usd=float(item["total_cost_usd"]),
            )
            for item in ranking_rows[:10]
        ]

        trend = [
            OverviewModelTrendPoint(date=str(item["date"]), model=str(item["model"]), value=float(item["total_cost_usd"]))
            for item in trend_rows
        ]

        available_models = sorted({item.model for item in distribution} | {item.model for item in ranking} | {item.model for item in trend})
        return OverviewModelAnalytics(
            distribution=distribution,
            request_ranking=ranking,
            trend=trend,
            available_models=available_models,
        )

    async def estimate_model_cost(
        self,
        model_name: str | None,
        input_tokens: int,
        output_tokens: int,
        cache_read_input_tokens: int = 0,
        cache_write_input_tokens: int = 0,
    ) -> tuple[float, float, float]:
        if not model_name:
            return 0.0, 0.0, 0.0

        async with self._session_factory() as session:
            entity = await session.get(ModelPriceEntity, normalize_model_key(model_name))
            if entity is None:
                return 0.0, 0.0, 0.0

        total_input_tokens = max(input_tokens, 0)
        cache_read_tokens = max(cache_read_input_tokens, 0)
        cache_write_tokens = max(cache_write_input_tokens, 0)
        regular_input_tokens = max(
            total_input_tokens - cache_read_tokens - cache_write_tokens, 0
        )

        input_cost = (regular_input_tokens / 1_000_000) * float(entity.input_price_per_million)
        input_cost += (cache_read_tokens / 1_000_000) * float(entity.cache_read_price_per_million)
        input_cost += (cache_write_tokens / 1_000_000) * float(entity.cache_write_price_per_million)
        output_cost = (max(output_tokens, 0) / 1_000_000) * float(entity.output_price_per_million)
        total_cost = input_cost + output_cost
        return round(input_cost, 8), round(output_cost, 8), round(total_cost, 8)

    async def _merged_daily_points(self, session: AsyncSession, *, days: int, offset_days: int = 0) -> list[OverviewDailyPoint]:
        imported_points = await self._imported_daily_points(session, days=days, offset_days=offset_days)
        imported_dates = {item.date for item in imported_points}
        archived_points = await self._archived_daily_points(session, days=days, offset_days=offset_days, exclude_dates=imported_dates)
        request_log_points = await self._request_log_daily_points(
            session,
            days=days,
            offset_days=offset_days,
            exclude_dates=imported_dates,
        )
        merged = {item.date: item.model_copy(deep=True) for item in imported_points}
        for item in archived_points:
            merged[item.date] = item.model_copy(deep=True)
        for item in request_log_points:
            current = merged.get(item.date)
            if current is None:
                merged[item.date] = item.model_copy(deep=True)
                continue
            merged[item.date] = OverviewDailyPoint(
                date=item.date,
                request_count=current.request_count + item.request_count,
                total_tokens=current.total_tokens + item.total_tokens,
                total_cost_usd=current.total_cost_usd + item.total_cost_usd,
                wait_time_ms=current.wait_time_ms + item.wait_time_ms,
                successful_requests=current.successful_requests + item.successful_requests,
                failed_requests=current.failed_requests + item.failed_requests,
            )
        return [merged[date] for date in sorted(merged)]

    async def _imported_daily_points(self, session: AsyncSession, *, days: int, offset_days: int = 0) -> list[OverviewDailyPoint]:
        stmt = select(ImportedStatsDailyEntity).order_by(ImportedStatsDailyEntity.date.asc())
        start_at, end_at = self._resolve_imported_date_window(days, offset_days=offset_days)
        if start_at is not None and end_at is not None:
            stmt = stmt.where(ImportedStatsDailyEntity.date >= start_at).where(ImportedStatsDailyEntity.date < end_at)
        rows = (await session.execute(stmt)).scalars().all()
        return [
            OverviewDailyPoint(
                date=item.date,
                request_count=int(item.request_success + item.request_failed),
                total_tokens=int(item.input_token + item.output_token),
                total_cost_usd=float(item.input_cost + item.output_cost),
                wait_time_ms=int(item.wait_time),
                successful_requests=int(item.request_success),
                failed_requests=int(item.request_failed),
            )
            for item in rows
        ]

    async def _archived_daily_points(
        self,
        session: AsyncSession,
        *,
        days: int,
        offset_days: int = 0,
        exclude_dates: set[str] | None = None,
    ) -> list[OverviewDailyPoint]:
        stmt = select(RequestLogDailyStatsEntity).order_by(RequestLogDailyStatsEntity.date.asc())
        start_at, end_at = self._resolve_imported_date_window(days, offset_days=offset_days)
        if start_at is not None and end_at is not None:
            stmt = stmt.where(RequestLogDailyStatsEntity.date >= start_at).where(RequestLogDailyStatsEntity.date < end_at)
        if exclude_dates:
            stmt = stmt.where(RequestLogDailyStatsEntity.date.not_in(sorted(exclude_dates)))
        try:
            rows = (await session.execute(stmt)).scalars().all()
        except OperationalError as exc:
            if self._is_missing_sqlite_table(exc, "request_log_daily_stats"):
                return []
            raise
        return [
            OverviewDailyPoint(
                date=item.date,
                request_count=int(item.request_count),
                total_tokens=int(item.total_tokens),
                total_cost_usd=float(item.total_cost_usd),
                wait_time_ms=int(item.wait_time_ms),
                successful_requests=int(item.successful_requests),
                failed_requests=int(item.failed_requests),
            )
            for item in rows
        ]

    async def _request_log_daily_points(
        self,
        session: AsyncSession,
        *,
        days: int,
        offset_days: int = 0,
        exclude_dates: set[str] | None = None,
    ) -> list[OverviewDailyPoint]:
        stmt = (
            select(
                func.strftime('%Y%m%d', RequestLogEntity.created_at),
                func.count(),
                func.sum(RequestLogEntity.total_tokens),
                func.sum(RequestLogEntity.total_cost_usd),
                func.sum(RequestLogEntity.latency_ms),
                func.sum(RequestLogEntity.success),
            )
            .select_from(RequestLogEntity)
            .group_by(func.strftime('%Y%m%d', RequestLogEntity.created_at))
            .order_by(func.strftime('%Y%m%d', RequestLogEntity.created_at).asc())
        )
        stmt = stmt.where(RequestLogEntity.stats_archived == 0)
        stmt = self._apply_request_log_window(stmt, days=days, offset_days=offset_days)
        if exclude_dates:
            stmt = stmt.where(func.strftime('%Y%m%d', RequestLogEntity.created_at).not_in(sorted(exclude_dates)))
        rows = (await session.execute(stmt)).all()
        points: list[OverviewDailyPoint] = []
        for date_value, request_count, total_tokens, total_cost_usd, wait_time_ms, successful_requests in rows:
            total_value = int(request_count or 0)
            success_value = int(successful_requests or 0)
            points.append(
                OverviewDailyPoint(
                    date=str(date_value),
                    request_count=total_value,
                    total_tokens=int(total_tokens or 0),
                    total_cost_usd=float(total_cost_usd or 0.0),
                    wait_time_ms=int(wait_time_ms or 0),
                    successful_requests=success_value,
                    failed_requests=max(total_value - success_value, 0),
                )
            )
        return points

    async def _request_log_totals_excluding_imported_days(self, session: AsyncSession) -> dict[str, float]:
        imported_dates = {
            row[0]
            for row in (await session.execute(select(ImportedStatsDailyEntity.date))).all()
        }
        archived_totals = await self._archived_period_totals(session, days=0, exclude_dates=imported_dates)
        live_totals = await self._request_log_period_totals(session, days=0, exclude_dates=imported_dates)
        return {
            "request_count": archived_totals["request_count"] + live_totals["request_count"],
            "wait_time_ms": archived_totals["wait_time_ms"] + live_totals["wait_time_ms"],
            "input_tokens": archived_totals["input_tokens"] + live_totals["input_tokens"],
            "output_tokens": archived_totals["output_tokens"] + live_totals["output_tokens"],
            "input_cost_usd": archived_totals["input_cost_usd"] + live_totals["input_cost_usd"],
            "output_cost_usd": archived_totals["output_cost_usd"] + live_totals["output_cost_usd"],
            "total_cost_usd": archived_totals["total_cost_usd"] + live_totals["total_cost_usd"],
            "successful_requests": archived_totals["successful_requests"] + live_totals["successful_requests"],
        }

    async def _archived_period_totals(
        self,
        session: AsyncSession,
        *,
        days: int,
        offset_days: int = 0,
        exclude_dates: set[str] | None = None,
    ) -> dict[str, float]:
        stmt = (
            select(
                func.sum(RequestLogDailyStatsEntity.request_count),
                func.sum(RequestLogDailyStatsEntity.wait_time_ms),
                func.sum(RequestLogDailyStatsEntity.input_tokens),
                func.sum(RequestLogDailyStatsEntity.output_tokens),
                func.sum(RequestLogDailyStatsEntity.input_cost_usd),
                func.sum(RequestLogDailyStatsEntity.output_cost_usd),
                func.sum(RequestLogDailyStatsEntity.total_cost_usd),
                func.sum(RequestLogDailyStatsEntity.successful_requests),
            )
            .select_from(RequestLogDailyStatsEntity)
        )
        start_at, end_at = self._resolve_imported_date_window(days, offset_days=offset_days)
        if start_at is not None:
            stmt = stmt.where(RequestLogDailyStatsEntity.date >= start_at)
        if end_at is not None:
            stmt = stmt.where(RequestLogDailyStatsEntity.date < end_at)
        if exclude_dates:
            stmt = stmt.where(RequestLogDailyStatsEntity.date.not_in(sorted(exclude_dates)))
        try:
            row = (await session.execute(stmt)).one()
        except OperationalError as exc:
            if self._is_missing_sqlite_table(exc, "request_log_daily_stats"):
                return {
                    "request_count": 0.0,
                    "wait_time_ms": 0.0,
                    "input_tokens": 0.0,
                    "output_tokens": 0.0,
                    "input_cost_usd": 0.0,
                    "output_cost_usd": 0.0,
                    "total_cost_usd": 0.0,
                    "successful_requests": 0.0,
                }
            raise
        return {
            "request_count": float(row[0] or 0),
            "wait_time_ms": float(row[1] or 0),
            "input_tokens": float(row[2] or 0),
            "output_tokens": float(row[3] or 0),
            "input_cost_usd": float(row[4] or 0),
            "output_cost_usd": float(row[5] or 0),
            "total_cost_usd": float(row[6] or 0),
            "successful_requests": float(row[7] or 0),
        }

    async def _overview_model_daily_rows(
        self,
        session: AsyncSession,
        *,
        start_at: str | None,
        end_at: str | None,
    ) -> list[tuple[str, str, int, int, float]]:
        stmt = select(
            OverviewModelDailyStatsEntity.date,
            OverviewModelDailyStatsEntity.model,
            OverviewModelDailyStatsEntity.requests,
            OverviewModelDailyStatsEntity.total_tokens,
            OverviewModelDailyStatsEntity.total_cost_usd,
        )
        if start_at is not None:
            stmt = stmt.where(OverviewModelDailyStatsEntity.date >= start_at)
        if end_at is not None:
            stmt = stmt.where(OverviewModelDailyStatsEntity.date < end_at)
        try:
            rows = (await session.execute(stmt.order_by(OverviewModelDailyStatsEntity.date.asc()))).all()
        except OperationalError as exc:
            if self._is_missing_sqlite_table(exc, "overview_model_daily_stats"):
                return []
            raise
        return [(str(date_value), str(model), int(requests or 0), int(total_tokens or 0), float(total_cost or 0.0)) for date_value, model, requests, total_tokens, total_cost in rows]

    async def _request_log_model_daily_rows(self, session: AsyncSession, *, days: int, offset_days: int = 0) -> list[tuple[str, str, int, int, float]]:
        model_expr = func.coalesce(RequestLogEntity.resolved_group_name, RequestLogEntity.requested_group_name)
        stmt = (
            select(
                func.strftime('%Y%m%d', RequestLogEntity.created_at),
                model_expr,
                func.sum(RequestLogEntity.success),
                func.sum(RequestLogEntity.total_tokens),
                func.sum(RequestLogEntity.total_cost_usd),
            )
            .where(RequestLogEntity.stats_archived == 0)
            .where(RequestLogEntity.success == 1)
            .where(model_expr.is_not(None))
            .group_by(func.strftime('%Y%m%d', RequestLogEntity.created_at), model_expr)
            .order_by(func.strftime('%Y%m%d', RequestLogEntity.created_at).asc())
        )
        stmt = self._apply_request_log_window(stmt, days=days, offset_days=offset_days)
        rows = (await session.execute(stmt)).all()
        return [(str(date_value), str(model), int(requests or 0), int(total_tokens or 0), float(total_cost or 0.0)) for date_value, model, requests, total_tokens, total_cost in rows if model]

    async def _request_log_model_hourly_rows(self, session: AsyncSession, *, days: int, offset_days: int = 0) -> list[tuple[str, str, int, int, float]]:
        model_expr = func.coalesce(RequestLogEntity.resolved_group_name, RequestLogEntity.requested_group_name)
        hourly_bucket = func.strftime('%Y%m%d%H', RequestLogEntity.created_at)
        stmt = (
            select(
                hourly_bucket,
                model_expr,
                func.sum(RequestLogEntity.success),
                func.sum(RequestLogEntity.total_tokens),
                func.sum(RequestLogEntity.total_cost_usd),
            )
            .where(RequestLogEntity.stats_archived == 0)
            .where(RequestLogEntity.success == 1)
            .where(model_expr.is_not(None))
            .group_by(hourly_bucket, model_expr)
            .order_by(hourly_bucket.asc())
        )
        stmt = self._apply_request_log_window(stmt, days=days, offset_days=offset_days)
        rows = (await session.execute(stmt)).all()
        return [
            (str(date_value), str(model), int(requests or 0), int(total_tokens or 0), float(total_cost or 0.0))
            for date_value, model, requests, total_tokens, total_cost in rows
            if model
        ]

    async def _merged_period_totals(self, session: AsyncSession, *, days: int, offset_days: int = 0) -> dict[str, float]:
        imported_totals = await self._imported_period_totals(session, days=days, offset_days=offset_days)
        archived_totals = await self._archived_period_totals(
            session,
            days=days,
            offset_days=offset_days,
            exclude_dates=imported_totals["covered_dates"],
        )
        request_log_totals = await self._request_log_period_totals(
            session,
            days=days,
            offset_days=offset_days,
            exclude_dates=imported_totals["covered_dates"],
        )
        return {
            "request_count": imported_totals["request_count"] + archived_totals["request_count"] + request_log_totals["request_count"],
            "wait_time_ms": imported_totals["wait_time_ms"] + archived_totals["wait_time_ms"] + request_log_totals["wait_time_ms"],
            "input_tokens": imported_totals["input_tokens"] + archived_totals["input_tokens"] + request_log_totals["input_tokens"],
            "output_tokens": imported_totals["output_tokens"] + archived_totals["output_tokens"] + request_log_totals["output_tokens"],
            "input_cost_usd": imported_totals["input_cost_usd"] + archived_totals["input_cost_usd"] + request_log_totals["input_cost_usd"],
            "output_cost_usd": imported_totals["output_cost_usd"] + archived_totals["output_cost_usd"] + request_log_totals["output_cost_usd"],
            "total_cost_usd": imported_totals["total_cost_usd"] + archived_totals["total_cost_usd"] + request_log_totals["total_cost_usd"],
        }

    async def _imported_period_totals(self, session: AsyncSession, *, days: int, offset_days: int = 0) -> dict[str, float | set[str]]:
        if days == 0:
            imported_total = await session.get(ImportedStatsTotalEntity, 1)
            covered_dates = {
                row[0]
                for row in (await session.execute(select(ImportedStatsDailyEntity.date))).all()
            }
            if imported_total is None:
                return {
                    "request_count": 0.0,
                    "wait_time_ms": 0.0,
                    "input_tokens": 0.0,
                    "output_tokens": 0.0,
                    "input_cost_usd": 0.0,
                    "output_cost_usd": 0.0,
                    "total_cost_usd": 0.0,
                    "covered_dates": covered_dates,
                }
            return {
                "request_count": float(imported_total.request_success + imported_total.request_failed),
                "wait_time_ms": float(imported_total.wait_time),
                "input_tokens": float(imported_total.input_token),
                "output_tokens": float(imported_total.output_token),
                "input_cost_usd": float(imported_total.input_cost),
                "output_cost_usd": float(imported_total.output_cost),
                "total_cost_usd": float(imported_total.input_cost + imported_total.output_cost),
                "covered_dates": covered_dates,
            }

        start_at, end_at = self._resolve_imported_date_window(days, offset_days=offset_days)
        rows = (
            await session.execute(
                select(ImportedStatsDailyEntity)
                .where(ImportedStatsDailyEntity.date >= start_at)
                .where(ImportedStatsDailyEntity.date < end_at)
            )
        ).scalars().all()
        covered_dates = {item.date for item in rows}
        return {
            "request_count": float(sum(item.request_success + item.request_failed for item in rows)),
            "wait_time_ms": float(sum(item.wait_time for item in rows)),
            "input_tokens": float(sum(item.input_token for item in rows)),
            "output_tokens": float(sum(item.output_token for item in rows)),
            "input_cost_usd": float(sum(item.input_cost for item in rows)),
            "output_cost_usd": float(sum(item.output_cost for item in rows)),
            "total_cost_usd": float(sum(item.input_cost + item.output_cost for item in rows)),
            "covered_dates": covered_dates,
        }

    async def _request_log_period_totals(
        self,
        session: AsyncSession,
        *,
        days: int,
        offset_days: int = 0,
        exclude_dates: set[str] | None = None,
    ) -> dict[str, float]:
        stmt = (
            select(
                func.count(),
                func.sum(RequestLogEntity.latency_ms),
                func.sum(RequestLogEntity.input_tokens),
                func.sum(RequestLogEntity.output_tokens),
                func.sum(RequestLogEntity.input_cost_usd),
                func.sum(RequestLogEntity.output_cost_usd),
                func.sum(RequestLogEntity.total_cost_usd),
                func.sum(RequestLogEntity.success),
            )
            .select_from(RequestLogEntity)
        )
        stmt = stmt.where(RequestLogEntity.stats_archived == 0)
        stmt = self._apply_request_log_window(stmt, days=days, offset_days=offset_days)
        if exclude_dates:
            stmt = stmt.where(func.strftime('%Y%m%d', RequestLogEntity.created_at).not_in(sorted(exclude_dates)))
        row = (await session.execute(stmt)).one()
        return {
            "request_count": float(row[0] or 0),
            "wait_time_ms": float(row[1] or 0),
            "input_tokens": float(row[2] or 0),
            "output_tokens": float(row[3] or 0),
            "input_cost_usd": float(row[4] or 0),
            "output_cost_usd": float(row[5] or 0),
            "total_cost_usd": float(row[6] or 0),
            "successful_requests": float(row[7] or 0),
        }

    @staticmethod
    def _zero_totals() -> dict[str, float]:
        return {
            "request_count": 0.0,
            "wait_time_ms": 0.0,
            "input_tokens": 0.0,
            "output_tokens": 0.0,
            "input_cost_usd": 0.0,
            "output_cost_usd": 0.0,
            "total_cost_usd": 0.0,
        }

    @staticmethod
    def _resolve_request_log_window(days: int, *, offset_days: int = 0) -> tuple[datetime | None, datetime | None]:
        if days == 0:
            return None, None

        now = datetime.now(UTC).replace(tzinfo=None)
        if days == -1:
            start_at = now.replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=offset_days)
            return start_at, start_at + timedelta(days=1)

        end_at = now - timedelta(days=offset_days)
        return end_at - timedelta(days=days), end_at

    @classmethod
    def _resolve_imported_date_window(cls, days: int, *, offset_days: int = 0) -> tuple[str | None, str | None]:
        start_at, end_at = cls._resolve_request_log_window(days, offset_days=offset_days)
        if start_at is None or end_at is None:
            return None, None
        return start_at.strftime("%Y%m%d"), end_at.strftime("%Y%m%d")

    @classmethod
    def _apply_request_log_window(cls, stmt: Any, *, days: int, offset_days: int = 0) -> Any:
        start_at, end_at = cls._resolve_request_log_window(days, offset_days=offset_days)
        if start_at is not None:
            stmt = stmt.where(RequestLogEntity.created_at >= start_at)
        if end_at is not None:
            stmt = stmt.where(RequestLogEntity.created_at < end_at)
        return stmt

    @staticmethod
    def _delta_percent(current: float, previous: float) -> float:
        if previous <= 0:
            return 0.0
        return round(((current - previous) / previous) * 100, 2)

    @staticmethod
    def _normalize_total_payload(total: dict[str, int | float] | list[dict[str, int | float]] | None) -> dict[str, int | float] | None:
        if isinstance(total, list):
            return total[0] if total else None
        return total

    @staticmethod
    def _split_gateway_keys(raw_value: str) -> list[str]:
        keys: list[str] = []
        seen: set[str] = set()
        for item in raw_value.replace("\r", "\n").split("\n"):
            normalized = item.strip()
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            keys.append(normalized)
        return keys

    @staticmethod
    def _split_comma_lines(raw_value: str) -> list[str]:
        items: list[str] = []
        seen: set[str] = set()
        for chunk in raw_value.replace("\r", "\n").replace("，", ",").splitlines():
            for item in chunk.split(","):
                normalized = item.strip()
                if not normalized or normalized in seen:
                    continue
                seen.add(normalized)
                items.append(normalized)
        return items

    @staticmethod
    def _parse_bool(value: str | None, *, default: bool) -> bool:
        if value is None:
            return default
        return value.strip().lower() not in {"0", "false", "no", "off"}

    @staticmethod
    def _parse_int(value: str | None, *, default: int) -> int:
        if value is None:
            return default
        try:
            return int(value.strip())
        except ValueError:
            return default

    @staticmethod
    def _parse_float(value: str | None, *, default: float) -> float:
        if value is None:
            return default
        try:
            return float(value.strip())
        except ValueError:
            return default

    @staticmethod
    def _to_group(
        entity: ModelGroupEntity,
        items: list[ModelGroupItem],
        price: ModelPriceEntity | None = None,
        route_group_name: str = "",
    ) -> ModelGroup:
        return ModelGroup(
            id=entity.id,
            name=entity.name,
            protocol=entity.protocol,
            strategy=entity.strategy,
            route_group_id=entity.route_group_id,
            route_group_name=route_group_name,
            input_price_per_million=float(price.input_price_per_million) if price is not None else 0.0,
            output_price_per_million=float(price.output_price_per_million) if price is not None else 0.0,
            cache_read_price_per_million=float(price.cache_read_price_per_million) if price is not None else 0.0,
            cache_write_price_per_million=float(price.cache_write_price_per_million) if price is not None else 0.0,
            items=items,
        )

    @staticmethod
    def _to_request_log(entity: RequestLogEntity) -> RequestLogItem:
        attempts = DomainStore._parse_attempts_json(entity.attempts_json)
        return RequestLogItem(
            id=entity.id,
            protocol=entity.protocol,
            requested_group_name=entity.requested_group_name,
            resolved_group_name=entity.resolved_group_name,
            upstream_model_name=entity.upstream_model_name,
            channel_id=entity.channel_id,
            channel_name=entity.channel_name,
            gateway_key_id=entity.gateway_key_id,
            status_code=entity.status_code,
            success=bool(entity.success),
            is_stream=bool(entity.is_stream),
            first_token_latency_ms=entity.first_token_latency_ms,
            latency_ms=entity.latency_ms,
            input_tokens=entity.input_tokens,
            cache_read_input_tokens=entity.cache_read_input_tokens,
            cache_write_input_tokens=entity.cache_write_input_tokens,
            output_tokens=entity.output_tokens,
            total_tokens=entity.total_tokens,
            input_cost_usd=entity.input_cost_usd,
            output_cost_usd=entity.output_cost_usd,
            total_cost_usd=entity.total_cost_usd,
            attempt_count=len(attempts),
            error_message=entity.error_message,
            created_at=entity.created_at.replace(tzinfo=UTC).isoformat(),
        )

    @staticmethod
    def _to_request_log_detail(entity: RequestLogEntity) -> RequestLogDetail:
        return RequestLogDetail(
            **DomainStore._to_request_log(entity).model_dump(),
            request_content=entity.request_content,
            response_content=entity.response_content,
            attempts=[
                RequestLogAttempt(**item)
                for item in DomainStore._parse_attempts_json(entity.attempts_json)
            ],
        )

    @staticmethod
    def _parse_attempts_json(raw_value: str | None) -> list[dict[str, Any]]:
        if not raw_value:
            return []
        try:
            payload = json.loads(raw_value)
        except json.JSONDecodeError:
            return []
        if not isinstance(payload, list):
            return []
        return [item for item in payload if isinstance(item, dict)]
