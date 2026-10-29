"""示例扩展插件：给上游响应补一个标记头，并依赖渠道凭据插件。

它演示两件事：

1. `upstream_response`：改写上游返回的响应（这里只加一个响应头）。
2. `requires`：声明依赖 `channel_credential_bridge`，依赖停用时本插件进入 pending。
"""

from __future__ import annotations

from ...models.protocols import ChannelProxyMode
from ..contract import (
    EXT_UPSTREAM_RESPONSE,
    PluginContext,
    PluginDefinition,
    PluginManifest,
    UpstreamResponse,
)

MANIFEST = PluginManifest(
    id="response_header_stamp",
    name="响应标记",
    description="给经自定义渠道凭据插件处理的响应补一个标记头",
    version="0.1.0",
    author="Lens",
    requires=("channel_credential_bridge",),
)

MATCHED_PROXY_MODE = ChannelProxyMode.CUSTOM


class ResponseStampHook:
    """在响应头里补一个标记。"""

    def extension(self) -> str:
        return EXT_UPSTREAM_RESPONSE

    def matches(self, response: UpstreamResponse) -> bool:
        return response.channel.proxy_mode == MATCHED_PROXY_MODE

    async def apply(self, response: UpstreamResponse) -> UpstreamResponse:
        headers = {**response.headers, "x-lens-response-plugin": MANIFEST.id}
        return UpstreamResponse(
            channel=response.channel,
            protocol=response.protocol,
            status_code=response.status_code,
            headers=headers,
            content=response.content,
        )


def register(context: PluginContext) -> None:
    context.add_response_hook(ResponseStampHook())


PLUGIN = PluginDefinition(manifest=MANIFEST, register=register)
