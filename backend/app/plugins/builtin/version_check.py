"""版本检测插件。"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

import httpx
from packaging import version

from ...core.version import read_system_version
from ...models.settings import SettingItem
from ...persistence.cronjob_store import CronjobSpec
from ...persistence.settings_keys import (
    SETTING_LATEST_VERSION,
    SETTING_LATEST_VERSION_URL,
    SETTING_VERSION_CHECK_AT,
)
from ..contract import PluginContext, PluginDefinition, PluginManifest

if TYPE_CHECKING:
    from ...gateway.service.app_state import AppState

LATEST_RELEASE_URL = "https://api.github.com/repos/dyedd/lens/releases/latest"

MANIFEST = PluginManifest(
    id="version_check",
    name="版本检测",
    description="检测 GitHub releases 是否有新版本",
)

_SPEC = CronjobSpec(
    id=MANIFEST.id,
    name=MANIFEST.name,
    description=MANIFEST.description,
    default_interval_hours=24,
)


async def check_latest_version(state: AppState) -> None:
    """读取 GitHub 最新发布并记录版本状态。"""
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.get(
            LATEST_RELEASE_URL,
            headers={"Accept": "application/vnd.github.v3+json"},
        )
        response.raise_for_status()
        data = response.json()

    latest_version = str(data.get("tag_name", "")).lstrip("v")
    release_url = str(data.get("html_url", ""))
    checked_at = datetime.now(UTC).isoformat()

    if latest_version and version.parse(latest_version) > version.parse(
        read_system_version()
    ):
        items = [
            SettingItem(key=SETTING_LATEST_VERSION, value=latest_version),
            SettingItem(key=SETTING_LATEST_VERSION_URL, value=release_url),
            SettingItem(key=SETTING_VERSION_CHECK_AT, value=checked_at),
        ]
    else:
        items = [
            SettingItem(key=SETTING_VERSION_CHECK_AT, value=checked_at),
            SettingItem(key=SETTING_LATEST_VERSION, value=""),
            SettingItem(key=SETTING_LATEST_VERSION_URL, value=""),
        ]
    await state.settings_repo.upsert_settings(items)


def register(context: PluginContext) -> None:
    state = context.state

    async def run_version_check() -> None:
        await check_latest_version(state)

    context.add_cronjob(_SPEC, run_version_check)


PLUGIN = PluginDefinition(manifest=MANIFEST, register=register)
