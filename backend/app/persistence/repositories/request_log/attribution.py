from __future__ import annotations

import json
from collections import defaultdict
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, Literal
from zoneinfo import ZoneInfo

from sqlalchemy import Integer, func, select, union_all
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.runtime_channel_ids import split_runtime_channel_id
from app.models.overview import (
    OverviewAttribution,
    OverviewAttributionCoverage,
    OverviewAttributionFilterOption,
    OverviewAttributionItem,
    OverviewAttributionTrendPoint,
    OverviewDailyPoint,
)
from app.persistence.entities import RequestLogEntity, SiteProtocolConfigEntity
from app.persistence.stats_entities import OverviewAttributionHourlyStatsEntity

from .query import resolve_request_log_window
from .types import REQUEST_LOG_TERMINAL_STATUSES

if TYPE_CHECKING:
    from .overview import RequestLogOverview

METRICS = (
    "request_count",
    "successful_requests",
    "failed_requests",
    "wait_time_ms",
    "input_tokens",
    "cache_read_input_tokens",
    "cache_write_input_tokens",
    "output_tokens",
    "total_tokens",
    "input_cost_usd",
    "output_cost_usd",
    "total_cost_usd",
)


class RequestLogAttribution:
    def __init__(self, overview: RequestLogOverview) -> None:
        self.overview = overview

    async def load_buckets(
        self, session: AsyncSession, *, days: int, time_zone: ZoneInfo
    ) -> list[dict[str, Any]]:
        start, end = resolve_request_log_window(days, time_zone=time_zone)
        archive = OverviewAttributionHourlyStatsEntity
        archive_epoch = (
            func.strftime("%s", archive.hour_start)
            if session.get_bind().dialect.name == "sqlite"
            else func.extract("epoch", archive.hour_start)
        )
        archived = select(
            func.floor(archive_epoch / 900).label("bucket"),
            archive.upstream_model.label("model"),
            archive.channel_id,
            archive.channel_name,
            *[getattr(archive, name) for name in METRICS],
        )
        if start is not None:
            archived = archived.where(
                archive.hour_start >= start, archive.hour_start < end
            )
        log = RequestLogEntity
        epoch = (
            func.strftime("%s", log.created_at)
            if session.get_bind().dialect.name == "sqlite"
            else func.extract("epoch", log.created_at)
        )
        bucket = func.floor(epoch / 900)
        model = func.coalesce(log.upstream_model_name, "")
        channel = func.coalesce(log.channel_id, "")
        columns = {
            "request_count": func.count(),
            "successful_requests": func.sum(
                (log.lifecycle_status == "succeeded").cast(Integer)
            ),
            "failed_requests": func.sum(
                (log.lifecycle_status == "failed").cast(Integer)
            ),
            "wait_time_ms": func.sum(log.latency_ms),
            **{name: func.sum(getattr(log, name)) for name in METRICS[4:]},
        }
        stmt = select(
            bucket.label("bucket"),
            model.label("model"),
            channel.label("channel_id"),
            func.max(log.channel_name).label("channel_name"),
            *[value.label(name) for name, value in columns.items()],
        ).where(
            log.attribution_archived == 0,
            log.lifecycle_status.in_(REQUEST_LOG_TERMINAL_STATUSES),
        )
        if start is not None:
            stmt = stmt.where(log.created_at >= start, log.created_at < end)
        stmt = stmt.group_by(bucket, model, channel)
        # 一条查询读取归档和明细，避免归档事务提交时漏计或重复。
        buckets = []
        for row in (await session.execute(union_all(archived, stmt))).mappings():
            buckets.append(
                {
                    **dict(row),
                    "hour_start": datetime.fromtimestamp(
                        float(row["bucket"]) * 900, UTC
                    ).replace(tzinfo=None),
                }
            )
        return sorted(buckets, key=lambda row: row["hour_start"])

    async def get_analytics(
        self,
        *,
        days: int,
        dimension: Literal["model", "channel"],
        metric: str,
        filter_key: str | None = None,
    ) -> OverviewAttribution:
        overview = self.overview
        time_zone = overview.runtime_time_zone(
            await overview.settings_repo.get_runtime_settings()
        )
        async with overview.session_factory() as session:
            buckets = await self.load_buckets(session, days=days, time_zone=time_zone)
            configs = {
                row.id: row.protocols_json
                for row in (
                    await session.scalars(select(SiteProtocolConfigEntity))
                ).all()
            }
            daily = await overview.merged_daily_points(
                session, days=days, time_zone=time_zone
            )
        labels = {
            row["channel_id"]: row["channel_name"]
            or row["channel_id"]
            or "Unknown channel"
            for row in buckets
        }

        def deleted(key: str) -> bool:
            parsed = split_runtime_channel_id(key)
            if not parsed:
                return bool(key)
            return parsed[0] not in configs or parsed[1].value not in json.loads(
                configs[parsed[0]]
            )

        def label(key: str, dim: str) -> str:
            return (
                (key or "Unknown model")
                if dim == "model"
                else labels.get(key, key or "Unknown channel")
            )

        opposite = "channel" if dimension == "model" else "model"
        opposite_field = "channel_id" if opposite == "channel" else "model"
        filters = [
            OverviewAttributionFilterOption(
                key=key,
                label=label(key, opposite),
                is_deleted=opposite == "channel" and deleted(key),
            )
            for key in sorted({row[opposite_field] for row in buckets})
        ]
        groups: dict[str, dict[str, float]] = {}
        trend_groups: dict[tuple[str, str], dict[str, float]] = {}
        for row in buckets:
            if filter_key is not None and row[opposite_field] != filter_key:
                continue
            key = row["model" if dimension == "model" else "channel_id"]
            date = (
                row["hour_start"]
                .replace(tzinfo=UTC)
                .astimezone(time_zone)
                .strftime("%Y%m%d%H" if days == -1 else "%Y%m%d")
            )
            for target in (
                groups.setdefault(key, defaultdict(float)),
                trend_groups.setdefault((date, key), defaultdict(float)),
            ):
                for name in METRICS:
                    target[name] += row[name] or 0

        def rate(values: dict[str, float]) -> float | None:
            return (
                values["cache_read_input_tokens"] / values["input_tokens"]
                if values["input_tokens"]
                else None
            )

        items = [
            OverviewAttributionItem(
                key=key,
                label=label(key, dimension),
                is_deleted=dimension == "channel" and deleted(key),
                requests=int(values["request_count"]),
                **{
                    name: values[name]
                    for name in METRICS
                    if name
                    not in ("request_count", "input_cost_usd", "output_cost_usd")
                },
                cache_hit_rate=rate(values),
            )
            for key, values in groups.items()
        ]
        field = {
            "requests": "request_count",
            "tokens": "total_tokens",
            "cost": "total_cost_usd",
            "duration": "wait_time_ms",
        }.get(metric)
        trend = [
            OverviewAttributionTrendPoint(
                date=date, key=key, value=values[field] if field else rate(values)
            )
            for (date, key), values in sorted(trend_groups.items())
        ]
        known = sum(row["request_count"] for row in buckets)
        completed = sum(point.request_count for point in daily)
        complete = known == completed
        return OverviewAttribution(
            items=sorted(items, key=lambda item: (-item.requests, item.key)),
            trend=trend,
            filters=filters,
            dimension=dimension,
            metric=metric,
            filter_key=filter_key,
            filter_label=label(filter_key, opposite)
            if filter_key is not None
            else None,
            coverage=OverviewAttributionCoverage(
                has_dimension_history=complete, has_hourly_history=complete
            ),
        )

    async def hourly_points(self, *, days: int) -> list[OverviewDailyPoint]:
        overview = self.overview
        time_zone = overview.runtime_time_zone(
            await overview.settings_repo.get_runtime_settings()
        )
        async with overview.session_factory() as session:
            buckets = await self.load_buckets(session, days=days, time_zone=time_zone)
            daily = await overview.merged_daily_points(
                session, days=days, time_zone=time_zone
            )
        # 老归档没有小时信息时保留真实日粒度，不能将全天汇总冒充某个小时。
        if sum(row["request_count"] for row in buckets) != sum(
            point.request_count for point in daily
        ):
            return daily
        points: dict[str, dict[str, float]] = {}
        for row in buckets:
            date = (
                row["hour_start"]
                .replace(tzinfo=UTC)
                .astimezone(time_zone)
                .strftime("%Y%m%d%H")
            )
            values = points.setdefault(date, defaultdict(float))
            for name in METRICS:
                values[name] += row[name] or 0
        fields = set(OverviewDailyPoint.model_fields) - {"date"}
        return [
            OverviewDailyPoint(date=date, **{name: values[name] for name in fields})
            for date, values in sorted(points.items())
        ]
