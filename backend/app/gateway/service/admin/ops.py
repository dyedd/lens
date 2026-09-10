from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import Depends, File, HTTPException, Query, Response, UploadFile
from fastapi.responses import JSONResponse

from ....core.time_zone import load_time_zone
from ....models.backups import ConfigImportResult
from ....models.cronjobs import CronjobItem, CronjobRunResult, CronjobUpdate
from ....models.gateway_keys import (
    GatewayApiKey,
    GatewayApiKeyCreate,
    GatewayApiKeyUpdate,
)
from ....models.model_prices import (
    ModelPriceItem,
    ModelPriceListResponse,
    ModelPriceUpdate,
)
from ....models.overview import (
    OverviewDailyPoint,
    OverviewModelAnalytics,
    OverviewSummary,
)
from ....models.protocols import (
    ProtocolKind,
    RequestLogSortMode,
    RequestLogStatusFilter,
)
from ....models.request_logs import RequestLogDetail, RequestLogPage
from ....models.settings import SettingItem, SettingsUpdate
from ....persistence.backup_store import BackupStore
from ....persistence.editable_settings import canonicalize_editable_settings
from ....persistence.settings_keys import SETTING_TIME_ZONE
from ..app_state import app_state, read_system_version
from ..auth import get_current_admin
from ..tasks.model_price_tasks import ModelPriceSyncError, sync_group_prices

# --- backups ---


async def export_settings_bundle(
    include_logs: bool = False,
    include_gateway_api_keys: bool = False,
    _: Any = Depends(get_current_admin),
) -> JSONResponse:
    """Export the selected configuration as a downloadable backup."""
    dump = await app_state.backup_store.export_dump(
        lens_version=read_system_version(),
        include_request_logs=include_logs,
        include_gateway_api_keys=include_gateway_api_keys,
    )
    runtime = await app_state.settings_repo.get_runtime_settings()
    timestamp = datetime.now(load_time_zone(str(runtime["time_zone"]))).strftime(
        "%Y%m%d%H%M%S"
    )
    return JSONResponse(
        content=dump.model_dump(
            mode="json",
            exclude={
                "sites": {
                    "__all__": {
                        "credentials": {
                            "__all__": {
                                "rate_multiplier",
                                "rate_observed_at",
                                "rate_last_synced_at",
                                "rate_last_error",
                            }
                        }
                    }
                }
            },
        ),
        headers={
            "content-disposition": f'attachment; filename="lens-backup-{timestamp}.json"',
        },
    )


async def import_settings_bundle(
    file: UploadFile = File(...), _: Any = Depends(get_current_admin)
) -> ConfigImportResult:
    """Import configuration from an uploaded backup."""
    payload = await _read_upload_file(file)
    dump = BackupStore.parse_dump(payload)
    result = await app_state.backup_store.import_dump(dump)

    app_state.settings_repo.invalidate_settings_cache()
    return result


async def _read_upload_file(file: UploadFile) -> bytes:
    try:
        return await file.read()
    finally:
        await file.close()


# --- cronjobs ---


async def list_cronjobs(
    _: Any = Depends(get_current_admin),
) -> list[CronjobItem]:
    """List registered cron jobs and their schedules."""
    return await app_state.cronjob_runner.list_cronjobs()


async def update_cronjob(
    task_id: str,
    payload: CronjobUpdate,
    _: Any = Depends(get_current_admin),
) -> CronjobItem:
    """Update a cron job schedule."""
    return await app_state.cronjob_runner.update_cronjob(
        task_id,
        enabled=payload.enabled,
        schedule_type=(
            payload.schedule_type.value if payload.schedule_type is not None else None
        ),
        interval_hours=payload.interval_hours,
        run_at_time=payload.run_at_time,
        weekdays=payload.weekdays,
    )


async def run_cronjob(
    task_id: str,
    _: Any = Depends(get_current_admin),
) -> CronjobRunResult:
    """Run a cron job immediately."""
    task = await app_state.cronjob_runner.run_cronjob_now(task_id)
    return CronjobRunResult(cronjob=task)


# --- gateway API keys ---


