"""凭据倍率同步插件。"""

from ...persistence.cronjob_store import CronjobSpec
from ..contract import PluginContext, PluginDefinition, PluginManifest

MANIFEST = PluginManifest(
    id="credential_rate_sync",
    name="凭据倍率同步",
    description="同步 Sub2API 有效倍率与 NewAPI 分组参考倍率",
)

_SPEC = CronjobSpec(
    id=MANIFEST.id,
    name=MANIFEST.name,
    description=MANIFEST.description,
    default_interval_hours=24,
)


def register(context: PluginContext) -> None:
    state = context.state

    async def run_credential_rate_sync() -> None:
        # 任务模块反向依赖 app_state，延迟导入避免循环。
        from ...gateway.service.tasks.credential_rate_tasks import (
            sync_all_site_credential_rates,
        )

        await sync_all_site_credential_rates(state)

    context.add_cronjob(_SPEC, run_credential_rate_sync)


PLUGIN = PluginDefinition(manifest=MANIFEST, register=register)
