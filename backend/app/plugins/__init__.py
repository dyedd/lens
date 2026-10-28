"""插件内核：清单、注册上下文与扩展点。"""

from .contract import (
    PLUGIN_API_VERSION,
    CronjobContribution,
    PluginContext,
    PluginDefinition,
    PluginManifest,
    TaskHandler,
)
from .registry import PluginRegistry

__all__ = [
    "PLUGIN_API_VERSION",
    "CronjobContribution",
    "PluginContext",
    "PluginDefinition",
    "PluginManifest",
    "PluginRegistry",
    "TaskHandler",
]
