"""Refresh the stored Lens release information for the scheduled check."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

import httpx
from packaging import version

from app import __version__
from app.models.settings import SettingItem
from app.persistence.settings_keys import (
    SETTING_LATEST_VERSION,
    SETTING_LATEST_VERSION_URL,
    SETTING_VERSION_CHECK_AT,
)

if TYPE_CHECKING:
    from ..app_state import AppState


async def sync_version(state: AppState) -> None:
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.get(
            "https://dyedd.github.io/lens/version.txt",
            headers={"Accept": "text/plain", "Cache-Control": "no-cache"},
        )
        response.raise_for_status()

    published_version = version.Version(response.text.strip())
    has_update = published_version > version.Version(__version__)
    latest_version = str(published_version) if has_update else ""
    release_url = (
        f"https://github.com/dyedd/lens/releases/tag/v{published_version}"
        if has_update
        else ""
    )
    await state.settings_repo.upsert_settings(
        [
            SettingItem(key=SETTING_LATEST_VERSION, value=latest_version),
            SettingItem(key=SETTING_LATEST_VERSION_URL, value=release_url),
            SettingItem(
                key=SETTING_VERSION_CHECK_AT, value=datetime.now(UTC).isoformat()
            ),
        ]
    )
