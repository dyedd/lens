"""Lens 内置插件。

新增插件时在本模块登记它的 `PLUGIN`，无需改动网关或管理端代码。
插件只能通过扩展点接入核心，不接管平台自身的计划任务与设置。
"""

from ..contract import PluginDefinition
from . import channel_credential_bridge, response_header_stamp

BUILTIN_PLUGINS: tuple[PluginDefinition, ...] = (
    channel_credential_bridge.PLUGIN,
    response_header_stamp.PLUGIN,
)

__all__ = ["BUILTIN_PLUGINS"]
