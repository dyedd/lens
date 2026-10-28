"""渠道模型同步插件。"""

from ...persistence.cronjob_store import CronjobSpec
from ..contract import PluginContext, PluginDefinition, PluginManifest

MANIFEST = PluginManifest(
    id="channel_model_sync",
    name="渠道模型同步",
    description="为启用的渠道拉取上游模型，按凭证规则保存匹配项",
)

_SPEC = CronjobSpec(
    id=MANIFEST.id,
    name=MANIFEST.name,
    description=MANIFEST.description,
    default_interval_hours=24,
)


def register(context: PluginContext) -> None:
    state = context.state

    async def run_channel_model_sync() -> None:
        # 任务模块反向依赖 app_state，延迟导入避免循环。
        from ...gateway.service.tasks.model_sync import sync_channel_models

        await sync_channel_models(state)

    context.add_cronjob(_SPEC, run_channel_model_sync)


PLUGIN = PluginDefinition(manifest=MANIFEST, register=register)
