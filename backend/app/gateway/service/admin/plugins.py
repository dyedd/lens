from __future__ import annotations

from typing import Any

from fastapi import Depends

from ....models.plugins import PluginSettingsUpdate, PluginUpdate, PluginView
from ..app_state import app_state
from ..auth import get_current_admin


async def list_plugins(_: Any = Depends(get_current_admin)) -> list[PluginView]:
    """List registered plugins with state, extensions, and settings."""
    return app_state.plugin_registry.views()


async def update_plugin(
    plugin_id: str,
    payload: PluginUpdate,
    _: Any = Depends(get_current_admin),
) -> PluginView:
    """Enable or disable a plugin and reapply its extensions."""
    return await app_state.set_plugin_enabled(plugin_id, enabled=payload.enabled)


async def update_plugin_settings(
    plugin_id: str,
    payload: PluginSettingsUpdate,
    _: Any = Depends(get_current_admin),
) -> PluginView:
    """Validate and save one plugin's settings."""
    return await app_state.set_plugin_settings(plugin_id, payload.values)


async def reload_plugins(_: Any = Depends(get_current_admin)) -> list[PluginView]:
    """Rescan the plugins directory and reapply everything, without restart."""
    return await app_state.reload_plugins()
