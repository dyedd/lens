"""扩展点的应用逻辑。

网关只调用这里的函数，不关心插件怎么实现。
所有钩子都 fail open：插件出错只记录日志，不阻断转发。
"""

from __future__ import annotations

import logging
from collections.abc import Iterable

from ..models.channels import ChannelConfig
from .contract import (
    CatalogEntry,
    ModelCatalogHook,
    RequestObserver,
    RequestRecord,
    ResponseHook,
    UpstreamCall,
    UpstreamHook,
    UpstreamResponse,
)

logger = logging.getLogger(__name__)


async def apply_upstream_hooks(
    call: UpstreamCall, hooks: Iterable[UpstreamHook]
) -> UpstreamCall:
    """依次应用匹配的请求钩子，返回最终请求。"""
    current = call
    for hook in hooks:
        try:
            if not hook.matches(current):
                continue
            current = await hook.apply(current)
        except Exception:
            logger.exception("Upstream hook failed: %s", hook.extension())
    return current


async def apply_response_hooks(
    response: UpstreamResponse, hooks: Iterable[ResponseHook]
) -> UpstreamResponse:
    """依次应用匹配的响应钩子，返回最终响应。"""
    current = response
    for hook in hooks:
        try:
            if not hook.matches(current):
                continue
            current = await hook.apply(current)
        except Exception:
            logger.exception("Response hook failed: %s", hook.extension())
    return current


async def notify_request_observers(
    record: RequestRecord, observers: Iterable[RequestObserver]
) -> None:
    """把已完成的请求交给观察者；只读，异常被吞掉。"""
    for observer in observers:
        try:
            await observer.completed(record)
        except Exception:
            logger.exception("Request observer failed: %s", observer.extension())


async def collect_catalog_entries(
    channel: ChannelConfig, hooks: Iterable[ModelCatalogHook]
) -> list[CatalogEntry]:
    """收集插件为渠道补充的模型，去重并保留首次出现的顺序。"""
    entries: list[CatalogEntry] = []
    seen: set[str] = set()
    for hook in hooks:
        try:
            if not hook.matches(channel):
                continue
            contributed = await hook.models(channel)
        except Exception:
            logger.exception("Model catalog hook failed: %s", hook.extension())
            continue
        for entry in contributed or ():
            name = entry.model_name.strip()
            if not name or name in seen:
                continue
            seen.add(name)
            entries.append(CatalogEntry(model_name=name, enabled=entry.enabled))
    return entries
