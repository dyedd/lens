from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from ._overview_common import _OverviewCommonMixin
from ._overview_daily import _OverviewDailyMixin
from ._overview_model_analytics import _OverviewModelAnalyticsMixin
from ._overview_query_aggregation import _OverviewQueryAggregationMixin
from ._overview_summary import _OverviewSummaryMixin


class OverviewMixin(
    _OverviewSummaryMixin,
    _OverviewDailyMixin,
    _OverviewModelAnalyticsMixin,
    _OverviewQueryAggregationMixin,
    _OverviewCommonMixin,
):
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory
