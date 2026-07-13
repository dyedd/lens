from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from ._request_log_detail_read import _RequestLogDetailReadMixin
from ._request_log_page_read import _RequestLogPageReadMixin
from ._request_log_site_runtime_read import _RequestLogSiteRuntimeReadMixin


class RequestLogReadMixin(
    _RequestLogPageReadMixin,
    _RequestLogSiteRuntimeReadMixin,
    _RequestLogDetailReadMixin,
):
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory
