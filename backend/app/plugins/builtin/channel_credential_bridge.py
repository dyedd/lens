"""示例扩展插件：为自定义渠道提供凭据并改写出站请求。

它演示两个能力，都不绑定任何具体厂商：

1. 出站请求改写：给匹配渠道的请求补一个可观测的标记头。
2. 渠道鉴权：把渠道里保存的密钥换成插件运行时取得的凭据头。

真实实现里，第 2 步通常是一次令牌交换或刷新；这里用渠道配置的
`channel_proxy` 之外没有任何外部依赖的方式演示调用形态。
"""

from __future__ import annotations

from ...models.protocols import ChannelProxyMode
from ..contract import (
    PluginContext,
    PluginDefinition,
    PluginManifest,
    UpstreamCall,
)

MANIFEST = PluginManifest(
    id="channel_credential_bridge",
    name="自定义渠道凭据",
    description="为指定渠道改用插件提供的鉴权头，并改写它的出站请求",
    version="0.1.0",
)

# 只接管明确标记为自定义代理模式的渠道，避免影响平台默认鉴权。
MATCHED_PROXY_MODE = ChannelProxyMode.CUSTOM


class ChannelCredentialBridge:
    """给匹配渠道换鉴权头，并加一个标记头。"""

    def id(self) -> str:
        return "upstream_credential"

    def matches(self, call: UpstreamCall) -> bool:
        return call.channel.proxy_mode == MATCHED_PROXY_MODE

    async def apply(self, call: UpstreamCall) -> UpstreamCall:
        headers = dict(call.headers)
        # 演示鉴权接管：这里换成插件自己取得的凭据。
        headers["authorization"] = "Bearer plugin-issued-credential"
        headers["x-lens-plugin"] = MANIFEST.id
        return UpstreamCall(
            channel=call.channel,
            protocol=call.protocol,
            url=call.url,
            headers=headers,
            body=call.body,
            credential_id=call.credential_id,
        )


def register(context: PluginContext) -> None:
    context.add_upstream_hook(ChannelCredentialBridge())


PLUGIN = PluginDefinition(manifest=MANIFEST, register=register)
