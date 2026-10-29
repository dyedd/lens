"""插件内核：清单、上下文、扩展点与注册表。"""

from .contract import (
    EXT_MODEL_CATALOG,
    EXT_REQUEST_OBSERVER,
    EXT_UPSTREAM_CREDENTIAL,
    EXT_UPSTREAM_REQUEST,
    PLUGIN_API_VERSION,
    CatalogEntry,
    CronjobContribution,
    ModelCatalogHook,
    PluginContext,
    PluginDefinition,
    PluginManifest,
    RequestObserver,
    RequestRecord,
    TaskHandler,
    UpstreamCall,
    UpstreamHook,
)
from .registry import PluginRegistry

__all__ = [
    "EXT_MODEL_CATALOG",
    "EXT_REQUEST_OBSERVER",
    "EXT_UPSTREAM_CREDENTIAL",
    "EXT_UPSTREAM_REQUEST",
    "PLUGIN_API_VERSION",
    "CatalogEntry",
    "CronjobContribution",
    "ModelCatalogHook",
    "PluginContext",
    "PluginDefinition",
    "PluginManifest",
    "PluginRegistry",
    "RequestObserver",
    "RequestRecord",
    "TaskHandler",
    "UpstreamCall",
    "UpstreamHook",
]
