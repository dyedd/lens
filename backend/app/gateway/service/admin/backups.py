from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import Depends, File, UploadFile
from fastapi.responses import JSONResponse

from ....core.time_zone import load_time_zone
from ....models.backups import ConfigImportResult
from ....persistence.backup_store import BackupStore
from ..app_state import app_state, read_system_version
from ..auth import get_current_admin
from ..tasks.model_group_reconcile import run_model_group_reconcile


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
    await run_model_group_reconcile(app_state)
    return result


async def _read_upload_file(file: UploadFile) -> bytes:
    try:
        return await file.read()
    finally:
        await file.close()
