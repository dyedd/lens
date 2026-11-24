from __future__ import annotations

import logging
from typing import Any

from fastapi import Depends
from packaging import version

from app import __version__

from ...models.system_info import AppInfo, PublicBranding, VersionCheckResult
from ...persistence.settings_keys import (
    SETTING_LATEST_VERSION,
    SETTING_LATEST_VERSION_URL,
    SETTING_VERSION_CHECK_AT,
)
from .app_state import app_state
from .auth import get_current_admin

logger = logging.getLogger(__name__)


def _has_version_update(latest_version: str, current_version: str) -> bool:
    if not latest_version:
        return False
    try:
        return version.parse(latest_version) > version.parse(current_version)
    except version.InvalidVersion:
        logger.warning(
            "Invalid version string when comparing %r vs %r",
            latest_version,
            current_version,
        )
        return False


async def get_public_branding() -> PublicBranding:
    """Return public site branding settings."""
    branding = await app_state.settings_repo.get_branding_settings()
    return PublicBranding(
        site_name=branding["site_name"], logo_url=branding["site_logo_url"]
    )


async def get_app_info(_: Any = Depends(get_current_admin)) -> AppInfo:
    """Return administrative application metadata and capabilities."""
    runtime = await app_state.settings_repo.get_runtime_settings()
    return AppInfo(
        system_version=__version__,
        site_name=str(runtime["site_name"]),
        logo_url=str(runtime["site_logo_url"]),
        time_zone=str(runtime["time_zone"]),
    )


async def check_version(_: Any = Depends(get_current_admin)) -> VersionCheckResult:
    """Return the latest stored application update status."""
    current_version = __version__

    settings = await app_state.settings_repo.list_settings()
    settings_dict = {setting.key: setting.value for setting in settings}

    latest_version = settings_dict.get(SETTING_LATEST_VERSION, "")
    latest_url = settings_dict.get(SETTING_LATEST_VERSION_URL, "")
    checked_at = settings_dict.get(SETTING_VERSION_CHECK_AT, "")

    has_update = _has_version_update(latest_version, current_version)

    return VersionCheckResult(
        current_version=current_version,
        latest_version=latest_version if has_update else "",
        release_url=latest_url if has_update else "",
        has_update=has_update,
        checked_at=checked_at,
    )
