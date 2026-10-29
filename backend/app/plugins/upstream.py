"""出站请求扩展点的应用逻辑。

网关只调用 `apply_upstream_hooks`，不关心插件怎么实现。
钩子失败一律 fail open：记录后按原请求发出，绝不让插件阻断转发。
"""

from __future__ import annotations

import logging
from collections.abc import Iterable

from .contract import UpstreamCall, UpstreamHook

logger = logging.getLogger(__name__)


async def apply_upstream_hooks(
    call: UpstreamCall, hooks: Iterable[UpstreamHook]
) -> UpstreamCall:
    """依次应用匹配的钩子，返回最终请求。"""
    current = call
    for hook in hooks:
        try:
            if not hook.matches(current):
                continue
            current = await hook.apply(current)
        except Exception:
            # 插件出问题不应影响转发；保留原请求继续。
            logger.exception("Upstream hook failed: %s", hook.id())
    return current
