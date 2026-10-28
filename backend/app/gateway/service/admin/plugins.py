from __future__ import annotations

from typing import Any

from fastapi import Depends

from ....models.plugins import PluginUpdate, PluginView
from ..app_state import app_state
from ..auth import get_current_admin


async def list_plugins(_: Any = Depends(get_current_admin)) -> list[PluginView]:
    """List registered plugins with their state and contributions."""
    return app_state.plugin_registry.views()


async def update_plugin(
    plugin_id: str,
    payload: PluginUpdate,
    _: Any = Depends(get_current_admin),
) -> PluginView:
    """Enable or disable a plugin and reapply its contributions."""
    return await app_state.set_plugin_enabled(plugin_id, enabled=payload.enabled)


__all__ = ["list_plugins", "update_plugin"]
