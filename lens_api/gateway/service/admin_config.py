from __future__ import annotations

from .runtime_context import (
    Any,
    BOOLEAN_SETTING_KEYS,
    BackupStore,
    ConfigBackupDump,
    ConfigImportResult,
    CronjobItem,
    CronjobRunResult,
    CronjobUpdate,
    Depends,
    FLOAT_SETTING_KEYS,
    File,
    GatewayApiKey,
    GatewayApiKeyCreate,
    GatewayApiKeyUpdate,
    INTEGER_SETTING_KEYS,
    JSONResponse,
    ModelGroup,
    ModelGroupCandidatesRequest,
    ModelGroupCandidatesResponse,
    ModelGroupCreate,
    ModelGroupStats,
    ModelGroupUpdate,
    ModelPriceItem,
    ModelPriceListResponse,
    ModelPriceUpdate,
    Response,
    SETTING_SITE_LOGO_URL,
    SETTING_SITE_NAME,
    SETTING_TIME_ZONE,
    SETTING_UPSTREAM_HEADERS_CONFIG,
    SettingItem,
    SettingsUpdate,
    UploadFile,
    _read_system_version,
    app_state,
    datetime,
    json,
    normalize_upstream_headers_config_json,
    resolve_time_zone,
)
from .tasks import _sync_group_prices
from .auth import get_current_admin


async def list_model_groups(_: Any = Depends(get_current_admin)) -> list[ModelGroup]:
    return await app_state.domain_store.list_groups()


async def get_model_group(
    group_id: str, _: Any = Depends(get_current_admin)
) -> ModelGroup:
    return await app_state.domain_store.get_group(group_id)


async def list_model_group_stats(
    _: Any = Depends(get_current_admin),
) -> list[ModelGroupStats]:
    return await app_state.domain_store.list_group_stats()


async def list_model_prices(
    _: Any = Depends(get_current_admin),
) -> ModelPriceListResponse:
    return await app_state.domain_store.list_model_prices()


async def update_model_price(
    model_key: str, payload: ModelPriceUpdate, _: Any = Depends(get_current_admin)
) -> ModelPriceItem:
    return await app_state.domain_store.upsert_model_price(
        payload.model_copy(update={"model_key": model_key})
    )


async def sync_model_prices(
    _: Any = Depends(get_current_admin),
) -> ModelPriceListResponse:
    await _sync_group_prices(app_state, overwrite_existing=True)
    return await app_state.domain_store.list_model_prices()


async def list_cronjobs(
    _: Any = Depends(get_current_admin),
) -> list[CronjobItem]:
    return await app_state.cronjob_runner.list_cronjobs()


async def update_cronjob(
    task_id: str,
    payload: CronjobUpdate,
    _: Any = Depends(get_current_admin),
) -> CronjobItem:
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
    task = await app_state.cronjob_runner.run_cronjob_now(task_id)
    return CronjobRunResult(cronjob=task)


async def model_group_candidates(
    payload: ModelGroupCandidatesRequest, _: Any = Depends(get_current_admin)
) -> ModelGroupCandidatesResponse:
    return await app_state.domain_store.list_group_candidates(payload)


async def create_model_group(
    payload: ModelGroupCreate, _: Any = Depends(get_current_admin)
) -> ModelGroup:
    return await app_state.domain_store.create_group(payload)


async def update_model_group(
    group_id: str, payload: ModelGroupUpdate, _: Any = Depends(get_current_admin)
) -> ModelGroup:
    return await app_state.domain_store.update_group(group_id, payload)


async def delete_model_group(
    group_id: str, _: Any = Depends(get_current_admin)
) -> Response:
    await app_state.domain_store.delete_group(group_id)
    return Response(status_code=204)


async def list_settings(_: Any = Depends(get_current_admin)) -> list[SettingItem]:
    return await app_state.domain_store.list_settings()


