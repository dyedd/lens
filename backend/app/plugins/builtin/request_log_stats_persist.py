"""请求日志统计归档插件。"""

from ...persistence.cronjob_store import CronjobSpec
from ..contract import PluginContext, PluginDefinition, PluginManifest

MANIFEST = PluginManifest(
    id="request_log_stats_persist",
    name="请求日志统计落库",
    description="归档请求日志统计数据",
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
        context.state.request_log_store.statistics.persist_request_log_stats,
    )


PLUGIN = PluginDefinition(manifest=MANIFEST, register=register)
