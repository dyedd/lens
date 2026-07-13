from __future__ import annotations

from typing import Any

from fastapi import Depends, Query

from ....models import OverviewDailyPoint, OverviewModelAnalytics, OverviewSummary
from ..auth import get_current_admin
from ..app_state import app_state


async def get_overview_summary(
    days: int = 7,
    _: Any = Depends(get_current_admin),
) -> OverviewSummary:
    """Return aggregate request statistics for the selected period."""
    return await app_state.request_log_store.get_overview_summary(
        days=days,
    )


async def list_overview_daily(
    days: int = 0,
    _: Any = Depends(get_current_admin),
) -> list[OverviewDailyPoint]:
    """List daily request statistics for the selected period."""
    return await app_state.request_log_store.list_overview_daily(
        days=days,
    )


async def get_overview_model_analytics(
    days: int = 7,
    metric: str = Query(default="cost", pattern="^(cost|requests|tokens)$"),
    gateway_key_id: str | None = None,
    _: Any = Depends(get_current_admin),
) -> OverviewModelAnalytics:
    """Return model analytics for the selected metric and filters."""
    return await app_state.request_log_store.get_model_analytics(
        days=days,
        metric=metric,
        gateway_key_id=gateway_key_id,
    )