async def list_gateway_api_keys(
    _: Any = Depends(get_current_admin),
) -> list[GatewayApiKey]:
    """List gateway API keys."""
    return await app_state.gateway_api_key_repo.list_gateway_api_keys()


async def create_gateway_api_key(
    payload: GatewayApiKeyCreate, _: Any = Depends(get_current_admin)
) -> GatewayApiKey:
    """Create a gateway API key."""
    return await app_state.gateway_api_key_repo.create_gateway_api_key(payload)


async def update_gateway_api_key(
    key_id: str, payload: GatewayApiKeyUpdate, _: Any = Depends(get_current_admin)
) -> GatewayApiKey:
    """Update a gateway API key."""
    return await app_state.gateway_api_key_repo.update_gateway_api_key(key_id, payload)


async def delete_gateway_api_key(
    key_id: str, _: Any = Depends(get_current_admin)
) -> Response:
    """Delete a gateway API key."""
    await app_state.gateway_api_key_repo.delete_gateway_api_key(key_id)
    return Response(status_code=204)


# --- model prices ---


async def list_model_prices(
    _: Any = Depends(get_current_admin),
) -> ModelPriceListResponse:
    """List configured model prices."""
    return await app_state.model_price_repo.list_model_prices()


async def update_model_price(
    model_key: str, payload: ModelPriceUpdate, _: Any = Depends(get_current_admin)
) -> ModelPriceItem:
    """Create or update the price for a model group."""
    return await app_state.model_price_repo.upsert_model_price(
        payload.model_copy(update={"model_key": model_key})
    )


async def sync_model_prices(
    _: Any = Depends(get_current_admin),
) -> ModelPriceListResponse:
    """Refresh model prices and return the resulting list."""
    try:
        await sync_group_prices(app_state)
    except ModelPriceSyncError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return await app_state.model_price_repo.list_model_prices()


# --- overview ---


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


# --- request logs ---


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


# --- routing ---


async def get_router_snapshot(_: Any = Depends(get_current_admin)) -> dict[str, Any]:
    """Return the current routing and health snapshot."""
    channels = await app_state.channel_store.list_channels()
    return app_state.router.snapshot(channels).model_dump(mode="json")


# --- settings ---


async def list_settings(_: Any = Depends(get_current_admin)) -> list[SettingItem]:
    """List administrative settings."""
    return await app_state.settings_repo.list_editable_settings()


async def update_settings(
    payload: SettingsUpdate, _: Any = Depends(get_current_admin)
) -> list[SettingItem]:
    """Canonicalize and persist administrative settings."""
    canonical_items = canonicalize_editable_settings(payload.items)
    current_time_zone = None
    next_time_zone = None
    next_time_zone_value = None
    if any(item.key == SETTING_TIME_ZONE for item in canonical_items):
        runtime = await app_state.settings_repo.get_runtime_settings()
        current_time_zone = str(runtime["time_zone"])
    for item in canonical_items:
        if item.key == SETTING_TIME_ZONE:
            time_zone = load_time_zone(item.value)
            next_time_zone = time_zone.key
            next_time_zone_value = time_zone
    await app_state.settings_repo.upsert_settings(canonical_items)
    if next_time_zone is not None and next_time_zone != current_time_zone:
        await app_state.request_log_store.persist_request_log_stats(force=True)
        if next_time_zone_value is not None:
            await app_state.cronjob_runner.reschedule_cronjobs(next_time_zone_value)
    return await app_state.settings_repo.list_editable_settings()


__all__ = [
    "clear_request_logs",
    "create_gateway_api_key",
    "delete_gateway_api_key",
    "export_settings_bundle",
    "get_overview_model_analytics",
    "get_overview_summary",
    "get_request_log_detail",
    "get_router_snapshot",
    "import_settings_bundle",
    "list_cronjobs",
    "list_gateway_api_keys",
    "list_model_prices",
    "list_overview_daily",
    "list_request_logs",
    "list_settings",
    "run_cronjob",
    "sync_model_prices",
    "update_cronjob",
    "update_gateway_api_key",
    "update_model_price",
    "update_settings",
]
