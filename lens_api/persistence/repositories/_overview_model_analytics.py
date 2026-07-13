from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from ..shared import (
    OverviewModelAnalytics,
    OverviewModelDailyStatsEntity,
    OverviewModelMetricPoint,
    OverviewModelTrendPoint,
    RequestLogEntity,
    RequestLogLifecycleStatus,
    ZoneInfo,
    func,
    select,
)


class _OverviewModelAnalyticsMixin:
    async def get_model_analytics(
        self,
        days: int = 7,
        gateway_key_id: str | None = None,
        metric: str = "cost",
    ) -> OverviewModelAnalytics:
        """Return model distribution and trend analytics for a metric."""
        model_metric = metric if metric in {"cost", "requests", "tokens"} else "cost"
        normalized_gateway_key_id = self._normalize_gateway_key_id(gateway_key_id)
        time_zone = self._runtime_time_zone(
            await self._settings_repo.get_runtime_settings()
        )
        async with self._session_factory() as session:
            if normalized_gateway_key_id is not None:
                archived_model_rows = []
                if days == -1:
                    live_model_rows = await self._request_log_model_hourly_rows(
                        session,
                        days=days,
                        gateway_key_id=normalized_gateway_key_id,
                        include_archived=True,
                        time_zone=time_zone,
                    )
                else:
                    live_model_rows = await self._request_log_model_daily_rows(
                        session,
                        days=days,
                        gateway_key_id=normalized_gateway_key_id,
                        include_archived=True,
                        time_zone=time_zone,
                    )
            elif days == -1:
                archived_model_rows = []
                live_model_rows = await self._request_log_model_hourly_rows(
                    session, days=days, time_zone=time_zone
                )
            else:
                window_start, window_end = self._resolve_imported_date_window(
                    days, time_zone=time_zone
                )
                archived_model_rows = await self._overview_model_daily_rows(
                    session,
                    start_at=window_start,
                    end_at=window_end,
                )
                live_model_rows = await self._request_log_model_daily_rows(
                    session, days=days, time_zone=time_zone
                )

        merged_rows: dict[tuple[str, str], dict[str, float | str]] = {}
        for date_value, model, requests, total_tokens, total_cost in [
            *archived_model_rows,
            *live_model_rows,
        ]:
            if not model:
                continue
            key = (str(date_value), str(model))
            current = merged_rows.get(key)
            if current is None:
                merged_rows[key] = {
                    "date": str(date_value),
                    "model": str(model),
                    "requests": float(requests),
                    "total_tokens": float(total_tokens),
                    "total_cost_usd": float(total_cost),
                }
                continue
            current["requests"] = float(current["requests"]) + float(requests)
            current["total_tokens"] = float(current["total_tokens"]) + float(
                total_tokens
            )
            current["total_cost_usd"] = float(current["total_cost_usd"]) + float(
                total_cost
            )

        trend_rows = sorted(
            merged_rows.values(),
            key=lambda item: (str(item["date"]), str(item["model"])),
        )

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
            current["total_tokens"] = float(current["total_tokens"]) + float(
                item["total_tokens"]
            )
            current["total_cost_usd"] = float(current["total_cost_usd"]) + float(
                item["total_cost_usd"]
            )

        def metric_value(item: dict[str, float | str]) -> float:
            if model_metric == "requests":
                return float(item["requests"])
            if model_metric == "tokens":
                return float(item["total_tokens"])
            return float(item["total_cost_usd"])

        def secondary_metric_value(item: dict[str, float | str]) -> float:
            if model_metric == "cost":
                return float(item["requests"])
            return float(item["total_cost_usd"])

        aggregated_models = list(model_rows.values())
        distribution_rows = sorted(
            aggregated_models,
            key=lambda item: (
                -metric_value(item),
                -secondary_metric_value(item),
                str(item["model"]),
            ),
        )

        distribution = [
            OverviewModelMetricPoint(
                model=str(item["model"]),
                requests=int(item["requests"]),
                total_tokens=int(item["total_tokens"]),
                total_cost_usd=float(item["total_cost_usd"]),
            )
            for item in distribution_rows[:12]
        ]

        trend = [
            OverviewModelTrendPoint(
                date=str(item["date"]),
                model=str(item["model"]),
                value=metric_value(item),
            )
            for item in trend_rows
        ]

        available_models = sorted(
            {item.model for item in distribution} | {item.model for item in trend}
        )
        return OverviewModelAnalytics(
            distribution=distribution,
            trend=trend,
            available_models=available_models,
        )

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
        rows = (
            await session.execute(
                stmt.order_by(OverviewModelDailyStatsEntity.date.asc())
            )
        ).all()
        return [
            (
                str(date_value),
                str(model),
                int(requests),
                int(total_tokens),
                float(total_cost),
            )
            for date_value, model, requests, total_tokens, total_cost in rows
        ]

    async def _request_log_model_daily_rows(
        self,
        session: AsyncSession,
        *,
        days: int,
        offset_days: int = 0,
        gateway_key_id: str | None = None,
        include_archived: bool = False,
        time_zone: ZoneInfo,
    ) -> list[tuple[str, str, int, int, float]]:
        model_expr = func.coalesce(
            RequestLogEntity.resolved_group_name, RequestLogEntity.requested_group_name
        )
        stmt = (
            select(
                RequestLogEntity.created_at,
                model_expr,
                RequestLogEntity.total_tokens,
                RequestLogEntity.total_cost_usd,
            )
            .where(RequestLogEntity.success == 1)
            .where(
                RequestLogEntity.lifecycle_status
                == RequestLogLifecycleStatus.SUCCEEDED.value
            )
            .where(model_expr.is_not(None))
            .order_by(RequestLogEntity.created_at.asc())
        )
        if not include_archived:
            stmt = stmt.where(RequestLogEntity.stats_archived == 0)
        stmt = self._apply_request_log_window(
            stmt, days=days, offset_days=offset_days, time_zone=time_zone
        )
        stmt = self._apply_gateway_key_filter(stmt, gateway_key_id=gateway_key_id)
        rows = (await session.execute(stmt)).all()
        return self._model_rows_by_local_bucket(rows, "%Y%m%d", time_zone)

    async def _request_log_model_hourly_rows(
        self,
        session: AsyncSession,
        *,
        days: int,
        offset_days: int = 0,
        gateway_key_id: str | None = None,
        include_archived: bool = False,
        time_zone: ZoneInfo,
    ) -> list[tuple[str, str, int, int, float]]:
        model_expr = func.coalesce(
            RequestLogEntity.resolved_group_name, RequestLogEntity.requested_group_name
        )
        stmt = (
            select(
                RequestLogEntity.created_at,
                model_expr,
                RequestLogEntity.total_tokens,
                RequestLogEntity.total_cost_usd,
            )
            .where(RequestLogEntity.success == 1)
            .where(
                RequestLogEntity.lifecycle_status
                == RequestLogLifecycleStatus.SUCCEEDED.value
            )
            .where(model_expr.is_not(None))
            .order_by(RequestLogEntity.created_at.asc())
        )
        if not include_archived:
            stmt = stmt.where(RequestLogEntity.stats_archived == 0)
        stmt = self._apply_request_log_window(
            stmt, days=days, offset_days=offset_days, time_zone=time_zone
        )
        stmt = self._apply_gateway_key_filter(stmt, gateway_key_id=gateway_key_id)
        rows = (await session.execute(stmt)).all()
        return self._model_rows_by_local_bucket(rows, "%Y%m%d%H", time_zone)
