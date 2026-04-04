from __future__ import annotations

import json
import re
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from ..models import ModelGroup, ModelGroupCandidateItem, ModelGroupCandidatesRequest, ModelGroupCandidatesResponse, ModelGroupCreate, ModelGroupItem, ModelGroupItemInput, ModelGroupStats, ModelGroupUpdate, OverviewDailyPoint, OverviewMetrics, OverviewModelAnalytics, OverviewModelMetricPoint, OverviewModelTrendPoint, OverviewSummary, OverviewSummaryMetric, RequestLogItem, SettingItem
from .entities import ImportedStatsDailyEntity, ImportedStatsTotalEntity, ModelGroupEntity, ModelGroupItemEntity, ModelPriceEntity, RequestLogEntity, SettingEntity, SiteCredentialEntity, SiteDiscoveredModelEntity, SiteEntity, SiteProtocolConfigEntity, SiteProtocolCredentialBindingEntity


SETTING_GATEWAY_API_KEYS = "gateway_api_keys"
SETTING_GATEWAY_REQUIRE_API_KEY = "gateway_require_api_key"
SETTING_GATEWAY_API_KEY_HINT = "gateway_api_key_hint"


class DomainStore:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

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
            await session.execute(delete(ModelPriceEntity))

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
                    )
                )

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
            items = await self._load_group_items(session, [group_id])
            return self._to_group(entity, items.get(group_id, []))

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
            items = await self._load_group_items(session, [entity.id])
            return self._to_group(entity, items.get(entity.id, []))

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

        site_name_by_channel: dict[str, str] = {}
        if channel_ids:
            async with self._session_factory() as session:
                rows = (
                    await session.execute(
                        select(SiteProtocolConfigEntity.id, SiteEntity.name)
                        .join(SiteEntity, SiteEntity.id == SiteProtocolConfigEntity.site_id)
                        .where(SiteProtocolConfigEntity.id.in_(channel_ids))
                    )
                ).all()
            site_name_by_channel = {channel_id: site_name for channel_id, site_name in rows}

        for channel in channels:
            channel_items = list(dict.fromkeys(models_by_channel.get(channel.id, [])))
            for credential_id, model_name in channel_items:
                candidate_key = (channel.id, credential_id, model_name)
                if candidate_key in seen:
                    continue
                seen.add(candidate_key)
                candidates.append(
                    ModelGroupCandidateItem(
                        channel_id=channel.id,
                        channel_name=site_name_by_channel.get(channel.id, channel.protocol),
                        credential_id=credential_id,
                        credential_name=credential_names.get(credential_id, ""),
                        base_url=channel.base_url,
                        model_name=model_name,
                    )
                )

        matched_items = [
            item
            for item in candidates
            if (item.channel_id, item.model_name) not in excluded
            and self._candidate_matches_group(item.model_name, payload.name, payload.match_regex)
        ]
        return ModelGroupCandidatesResponse(candidates=candidates, matched_items=matched_items)

    async def list_group_stats(self) -> list[ModelGroupStats]:
        async with self._session_factory() as session:
            groups = (
                await session.execute(select(ModelGroupEntity).order_by(ModelGroupEntity.name))
            ).scalars().all()
            grouped_rows = (
                await session.execute(
                    select(
                        RequestLogEntity.matched_group_name,
                        func.count(RequestLogEntity.id),
                        func.sum(RequestLogEntity.success),
                        func.sum(RequestLogEntity.total_tokens),
                        func.sum(RequestLogEntity.total_cost_usd),
                        func.avg(RequestLogEntity.latency_ms),
                    )
                    .where(RequestLogEntity.matched_group_name.is_not(None))
                    .group_by(RequestLogEntity.matched_group_name)
                )
            ).all()

            last_model_rows = (
                await session.execute(
                    select(
                        RequestLogEntity.matched_group_name,
                        RequestLogEntity.resolved_model,
                    )
                    .where(RequestLogEntity.matched_group_name.is_not(None))
                    .where(RequestLogEntity.resolved_model.is_not(None))
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
        for group_name, resolved_model in last_model_rows:
            if not group_name or not resolved_model:
                continue
            key = str(group_name)
            if key not in last_models:
                last_models[key] = str(resolved_model)

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
            channels_by_id, channel_site_names = await self._validate_group_payload(session, payload.protocol.value, payload.name, payload.items)
            entity = ModelGroupEntity(
                id=str(uuid.uuid4()),
                name=payload.name.strip(),
                protocol=payload.protocol.value,
                strategy=payload.strategy.value,
                match_regex=payload.match_regex,
            )
            session.add(entity)
            await session.flush()
            await self._replace_group_items(session, entity.id, payload.items, channels_by_id, channel_site_names)
            await session.commit()
            await session.refresh(entity)
            items = await self._load_group_items(session, [entity.id])
            return self._to_group(entity, items.get(entity.id, []))

    async def update_group(self, group_id: str, payload: ModelGroupUpdate) -> ModelGroup:
        async with self._session_factory() as session:
            entity = await session.get(ModelGroupEntity, group_id)
            if entity is None:
                raise KeyError(group_id)

            next_protocol = payload.protocol.value if payload.protocol is not None else entity.protocol
            next_name = payload.name if payload.name is not None else entity.name
            current_items = await self._load_group_items(session, [group_id])
            next_items = payload.items if payload.items is not None else [
                ModelGroupItemInput(channel_id=item.channel_id, credential_id=item.credential_id, model_name=item.model_name, enabled=item.enabled)
                for item in current_items.get(group_id, [])
            ]
            channels_by_id, channel_site_names = await self._validate_group_payload(session, next_protocol, next_name, next_items, exclude_group_id=group_id)

            changes = payload.model_dump(exclude_unset=True)
            for key, value in changes.items():
                if key == "protocol" and value is not None:
                    entity.protocol = value.value
                elif key == "strategy" and value is not None:
                    entity.strategy = value.value
                elif key == "items" and value is not None:
                    continue
                else:
                    setattr(entity, key, value)

            if payload.items is not None or payload.protocol is not None:
                await session.execute(delete(ModelGroupItemEntity).where(ModelGroupItemEntity.group_id == group_id))
                await self._replace_group_items(session, group_id, next_items, channels_by_id, channel_site_names)

            await session.commit()
            await session.refresh(entity)
            items = await self._load_group_items(session, [entity.id])
            return self._to_group(entity, items.get(entity.id, []))

    async def delete_group(self, group_id: str) -> None:
        async with self._session_factory() as session:
            entity = await session.get(ModelGroupEntity, group_id)
            if entity is None:
                raise KeyError(group_id)
            await session.execute(delete(ModelGroupItemEntity).where(ModelGroupItemEntity.group_id == group_id))
            await session.delete(entity)
            await session.commit()

    async def _validate_group_payload(
        self,
        session: AsyncSession,
        protocol: str,
        name: str,
        items: list[ModelGroupItemInput],
        exclude_group_id: str | None = None,
    ) -> tuple[dict[str, SiteProtocolConfigEntity], dict[str, str]]:
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

        if not items:
            return {}, {}

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

        invalid_channel_ids = [channel.id for channel in channel_rows if channel.protocol != protocol]
        if invalid_channel_ids:
            raise ValueError(f'Channels must match protocol={protocol}: {", ".join(invalid_channel_ids)}')

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

        return channels_by_id, channel_site_names

    async def _hydrate_groups(self, session: AsyncSession, entities: list[ModelGroupEntity]) -> list[ModelGroup]:
        if not entities:
            return []
        items_by_group = await self._load_group_items(session, [item.id for item in entities])
        return [self._to_group(item, items_by_group.get(item.id, [])) for item in entities]

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

    @staticmethod
    def _normalize_match_value(value: str) -> str:
        return ''.join(ch for ch in value.lower() if ch.isalnum())

    def _candidate_matches_group(self, model_name: str, group_name: str, match_regex: str) -> bool:
        normalized_model = self._normalize_match_value(model_name)
        if match_regex.strip():
            return re.search(match_regex, model_name) is not None
        normalized_group = self._normalize_match_value(group_name)
        if not normalized_group:
            return False
        return normalized_group in normalized_model

    async def get_gateway_auth_config(self) -> dict[str, Any]:
        items = await self.list_settings()
        mapping = {item.key: item.value for item in items}
        keys = self._split_gateway_keys(mapping.get(SETTING_GATEWAY_API_KEYS, ""))
        require_api_key = mapping.get(SETTING_GATEWAY_REQUIRE_API_KEY, "true").strip().lower() not in {"0", "false", "no", "off"}
        return {
            "keys": keys,
            "require_api_key": require_api_key,
            "hint": mapping.get(SETTING_GATEWAY_API_KEY_HINT, ""),
        }

    async def list_settings(self) -> list[SettingItem]:
        async with self._session_factory() as session:
            result = await session.execute(select(SettingEntity).order_by(SettingEntity.key))
            return [SettingItem(key=item.key, value=item.value) for item in result.scalars().all()]

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
            return [SettingItem(key=item.key, value=item.value) for item in result.scalars().all()]

    async def create_request_log(
        self,
        *,
        protocol: str,
        requested_model: str | None,
        matched_group_name: str | None,
        channel_id: str | None,
        gateway_key_id: str | None,
        status_code: int,
        success: bool,
        latency_ms: int,
        resolved_model: str | None,
        input_tokens: int,
        output_tokens: int,
        total_tokens: int,
        input_cost_usd: float,
        output_cost_usd: float,
        total_cost_usd: float,
        error_message: str | None,
    ) -> RequestLogItem:
        async with self._session_factory() as session:
            entity = RequestLogEntity(
                protocol=protocol,
                requested_model=requested_model,
                matched_group_name=matched_group_name,
                channel_id=channel_id,
                gateway_key_id=gateway_key_id,
                status_code=status_code,
                success=1 if success else 0,
                latency_ms=latency_ms,
                resolved_model=resolved_model,
                input_tokens=max(input_tokens, 0),
                output_tokens=max(output_tokens, 0),
                total_tokens=max(total_tokens, 0),
                input_cost_usd=max(input_cost_usd, 0.0),
                output_cost_usd=max(output_cost_usd, 0.0),
                total_cost_usd=max(total_cost_usd, 0.0),
                error_message=error_message,
            )
            session.add(entity)
            await session.commit()
            await session.refresh(entity)
            return self._to_request_log(entity)

    async def list_request_logs(self, limit: int = 100) -> list[RequestLogItem]:
        async with self._session_factory() as session:
            result = await session.execute(
                select(RequestLogEntity)
                .order_by(RequestLogEntity.created_at.desc(), RequestLogEntity.id.desc())
                .limit(limit)
            )
            return [self._to_request_log(item) for item in result.scalars().all()]

    async def get_overview_metrics(self) -> OverviewMetrics:
        async with self._session_factory() as session:
            imported_total = await session.get(ImportedStatsTotalEntity, 1)
            if imported_total is not None:
                total_value = int(imported_total.request_success + imported_total.request_failed)
                success_value = int(imported_total.request_success)
                avg_latency = int(imported_total.wait_time / total_value) if total_value else 0
            else:
                total_requests = await session.scalar(select(func.count()).select_from(RequestLogEntity))
                successful_requests = await session.scalar(
                    select(func.count()).select_from(RequestLogEntity).where(RequestLogEntity.success == 1)
                )
                avg_latency_value = await session.scalar(select(func.avg(RequestLogEntity.latency_ms)).select_from(RequestLogEntity))
                total_value = int(total_requests or 0)
                success_value = int(successful_requests or 0)
                avg_latency = int(avg_latency_value or 0)

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

    async def get_overview_summary(self) -> OverviewSummary:
        async with self._session_factory() as session:
            imported_total = await session.get(ImportedStatsTotalEntity, 1)
            recent = await self._recent_log_totals(session, days=7)
            previous = await self._recent_log_totals(session, days=14, offset_days=7)

        if imported_total is not None:
            request_count = int(imported_total.request_success + imported_total.request_failed)
            wait_time_ms = int(imported_total.wait_time)
            input_tokens = int(imported_total.input_token)
            output_tokens = int(imported_total.output_token)
            total_cost_usd = float(imported_total.input_cost + imported_total.output_cost)
            input_cost_usd = float(imported_total.input_cost)
            output_cost_usd = float(imported_total.output_cost)
        else:
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

    async def list_overview_daily(self) -> list[OverviewDailyPoint]:
        async with self._session_factory() as session:
            imported_rows = (
                await session.execute(select(ImportedStatsDailyEntity).order_by(ImportedStatsDailyEntity.date.asc()))
            ).scalars().all()
            if imported_rows:
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
                    for item in imported_rows
                ]

            rows = (
                await session.execute(
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
            ).all()
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

    async def get_model_analytics(self, days: int = 30) -> OverviewModelAnalytics:
        since = datetime.utcnow() - timedelta(days=days)
        model_expr = func.coalesce(RequestLogEntity.resolved_model, RequestLogEntity.requested_model, RequestLogEntity.matched_group_name)
        async with self._session_factory() as session:
            distribution_rows = (
                await session.execute(
                    select(
                        model_expr,
                        func.count(),
                        func.sum(RequestLogEntity.total_tokens),
                        func.sum(RequestLogEntity.total_cost_usd),
                    )
                    .where(RequestLogEntity.success == 1)
                    .where(model_expr.is_not(None))
                    .where(RequestLogEntity.created_at >= since)
                    .group_by(model_expr)
                    .order_by(func.sum(RequestLogEntity.total_cost_usd).desc(), func.count().desc())
                    .limit(12)
                )
            ).all()

            ranking_rows = (
                await session.execute(
                    select(
                        model_expr,
                        func.count(),
                        func.sum(RequestLogEntity.total_tokens),
                        func.sum(RequestLogEntity.total_cost_usd),
                    )
                    .where(RequestLogEntity.success == 1)
                    .where(model_expr.is_not(None))
                    .where(RequestLogEntity.created_at >= since)
                    .group_by(model_expr)
                    .order_by(func.count().desc(), func.sum(RequestLogEntity.total_cost_usd).desc())
                    .limit(10)
                )
            ).all()

            trend_rows = (
                await session.execute(
                    select(
                        func.strftime('%Y%m%d', RequestLogEntity.created_at),
                        model_expr,
                        func.sum(RequestLogEntity.total_cost_usd),
                    )
                    .where(RequestLogEntity.success == 1)
                    .where(model_expr.is_not(None))
                    .where(RequestLogEntity.created_at >= since)
                    .group_by(func.strftime('%Y%m%d', RequestLogEntity.created_at), model_expr)
                    .order_by(func.strftime('%Y%m%d', RequestLogEntity.created_at).asc())
                )
            ).all()

        distribution = [
            OverviewModelMetricPoint(
                model=str(model),
                requests=int(requests or 0),
                total_tokens=int(total_tokens or 0),
                total_cost_usd=float(total_cost or 0.0),
            )
            for model, requests, total_tokens, total_cost in distribution_rows
            if model
        ]

        ranking = [
            OverviewModelMetricPoint(
                model=str(model),
                requests=int(requests or 0),
                total_tokens=int(total_tokens or 0),
                total_cost_usd=float(total_cost or 0.0),
            )
            for model, requests, total_tokens, total_cost in ranking_rows
            if model
        ]

        trend = [
            OverviewModelTrendPoint(date=str(date_value), model=str(model), value=float(value or 0.0))
            for date_value, model, value in trend_rows
            if model
        ]

        available_models = sorted({item.model for item in distribution} | {item.model for item in ranking} | {item.model for item in trend})
        return OverviewModelAnalytics(
            distribution=distribution,
            request_ranking=ranking,
            trend=trend,
            available_models=available_models,
        )

    async def estimate_model_cost(self, model_name: str | None, input_tokens: int, output_tokens: int) -> tuple[float, float, float]:
        if not model_name:
            return 0.0, 0.0, 0.0

        async with self._session_factory() as session:
            entity = await session.get(ModelPriceEntity, model_name.strip().lower())
            if entity is None:
                return 0.0, 0.0, 0.0

        input_cost = (max(input_tokens, 0) / 1_000_000) * float(entity.input_price_per_million)
        output_cost = (max(output_tokens, 0) / 1_000_000) * float(entity.output_price_per_million)
        total_cost = input_cost + output_cost
        return round(input_cost, 8), round(output_cost, 8), round(total_cost, 8)

    async def _recent_log_totals(self, session: AsyncSession, *, days: int, offset_days: int = 0) -> dict[str, float]:
        end_at = datetime.utcnow() - timedelta(days=offset_days)
        start_at = end_at - timedelta(days=days)
        row = (
            await session.execute(
                select(
                    func.count(),
                    func.sum(RequestLogEntity.latency_ms),
                    func.sum(RequestLogEntity.input_tokens),
                    func.sum(RequestLogEntity.output_tokens),
                    func.sum(RequestLogEntity.input_cost_usd),
                    func.sum(RequestLogEntity.output_cost_usd),
                    func.sum(RequestLogEntity.total_cost_usd),
                )
                .select_from(RequestLogEntity)
                .where(RequestLogEntity.created_at >= start_at)
                .where(RequestLogEntity.created_at < end_at)
            )
        ).one()
        return {
            "request_count": float(row[0] or 0),
            "wait_time_ms": float(row[1] or 0),
            "input_tokens": float(row[2] or 0),
            "output_tokens": float(row[3] or 0),
            "input_cost_usd": float(row[4] or 0),
            "output_cost_usd": float(row[5] or 0),
            "total_cost_usd": float(row[6] or 0),
        }

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
    def _to_group(entity: ModelGroupEntity, items: list[ModelGroupItem]) -> ModelGroup:
        return ModelGroup(
            id=entity.id,
            name=entity.name,
            protocol=entity.protocol,
            strategy=entity.strategy,
            match_regex=entity.match_regex,
            items=items,
        )

    @staticmethod
    def _to_request_log(entity: RequestLogEntity) -> RequestLogItem:
        return RequestLogItem(
            id=entity.id,
            protocol=entity.protocol,
            requested_model=entity.requested_model,
            matched_group_name=entity.matched_group_name,
            channel_id=entity.channel_id,
            gateway_key_id=entity.gateway_key_id,
            status_code=entity.status_code,
            success=bool(entity.success),
            latency_ms=entity.latency_ms,
            resolved_model=entity.resolved_model,
            input_tokens=entity.input_tokens,
            output_tokens=entity.output_tokens,
            total_tokens=entity.total_tokens,
            input_cost_usd=entity.input_cost_usd,
            output_cost_usd=entity.output_cost_usd,
            total_cost_usd=entity.total_cost_usd,
            error_message=entity.error_message,
            created_at=entity.created_at.replace(tzinfo=UTC).isoformat(),
        )

