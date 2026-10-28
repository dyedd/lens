"""请求日志清理插件。"""

from ...persistence.cronjob_store import CronjobSpec
from ..contract import PluginContext, PluginDefinition, PluginManifest

MANIFEST = PluginManifest(
    id="request_log_prune",
    name="请求日志清理",
    description="按日志保留天数清理过期请求日志",
)

_SPEC = CronjobSpec(
    id=MANIFEST.id,
    name=MANIFEST.name,
    description=MANIFEST.description,
    default_interval_hours=1,
)


def register(context: PluginContext) -> None:
    context.add_cronjob(
        _SPEC,
        context.state.request_log_store.maintenance.prune_request_logs,
    )


PLUGIN = PluginDefinition(manifest=MANIFEST, register=register)
