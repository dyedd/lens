"""用户插件示例：只观察请求，不改任何东西。

复制到 `data/plugins/request_counter/plugin.py`，
重启 Lens 后就会出现在 设置 → 插件 里。

插件目录默认 `./data/plugins`，可用 `LENS_PLUGINS_DIR` 覆盖；
Docker 部署时把宿主机目录挂到容器的 `/app/data/plugins` 即可。
"""

from __future__ import annotations

import logging

from app.plugins.contract import (
    EXT_REQUEST_OBSERVER,
    PluginContext,
    PluginDefinition,
    PluginManifest,
    RequestRecord,
)

logger = logging.getLogger(__name__)

MANIFEST = PluginManifest(
    id="example_requests",
    name="请求计数示例",
    description="观察已完成的请求并写日志，不改变请求与响应",
    version="0.1.0",
    author="your-name",
    homepage="https://github.com/dyedd/lens",
)


class LoggingObserver:
    """只读观察者。"""

    def extension(self) -> str:
        return EXT_REQUEST_OBSERVER

    async def completed(self, record: RequestRecord) -> None:
        logger.info(
            "example_requests: %s %s %s",
            record.model,
            record.status_code,
            record.latency_ms,
        )


def register(context: PluginContext) -> None:
    context.add_request_observer(LoggingObserver())


PLUGIN = PluginDefinition(manifest=MANIFEST, register=register)
