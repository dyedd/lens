"""Lens 内置插件：每个插件把自己挂到内核的扩展点上。

新增插件时在本模块登记它的 `PLUGIN`，无需改动网关或管理端代码。
"""

from ..contract import PluginDefinition
from . import (
    channel_model_sync,
    credential_rate_sync,
    model_price_sync,
    request_log_prune,
    request_log_stats_persist,
    version_check,
)

BUILTIN_PLUGINS: tuple[PluginDefinition, ...] = (
    request_log_prune.PLUGIN,
    model_price_sync.PLUGIN,
    request_log_stats_persist.PLUGIN,
    version_check.PLUGIN,
    channel_model_sync.PLUGIN,
    credential_rate_sync.PLUGIN,
)

__all__ = ["BUILTIN_PLUGINS"]
