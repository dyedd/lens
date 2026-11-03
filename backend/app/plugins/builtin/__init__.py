"""Lens 内置插件。

新增插件时在本模块登记它的 `PLUGIN`，无需改动网关或管理端代码。
插件只能通过扩展点接入核心，不接管平台自身的计划任务与设置。
示例插件在仓库的 `examples/plugins/` 下，复制到插件目录后才会加载。
"""

from ..contract import PluginDefinition

BUILTIN_PLUGINS: tuple[PluginDefinition, ...] = ()

__all__ = ["BUILTIN_PLUGINS"]