async def update_settings(
    payload: SettingsUpdate, _: Any = Depends(get_current_admin)
) -> list[SettingItem]:
    normalized_items = []
    current_time_zone = None
    next_time_zone = None
    next_time_zone_value = None
    if any(item.key == SETTING_TIME_ZONE for item in payload.items):
        runtime = await app_state.domain_store.get_runtime_settings()
        current_time_zone = str(runtime["time_zone"])
    for item in payload.items:
        if item.key == SETTING_SITE_NAME:
            normalized_items.append(
                SettingItem(key=item.key, value=item.value.strip() or "Lens")
            )
            continue
        if item.key == SETTING_SITE_LOGO_URL:
            normalized_items.append(SettingItem(key=item.key, value=item.value.strip()))
            continue
        if item.key == SETTING_TIME_ZONE:
            time_zone = resolve_time_zone(item.value)
            next_time_zone = time_zone.key
            next_time_zone_value = time_zone
            normalized_items.append(SettingItem(key=item.key, value=time_zone.key))
            continue
        if item.key == SETTING_UPSTREAM_HEADERS_CONFIG:
            normalized_items.append(
                SettingItem(
                    key=item.key,
                    value=normalize_upstream_headers_config_json(item.value),
                )
            )
            continue
        if item.key in INTEGER_SETTING_KEYS:
            value = item.value.strip()
            _parse_integer_setting(item.key, value)
            normalized_items.append(SettingItem(key=item.key, value=value))
            continue
        if item.key in FLOAT_SETTING_KEYS:
            value = item.value.strip()
            _parse_float_setting(item.key, value)
            normalized_items.append(SettingItem(key=item.key, value=value))
            continue
        if item.key in BOOLEAN_SETTING_KEYS:
            normalized_items.append(
                SettingItem(
                    key=item.key,
                    value=(
                        "true"
                        if _parse_boolean_setting(item.key, item.value)
                        else "false"
                    ),
                )
            )
            continue
        normalized_items.append(SettingItem(key=item.key, value=item.value.strip()))
    stored_items = await app_state.domain_store.upsert_settings(normalized_items)
    if next_time_zone is not None and next_time_zone != current_time_zone:
        await app_state.domain_store.persist_request_log_stats(force=True)
        if next_time_zone_value is not None:
            await app_state.cronjob_runner.reschedule_cronjobs(next_time_zone_value)
    return stored_items


async def list_gateway_api_keys(
    _: Any = Depends(get_current_admin),
) -> list[GatewayApiKey]:
    return await app_state.domain_store.list_gateway_api_keys()


async def create_gateway_api_key(
    payload: GatewayApiKeyCreate, _: Any = Depends(get_current_admin)
) -> GatewayApiKey:
    return await app_state.domain_store.create_gateway_api_key(payload)


async def update_gateway_api_key(
    key_id: str, payload: GatewayApiKeyUpdate, _: Any = Depends(get_current_admin)
) -> GatewayApiKey:
    return await app_state.domain_store.update_gateway_api_key(key_id, payload)


async def delete_gateway_api_key(
    key_id: str, _: Any = Depends(get_current_admin)
) -> Response:
    await app_state.domain_store.delete_gateway_api_key(key_id)
    return Response(status_code=204)


async def export_settings_bundle(
    include_logs: bool = False,
    include_gateway_api_keys: bool = False,
    _: Any = Depends(get_current_admin),
) -> JSONResponse:
    dump = await app_state.backup_store.export_dump(
        lens_version=_read_system_version(),
        include_request_logs=include_logs,
        include_gateway_api_keys=include_gateway_api_keys,
    )
    runtime = await app_state.domain_store.get_runtime_settings()
    timestamp = datetime.now(resolve_time_zone(str(runtime["time_zone"]))).strftime(
        "%Y%m%d%H%M%S"
    )
    return JSONResponse(
        content=dump.model_dump(mode="json"),
        headers={
            "content-disposition": f'attachment; filename="lens-backup-{timestamp}.json"',
        },
    )


async def import_settings_bundle(
    file: UploadFile = File(...), _: Any = Depends(get_current_admin)
) -> ConfigImportResult:
    payload = await _read_upload_file(file)
    dump = _parse_config_backup_dump(payload)
    result = await app_state.backup_store.import_dump(dump)

    app_state.domain_store.invalidate_settings_cache()
    return result


def _parse_integer_setting(key: str, value: str) -> int:
    try:
        return int(value)
    except ValueError as exc:
        raise ValueError(f"Invalid integer setting: {key}") from exc


def _parse_float_setting(key: str, value: str) -> float:
    try:
        return float(value)
    except ValueError as exc:
        raise ValueError(f"Invalid numeric setting: {key}") from exc


def _parse_boolean_setting(key: str, value: str) -> bool:
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ValueError(f"Invalid boolean setting: {key}")


async def _read_upload_file(file: UploadFile) -> bytes:
    try:
        return await file.read()
    finally:
        await file.close()


def _parse_config_backup_dump(payload: bytes) -> ConfigBackupDump:
    try:
        return BackupStore.parse_dump(payload)
    except (ValueError, json.JSONDecodeError) as exc:
        raise ValueError("Invalid backup file") from exc
