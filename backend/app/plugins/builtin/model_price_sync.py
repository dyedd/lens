"""模型价格同步插件。"""

from ...persistence.cronjob_store import CronjobSpec
from ..contract import PluginContext, PluginDefinition, PluginManifest

MANIFEST = PluginManifest(
    id="model_price_sync",
    name="模型价格同步",
    description="从 LiteLLM 同步模型价格",
)

_SPEC = CronjobSpec(
    id=MANIFEST.id,
    name=MANIFEST.name,
    description=MANIFEST.description,
    default_interval_hours=24,
)


def register(context: PluginContext) -> None:
    state = context.state

    async def run_model_price_sync() -> None:
        # 任务模块反向依赖 app_state，延迟导入避免循环。
        from ...gateway.service.tasks.model_price_tasks import sync_group_prices

        await sync_group_prices(state)

    context.add_cronjob(_SPEC, run_model_price_sync)


PLUGIN = PluginDefinition(manifest=MANIFEST, register=register)
