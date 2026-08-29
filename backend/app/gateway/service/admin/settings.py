from __future__ import annotations

from typing import Any

from fastapi import Depends

from ....core.time_zone import load_time_zone
from ....models.settings import SettingItem, SettingsUpdate
from ....persistence.editable_settings import canonicalize_editable_settings
from ....persistence.settings_keys import SETTING_TIME_ZONE
from ..app_state import app_state
from ..auth import get_current_admin


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
