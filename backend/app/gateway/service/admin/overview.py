from __future__ import annotations

from typing import Any, Literal

from fastapi import Depends, Query

from ....models.overview import (
    OverviewAttribution,
    OverviewDailyPoint,
    OverviewModelAnalytics,
    OverviewSummary,
)
from ..app_state import app_state
from ..auth import get_current_admin


async def get_overview_summary(
    days: int = 7,
    _: Any = Depends(get_current_admin),
) -> OverviewSummary:
    """Return aggregate request statistics for the selected period."""
    return await app_state.request_log_store.overview.get_overview_summary(
        days=days,
    )


async def list_overview_daily(
    days: int = 0,
    granularity: str = Query(default="daily", pattern="^(daily|hourly)$"),
    _: Any = Depends(get_current_admin),
) -> list[OverviewDailyPoint]:
    """List daily request statistics for the selected period."""
    if granularity == "hourly":
        return await app_state.request_log_store.attribution.hourly_points(days=days)
    return await app_state.request_log_store.overview.list_overview_daily(
        days=days,
    )


async def get_overview_model_analytics(
    days: int = 7,
    metric: str = Query(default="cost", pattern="^(cost|requests|tokens)$"),
    gateway_key_id: str | None = None,
    _: Any = Depends(get_current_admin),
) -> OverviewModelAnalytics:
    """Return model analytics for the selected metric and filters."""
    return await app_state.request_log_store.overview.get_model_analytics(
        days=days,
        metric=metric,
        gateway_key_id=gateway_key_id,
    )


async def get_overview_attribution(
    days: int = Query(default=-1, ge=-1),
    dimension: Literal["model", "channel"] = "model",
    metric: str = Query(
        default="cache", pattern="^(requests|tokens|cost|cache|duration)$"
    ),
    filter_key: str | None = None,
    _: Any = Depends(get_current_admin),
) -> OverviewAttribution:
    return await app_state.request_log_store.attribution.get_analytics(
        days=days,
        dimension=dimension,
        metric=metric,
        filter_key=filter_key,
    )
