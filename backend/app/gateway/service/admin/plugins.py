from __future__ import annotations

from typing import Any

from fastapi import Depends

from ....models.plugins import PluginSettingsUpdate, PluginUpdate, PluginView
from ..app_state import app_state
from ..auth import get_current_admin


async def list_plugins(_: Any = Depends(get_current_admin)) -> list[PluginView]:
    """列出插件状态、扩展点与设置。"""
    return app_state.plugin_registry.views()


async def update_plugin(
    plugin_id: str,
    payload: PluginUpdate,
    _: Any = Depends(get_current_admin),
) -> PluginView:
    """启停插件并更新扩展点。"""
    return await app_state.set_plugin_enabled(plugin_id, enabled=payload.enabled)


async def update_plugin_settings(
    plugin_id: str,
    payload: PluginSettingsUpdate,
    _: Any = Depends(get_current_admin),
) -> PluginView:
    """校验并保存插件设置。"""
    return await app_state.set_plugin_settings(plugin_id, payload.values)


async def reload_plugins(_: Any = Depends(get_current_admin)) -> list[PluginView]:
    """重新扫描插件目录并更新扩展点。"""
    return await app_state.reload_plugins()
