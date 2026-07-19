from __future__ import annotations

from typing import Any

from fastapi import Depends, Query, Response

from ....models import (
    ProtocolKind,
    RequestLogDetail,
    RequestLogPage,
    RequestLogSortMode,
    RequestLogStatusFilter,
)
from ..auth import get_current_admin
from ..app_state import app_state


async def list_request_logs(
    limit: int = Query(default=100, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    gateway_key_id: str | None = None,
    model_prefix: str | None = None,
    status_filter: RequestLogStatusFilter | None = Query(default=None, alias="status"),
    protocol: ProtocolKind | None = None,
    channel: str | None = None,
    keyword: str | None = None,
    sort: RequestLogSortMode = RequestLogSortMode.LATEST,
    _: Any = Depends(get_current_admin),
) -> RequestLogPage:
    """Return a filtered page of request logs."""
    return await app_state.request_log_store.list_request_log_page(
        limit=limit,
        offset=offset,
        gateway_key_id=gateway_key_id,
        model_prefix=model_prefix,
        status_filter=status_filter,
        protocol=protocol,
        channel=channel,
        keyword=keyword,
        sort=sort,
    )


async def clear_request_logs(_: Any = Depends(get_current_admin)) -> Response:
    """Delete all request logs."""
    await app_state.request_log_store.clear_request_logs()
    return Response(status_code=204)


async def get_request_log_detail(
    log_id: int, _: Any = Depends(get_current_admin)
) -> RequestLogDetail:
    """Return one request log with its payload and attempts."""
    return await app_state.request_log_store.get_request_log(log_id)
