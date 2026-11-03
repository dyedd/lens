"""示例插件：给指定渠道换凭据并改写请求。

复制到 `data/plugins/channel_credential_bridge/plugin.py` 即可加载。
它只接管「接管的渠道」设置里列出的渠道 id；留空时不匹配任何渠道。

1. `upstream_request`：给出站请求加标记头（头名可配置）。
2. `upstream_credential`：把渠道里保存的密钥换成插件签发的凭据头。

真实实现里第 2 步通常是一次令牌交换或刷新；这里为演示读取设置里的值。
"""

from __future__ import annotations

from app.plugins.contract import (
    EXT_UPSTREAM_CREDENTIAL,
    EXT_UPSTREAM_REQUEST,
    HookContext,
    PluginContext,
    PluginDefinition,
    PluginManifest,
    PluginSetting,
    UpstreamCall,
)

MANIFEST = PluginManifest(
    id="channel_credential_bridge",
    name="自定义渠道凭据",
    description="为指定渠道改用插件提供的鉴权头，并添加请求标记",
    version="0.4.0",
    author="Lens",
    settings=(
        PluginSetting(
            key="channel_ids",
            label="接管的渠道",
            type="string",
            default="",
            description="逗号分隔的渠道 id；留空不接管任何渠道",
        ),
        PluginSetting(
            key="marker_header",
            label="请求标记头",
            type="string",
            default="x-lens-plugin",
            description="写进出站请求的头名称；留空则不加",
        ),
        PluginSetting(
            key="credential",
            label="签发的凭据",
            type="string",
            default="",
            description="替换渠道密钥时使用的值；留空则不替换",
            secret=True,
        ),
    ),
)


def parse_channel_ids(raw: str) -> frozenset[str]:
    return frozenset(part.strip() for part in raw.split(",") if part.strip())


class MarkerHeaderHook:
    """给出站请求加一个可配置的标记头。"""

    def __init__(self, channel_ids: frozenset[str], marker_header: str) -> None:
        self.channel_ids = channel_ids
        self.marker_header = marker_header.strip()

    def extension(self) -> str:
        return EXT_UPSTREAM_REQUEST

    def matches(self, call: UpstreamCall) -> bool:
        return bool(self.marker_header) and call.channel.id in self.channel_ids

    async def apply(self, call: UpstreamCall, ctx: HookContext) -> UpstreamCall:
        headers = {**call.headers, self.marker_header: MANIFEST.id}
        return UpstreamCall(
            channel=call.channel,
            protocol=call.protocol,
            url=call.url,
            headers=headers,
            body=call.body,
            credential_id=call.credential_id,
            model_name=call.model_name,
        )


class ChannelCredentialHook:
    """把渠道凭据换成插件签发的那一份。"""

    def __init__(self, channel_ids: frozenset[str], credential: str) -> None:
        self.channel_ids = channel_ids
        self.credential = credential

    def extension(self) -> str:
        return EXT_UPSTREAM_CREDENTIAL

    def matches(self, call: UpstreamCall) -> bool:
        return bool(self.credential) and call.channel.id in self.channel_ids

    async def apply(self, call: UpstreamCall, ctx: HookContext) -> UpstreamCall:
        headers = {
            name: value
            for name, value in call.headers.items()
            if name.lower() not in {"authorization", "x-api-key", "x-goog-api-key"}
        }
        if call.protocol == "anthropic":
            headers["x-api-key"] = self.credential
        elif call.protocol == "gemini":
            headers["x-goog-api-key"] = self.credential
        else:
            headers["authorization"] = f"Bearer {self.credential}"
        return UpstreamCall(
            channel=call.channel,
            protocol=call.protocol,
            url=call.url,
            headers=headers,
            body=call.body,
            credential_id=call.credential_id,
            model_name=call.model_name,
        )


def register(context: PluginContext) -> None:
    settings = context.settings
    channel_ids = parse_channel_ids(str(settings.get("channel_ids", "")))
    context.add_upstream_hook(
        MarkerHeaderHook(channel_ids, str(settings.get("marker_header", "")))
    )
    context.add_upstream_hook(
        ChannelCredentialHook(channel_ids, str(settings.get("credential", "")))
    )


PLUGIN = PluginDefinition(manifest=MANIFEST, register=register)
