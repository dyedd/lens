from __future__ import annotations

from typing import Any

from fastapi import Depends

from ....core.time_zone import resolve_time_zone
from ....models import SettingItem, SettingsUpdate
from ....persistence.editable_settings import normalize_editable_setting_items
from ....persistence.shared import SETTING_TIME_ZONE
from ..auth import get_current_admin
from ..app_state import app_state


async def list_settings(_: Any = Depends(get_current_admin)) -> list[SettingItem]:
    """List administrative settings."""
    return await app_state.settings_repo.list_editable_settings()


async def update_settings(
    payload: SettingsUpdate, _: Any = Depends(get_current_admin)
) -> list[SettingItem]:
    """Normalize and persist administrative settings."""
    normalized_items = normalize_editable_setting_items(payload.items)
    current_time_zone = None
    next_time_zone = None
    next_time_zone_value = None
    if any(item.key == SETTING_TIME_ZONE for item in normalized_items):
        runtime = await app_state.settings_repo.get_runtime_settings()
        current_time_zone = str(runtime["time_zone"])
    for item in normalized_items:
        if item.key == SETTING_TIME_ZONE:
            time_zone = resolve_time_zone(item.value)
            next_time_zone = time_zone.key
            next_time_zone_value = time_zone
    await app_state.settings_repo.upsert_settings(normalized_items)
    if next_time_zone is not None and next_time_zone != current_time_zone:
        await app_state.request_log_store.persist_request_log_stats(force=True)
        if next_time_zone_value is not None:
            await app_state.cronjob_runner.reschedule_cronjobs(next_time_zone_value)
    return await app_state.settings_repo.list_editable_settings()
