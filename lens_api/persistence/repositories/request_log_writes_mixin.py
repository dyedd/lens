from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from ..shared import REQUEST_LOG_TERMINAL_STATUSES, RequestLogLifecycleStatus
from ._request_log_create import _RequestLogCreateMixin
from ._request_log_maintenance import _RequestLogMaintenanceMixin
from ._request_log_stats import _RequestLogStatsMixin
from ._request_log_update import _RequestLogUpdateMixin


class RequestLogWriteMixin(
    _RequestLogCreateMixin,
    _RequestLogUpdateMixin,
    _RequestLogMaintenanceMixin,
    _RequestLogStatsMixin,
):
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    @staticmethod
    def _gateway_key_spend_contribution(
        gateway_key_id: str | None,
        lifecycle_status: RequestLogLifecycleStatus | str,
        total_cost_usd: float,
    ) -> float:
        if not gateway_key_id:
            return 0.0
        lifecycle_value = (
            lifecycle_status.value
            if isinstance(lifecycle_status, RequestLogLifecycleStatus)
            else str(lifecycle_status)
        )
        if lifecycle_value not in REQUEST_LOG_TERMINAL_STATUSES:
            return 0.0
        return max(float(total_cost_usd), 0.0)
