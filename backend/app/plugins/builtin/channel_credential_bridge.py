"""示例扩展插件：给自定义渠道换凭据、改写请求、补充模型并观察请求。

四个能力都演示在同一插件里，方便对照扩展点写法：

1. `upstream_request`：给出站请求加标记头。
2. `upstream_credential`：把渠道里保存的密钥换成插件签发的凭据头。
3. `model_catalog`：为匹配渠道补充一个上游没返回的模型。
4. `request_observer`：只读地记录已完成请求，不改变任何结果。

真实实现里第 2 步通常是一次令牌交换或刷新；这里为演示给出固定值。
"""

from __future__ import annotations

import logging

from ...models.channels import ChannelConfig
from ...models.protocols import ChannelProxyMode
from ..contract import (
    EXT_MODEL_CATALOG,
    EXT_REQUEST_OBSERVER,
    EXT_UPSTREAM_CREDENTIAL,
    EXT_UPSTREAM_REQUEST,
    CatalogEntry,
    PluginContext,
    PluginDefinition,
    PluginManifest,
    RequestRecord,
    UpstreamCall,
)

logger = logging.getLogger(__name__)

MANIFEST = PluginManifest(
    id="channel_credential_bridge",
    name="自定义渠道凭据",
    description="为指定渠道改用插件提供的鉴权头，并补齐请求、模型与请求观察",
    version="0.2.0",
    author="Lens",
)

# 只接管明确标记为自定义代理模式的渠道，避免影响平台默认鉴权。
MATCHED_PROXY_MODE = ChannelProxyMode.CUSTOM


class RequestRewriteHook:
    """给出站请求加一个标记头。"""

    def extension(self) -> str:
        return EXT_UPSTREAM_REQUEST

    def matches(self, call: UpstreamCall) -> bool:
        return call.channel.proxy_mode == MATCHED_PROXY_MODE

    async def apply(self, call: UpstreamCall) -> UpstreamCall:
        headers = {**call.headers, "x-lens-plugin": MANIFEST.id}
        return UpstreamCall(
            channel=call.channel,
            protocol=call.protocol,
            url=call.url,
            headers=headers,
            body=call.body,
            credential_id=call.credential_id,
        )


class ChannelCredentialHook:
    """把渠道凭据换成插件签发的那一份。"""

    def extension(self) -> str:
        return EXT_UPSTREAM_CREDENTIAL

    def matches(self, call: UpstreamCall) -> bool:
        return call.channel.proxy_mode == MATCHED_PROXY_MODE

    async def apply(self, call: UpstreamCall) -> UpstreamCall:
        headers = {**call.headers, "authorization": "Bearer plugin-issued-credential"}
        return UpstreamCall(
            channel=call.channel,
            protocol=call.protocol,
            url=call.url,
            headers=headers,
            body=call.body,
            credential_id=call.credential_id,
        )


class ExtraModelCatalog:
    """为匹配渠道补充一个上游没返回的模型。"""

    def extension(self) -> str:
        return EXT_MODEL_CATALOG

    def matches(self, channel: ChannelConfig) -> bool:
        return channel.proxy_mode == MATCHED_PROXY_MODE

    async def models(self, channel: ChannelConfig) -> list[CatalogEntry]:
        return [CatalogEntry(model_name=f"{channel.name}-plugin-model")]


class RequestLogObserver:
    """只读地记录已完成请求。"""

    def extension(self) -> str:
        return EXT_REQUEST_OBSERVER

    async def completed(self, record: RequestRecord) -> None:
        logger.info(
            "plugin observed request: model=%s status=%s stream=%s",
            record.model,
            record.status_code,
            record.is_stream,
        )


def register(context: PluginContext) -> None:
    context.add_upstream_hook(RequestRewriteHook())
    context.add_upstream_hook(ChannelCredentialHook())
    context.add_model_catalog_hook(ExtraModelCatalog())
    context.add_request_observer(RequestLogObserver())


PLUGIN = PluginDefinition(manifest=MANIFEST, register=register)
