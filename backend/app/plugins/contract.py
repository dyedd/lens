from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Protocol

from ..models.channels import ChannelConfig
from ..persistence.cronjob_store import CronjobSpec

if TYPE_CHECKING:
    from ..gateway.service.app_state import AppState

PLUGIN_API_VERSION = 1

TaskHandler = Callable[[], Awaitable[None]]


@dataclass(frozen=True, slots=True)
class PluginManifest:
    """插件身份与兼容性声明。"""

    id: str
    name: str
    description: str = ""
    version: str = "1.0.0"
    api_version: int = PLUGIN_API_VERSION


@dataclass(frozen=True, slots=True)
class UpstreamCall:
    """一次即将发往上游的请求，插件可读可改。"""

    channel: ChannelConfig
    protocol: str
    url: str
    headers: dict[str, str]
    body: dict[str, Any]
    credential_id: str | None = None


@dataclass(frozen=True, slots=True)
class UpstreamCredential:
    """插件为渠道提供的凭据，用于替代渠道里保存的密钥。"""

    headers: Mapping[str, str]
    query: Mapping[str, str] = field(default_factory=dict)


class UpstreamHook(Protocol):
    """出站请求扩展点：改写请求，或接手渠道鉴权。

    `apply` 是异步的，允许插件在发送前换取、刷新凭据。
    """

    def id(self) -> str: ...

    def matches(self, call: UpstreamCall) -> bool: ...

    async def apply(self, call: UpstreamCall) -> UpstreamCall: ...


@dataclass(frozen=True, slots=True)
class CronjobContribution:
    """插件追加的计划任务（附加能力，不是插件的主定位）。"""

    spec: CronjobSpec
    handler: TaskHandler


class PluginContext:
    """插件注册时拿到的依赖入口，收集它向各扩展点提交的内容。"""

    def __init__(self, state: AppState) -> None:
        self.state = state
        self.cronjobs: list[CronjobContribution] = []
        self.upstream_hooks: list[UpstreamHook] = []

    def add_cronjob(self, spec: CronjobSpec, handler: TaskHandler) -> None:
        """追加一个计划任务。"""
        self.cronjobs.append(CronjobContribution(spec=spec, handler=handler))

    def add_upstream_hook(self, hook: UpstreamHook) -> None:
        """登记出站请求钩子：可改写请求，也可为渠道提供鉴权。"""
        self.upstream_hooks.append(hook)


@dataclass(frozen=True, slots=True)
class PluginDefinition:
    """一个可注册插件：清单加注册函数。"""

    manifest: PluginManifest
    register: Callable[[PluginContext], None]
