from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import Depends, File, UploadFile
from fastapi.responses import JSONResponse

from app import __version__
from app.core.config import settings
from app.models.privacy import PrivacyConfig
from app.models.settings import SettingItem
from app.persistence.editable_settings import canonicalize_editable_settings

from ....core.time_zone import load_time_zone
from ....models.backups import ConfigBackupRequestLog, ConfigImportResult
from ....persistence.backup_store import BackupStore
from ..app_state import app_state
from ..auth import get_current_admin
from ..privacy_context import PrivacyContext
from ..streaming.privacy_content import clean_privacy_stream_log
from ..tasks.model_group_reconcile import run_model_group_reconcile


async def export_settings_bundle(
    include_logs: bool = False,
    include_gateway_api_keys: bool = False,
    _: Any = Depends(get_current_admin),
) -> JSONResponse:
    """Export the selected configuration as a downloadable backup."""
    await app_state.request_log_store.statistics.persist_request_log_stats(force=True)
    dump = await app_state.backup_store.export_dump(
        lens_version=__version__,
        include_request_logs=include_logs,
        include_gateway_api_keys=include_gateway_api_keys,
    )
    runtime = await app_state.settings_repo.get_runtime_settings()
    _clean_backup_logs(dump.request_logs, runtime["privacy_config"])
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
    privacy_settings = canonicalize_editable_settings(
        item for item in dump.settings if item.key == "privacy_config"
    )
    current = (await app_state.settings_repo.get_runtime_settings())["privacy_config"]
    imported = next(
        (
            PrivacyConfig.model_validate_json(item.value)
            for item in privacy_settings
            if item.key == "privacy_config"
        ),
        None,
    )
    if imported is None:
        imported = current
        dump.settings.append(
            SettingItem(key="privacy_config", value=imported.model_dump_json())
        )
    _clean_backup_logs(dump.request_logs, current)
    _clean_backup_logs(dump.request_logs, imported)
    result = await app_state.backup_store.import_dump(dump)

    app_state.settings_repo.invalidate_settings_cache()
    app_state.apply_router_settings(
        await app_state.settings_repo.get_runtime_settings()
    )
    await run_model_group_reconcile(app_state)
    return result


async def _read_upload_file(file: UploadFile) -> bytes:
    try:
        return await file.read()
    finally:
        await file.close()


def _clean_backup_logs(
    logs: list[ConfigBackupRequestLog], config: PrivacyConfig
) -> None:
    if not config.enabled:
        return
    for log in logs:
        context = PrivacyContext(
            config.model_copy(update={"action": "mask"}), settings.auth_secret_key
        )
        for text in (
            log.request_content,
            log.response_content,
            log.error_message,
            *(attempt.error_message for attempt in log.attempts),
        ):
            if (
                context.clean_log(text, collect_values=True)
                == "[privacy content unavailable]"
            ):
                log.request_content = log.response_content = log.error_message = (
                    "[privacy content unavailable]"
                )
                for attempt in log.attempts:
                    attempt.error_message = "[privacy content unavailable]"
                break
        log.request_content = context.clean_log(log.request_content)
        if log.is_stream and log.response_content:
            log.response_content = (
                clean_privacy_stream_log(log.response_content, log.protocol, context)
                if log.success
                else "[privacy incomplete stream content omitted]"
            )
        else:
            log.response_content = context.clean_log(log.response_content)
        log.error_message = context.clean_log(log.error_message)
        for attempt in log.attempts:
            attempt.error_message = context.clean_log(attempt.error_message)
