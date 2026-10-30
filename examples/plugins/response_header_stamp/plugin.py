"""示例插件：给指定渠道的回复补一个标记头。

复制到 `data/plugins/response_header_stamp/plugin.py` 即可加载。

1. `upstream_response`：改写非流式回复（这里只加一个响应头）。
2. `requires`：依赖 `channel_credential_bridge`；它停用时本插件进入 pending。
"""

from __future__ import annotations

from app.plugins.contract import (
    EXT_UPSTREAM_RESPONSE,
    HookContext,
    PluginContext,
    PluginDefinition,
    PluginManifest,
    PluginSetting,
    UpstreamResponse,
)

MANIFEST = PluginManifest(
    id="response_header_stamp",
    name="响应标记",
    description="给指定渠道的回复补一个标记头",
    version="0.3.0",
    author="Lens",
    requires=("channel_credential_bridge",),
    settings=(
        PluginSetting(
            key="channel_ids",
            label="标记的渠道",
            type="string",
            default="",
            description="逗号分隔的渠道 id；留空不标记任何渠道",
        ),
    ),
)


def parse_channel_ids(raw: str) -> frozenset[str]:
    return frozenset(part.strip() for part in raw.split(",") if part.strip())


class ResponseStampHook:
    """在响应头里补一个标记。"""

    def __init__(self, channel_ids: frozenset[str]) -> None:
        self.channel_ids = channel_ids

    def extension(self) -> str:
        return EXT_UPSTREAM_RESPONSE

    def matches(self, response: UpstreamResponse) -> bool:
        return response.channel.id in self.channel_ids

    async def apply(
        self, response: UpstreamResponse, ctx: HookContext
    ) -> UpstreamResponse:
        headers = {**response.headers, "x-lens-response-plugin": MANIFEST.id}
        return UpstreamResponse(
            channel=response.channel,
            protocol=response.protocol,
            status_code=response.status_code,
            headers=headers,
            content=response.content,
        )


def register(context: PluginContext) -> None:
    channel_ids = parse_channel_ids(str(context.settings.get("channel_ids", "")))
    context.add_response_hook(ResponseStampHook(channel_ids))


PLUGIN = PluginDefinition(manifest=MANIFEST, register=register)
