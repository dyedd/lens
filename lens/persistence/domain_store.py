from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from ..models import ModelGroup, ModelGroupCreate, ModelGroupUpdate, OverviewDailyPoint, OverviewMetrics, OverviewModelAnalytics, OverviewModelMetricPoint, OverviewModelTrendPoint, OverviewSummary, OverviewSummaryMetric, RequestLogItem, SettingItem
from .entities import ImportedStatsDailyEntity, ImportedStatsTotalEntity, ModelGroupEntity, ModelPriceEntity, RequestLogEntity, SettingEntity


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
            result = await session.execute(select(ModelGroupEntity).order_by(ModelGroupEntity.name))
            return [self._to_group(item) for item in result.scalars().all()]

    async def find_group_by_name(self, protocol: str, name: str | None) -> ModelGroup | None:
        if not name:
            return None

        async with self._session_factory() as session:
            result = await session.execute(
                select(ModelGroupEntity)
                .where(ModelGroupEntity.protocol == protocol)
                .where(ModelGroupEntity.name == name)
                .where(ModelGroupEntity.enabled == 1)
                .limit(1)
            )
            entity = result.scalar_one_or_none()
            if entity is None:
                return None
            return self._to_group(entity)

    async def create_group(self, payload: ModelGroupCreate) -> ModelGroup:
        async with self._session_factory() as session:
            next_id = await self._next_id(session, ModelGroupEntity, payload.protocol.value)
            entity = ModelGroupEntity(
                id=next_id,
                name=payload.name,
                protocol=payload.protocol.value,
                strategy=payload.strategy.value,
                provider_ids_json=json.dumps(payload.provider_ids, ensure_ascii=True),
                enabled=1 if payload.enabled else 0,
            )
            session.add(entity)
            await session.commit()
            return self._to_group(entity)

    async def update_group(self, group_id: str, payload: ModelGroupUpdate) -> ModelGroup:
        async with self._session_factory() as session:
            entity = await session.get(ModelGroupEntity, group_id)
            if entity is None:
                raise KeyError(group_id)

            changes = payload.model_dump(exclude_unset=True)
            for key, value in changes.items():
                if key == "protocol" and value is not None:
                    entity.protocol = value.value
                elif key == "strategy" and value is not None:
                    entity.strategy = value.value
                elif key == "provider_ids" and value is not None:
                    entity.provider_ids_json = json.dumps(value, ensure_ascii=True)
                elif key == "enabled" and value is not None:
                    entity.enabled = 1 if value else 0
                else:
                    setattr(entity, key, value)

            await session.commit()
            await session.refresh(entity)
            return self._to_group(entity)

    async def delete_group(self, group_id: str) -> None:
        async with self._session_factory() as session:
            entity = await session.get(ModelGroupEntity, group_id)
            if entity is None:
                raise KeyError(group_id)
            await session.delete(entity)
            await session.commit()

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
        provider_id: str | None,
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
                provider_id=provider_id,
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

            enabled_groups = await session.scalar(
                select(func.count()).select_from(ModelGroupEntity).where(ModelGroupEntity.enabled == 1)
            )

        gateway_auth = await self.get_gateway_auth_config()

        return OverviewMetrics(
            total_requests=total_value,
            successful_requests=success_value,
            failed_requests=max(total_value - success_value, 0),
            avg_latency_ms=avg_latency,
            active_gateway_keys=len(gateway_auth["keys"]),
            enabled_groups=int(enabled_groups or 0),
            enabled_providers=0,
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

    async def _next_id(self, session: AsyncSession, entity_type, prefix: str) -> str:
        result = await session.execute(select(entity_type.id))
        existing_ids = set(result.scalars().all())
        next_number = len(existing_ids) + 1
        next_id = f"{prefix}-{next_number}"
        while next_id in existing_ids:
            next_number += 1
            next_id = f"{prefix}-{next_number}"
        return next_id

    @staticmethod
    def _to_group(entity: ModelGroupEntity) -> ModelGroup:
        return ModelGroup(
            id=entity.id,
            name=entity.name,
            protocol=entity.protocol,
            strategy=entity.strategy,
            provider_ids=json.loads(entity.provider_ids_json),
            enabled=bool(entity.enabled),
        )

    @staticmethod
    def _to_request_log(entity: RequestLogEntity) -> RequestLogItem:
        return RequestLogItem(
            id=entity.id,
            protocol=entity.protocol,
            requested_model=entity.requested_model,
            matched_group_name=entity.matched_group_name,
            provider_id=entity.provider_id,
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
