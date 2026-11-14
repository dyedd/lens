from __future__ import annotations

from typing import Any, Literal

from fastapi import Depends, Query, Response

from ....core.errors import ResourceConflictError
from ....models.protocols import (
    ProtocolKind,
    RequestLogSortMode,
    RequestLogStatusFilter,
)
from ....models.request_logs import RequestLogDetail, RequestLogPage
from ..app_state import app_state
from ..auth import get_current_admin


async def list_request_logs(
    limit: int = Query(default=100, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    days: int = Query(default=0, ge=-1),
    upstream_model: str | None = None,
    agent: Literal["codex", "claude_code", "other", "unknown"] | None = None,
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
    page = await app_state.request_log_store.queries.list_request_log_page(
        limit=limit,
        offset=offset,
        days=days,
        upstream_model=upstream_model,
        agent=agent,
        gateway_key_id=gateway_key_id,
        model_prefix=model_prefix,
        status_filter=status_filter,
        protocol=protocol,
        channel=channel,
        keyword=keyword,
        sort=sort,
    )
    for item in page.items:
        cancellation = app_state.active_requests.get(item.id)
        item.can_cancel = cancellation is not None and not cancellation.is_cancelled
    return page


async def clear_request_logs(_: Any = Depends(get_current_admin)) -> Response:
    """Delete all request logs."""
    await app_state.request_log_store.maintenance.clear_request_logs()
    return Response(status_code=204)


async def get_request_log_detail(
    log_id: int, _: Any = Depends(get_current_admin)
) -> RequestLogDetail:
    """Return one request log with its payload and attempts."""
    detail = await app_state.request_log_store.queries.get_request_log(log_id)
    cancellation = app_state.active_requests.get(log_id)
    detail.can_cancel = cancellation is not None and not cancellation.is_cancelled
    return detail


async def cancel_request(log_id: int, _: Any = Depends(get_current_admin)) -> Response:
    cancellation = app_state.active_requests.get(log_id)
    if cancellation is None:
        await app_state.request_log_store.queries.get_request_log(log_id)
        raise ResourceConflictError("Request is no longer active on this instance")
    cancellation.cancel()
    return Response(status_code=204)
