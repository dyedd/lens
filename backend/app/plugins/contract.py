from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Protocol

from ..models.channels import ChannelConfig
from ..persistence.cronjob_store import CronjobSpec

if TYPE_CHECKING:
    from ..gateway.service.app_state import AppState

PLUGIN_API_VERSION = 1

TaskHandler = Callable[[], Awaitable[None]]

# 扩展点标识。插件通过这些标识声明自己挂在哪里。
EXT_UPSTREAM_REQUEST = "upstream_request"  # 改写即将发出的请求
EXT_UPSTREAM_CREDENTIAL = "upstream_credential"  # 为渠道签发凭据
EXT_UPSTREAM_RESPONSE = "upstream_response"  # 改写上游返回的响应
EXT_REQUEST_OBSERVER = "request_observer"  # 只读观察已完成的请求
EXT_MODEL_CATALOG = "model_catalog"  # 为渠道补充模型

SETTING_TYPE_BOOL = "bool"
SETTING_TYPE_INT = "int"
SETTING_TYPE_STRING = "string"
SETTING_TYPE_ENUM = "enum"
SETTING_TYPES = frozenset(
    {SETTING_TYPE_BOOL, SETTING_TYPE_INT, SETTING_TYPE_STRING, SETTING_TYPE_ENUM}
)


@dataclass(frozen=True, slots=True)
class PluginSetting:
    """插件声明的一项设置，用于生成设置表单。"""

    key: str
    label: str
    type: str = SETTING_TYPE_STRING
    default: str | int | bool = ""
    description: str = ""
    options: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class PluginManifest:
    """插件身份、作者、依赖、设置与兼容性声明。"""

    id: str
    name: str
    description: str = ""
    version: str = "1.0.0"
    author: str = ""
    homepage: str = ""
    # 本插件依赖的其他插件 id；依赖未启用时本插件进入 pending。
    requires: tuple[str, ...] = ()
    settings: tuple[PluginSetting, ...] = ()
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
class UpstreamResponse:
    """上游返回的响应（目前只覆盖非流式 JSON），插件可读可改。"""

    channel: ChannelConfig
    protocol: str
    status_code: int
    headers: dict[str, str]
    content: bytes


@dataclass(frozen=True, slots=True)
class RequestRecord:
    """一次已完成请求的只读摘要，供观察者使用。"""

    channel_id: str
    channel_name: str
    protocol: str
    model: str
    status_code: int
    success: bool
    is_stream: bool
    latency_ms: int
    total_tokens: int


@dataclass(frozen=True, slots=True)
class CatalogEntry:
    """插件为渠道补充的一个模型。"""

    model_name: str
    enabled: bool = True


class UpstreamHook(Protocol):
    """出站请求扩展点：改写请求，或接手渠道鉴权。"""

    def extension(self) -> str: ...

    def matches(self, call: UpstreamCall) -> bool: ...

    async def apply(self, call: UpstreamCall) -> UpstreamCall: ...


class ResponseHook(Protocol):
    """响应扩展点：改写上游返回的响应。"""

    def extension(self) -> str: ...

    def matches(self, response: UpstreamResponse) -> bool: ...

    async def apply(self, response: UpstreamResponse) -> UpstreamResponse: ...


class RequestObserver(Protocol):
    """请求观察者：只读，不能改变请求或响应。"""

    def extension(self) -> str: ...

    async def completed(self, record: RequestRecord) -> None: ...


class ModelCatalogHook(Protocol):
    """模型目录扩展点：为渠道补充平台未发现的模型。"""

    def extension(self) -> str: ...

    def matches(self, channel: ChannelConfig) -> bool: ...

    async def models(self, channel: ChannelConfig) -> Sequence[CatalogEntry]: ...


@dataclass(frozen=True, slots=True)
class CronjobContribution:
    """插件追加的计划任务。"""

    spec: CronjobSpec
    handler: TaskHandler


class PluginContext:
    """插件注册时拿到的依赖入口，收集它向各扩展点提交的内容。"""

    def __init__(
        self, state: AppState, settings: Mapping[str, Any] | None = None
    ) -> None:
        self.state = state
        # 本插件当前生效的设置值（声明默认值叠加用户保存值）。
        self.settings: dict[str, Any] = dict(settings or {})
        self.cronjobs: list[CronjobContribution] = []
        self.upstream_hooks: list[UpstreamHook] = []
        self.response_hooks: list[ResponseHook] = []
        self.request_observers: list[RequestObserver] = []
        self.model_catalog_hooks: list[ModelCatalogHook] = []

    def add_cronjob(self, spec: CronjobSpec, handler: TaskHandler) -> None:
        """追加一个计划任务。"""
        self.cronjobs.append(CronjobContribution(spec=spec, handler=handler))

    def add_upstream_hook(self, hook: UpstreamHook) -> None:
        """登记出站请求钩子：改写请求，或为渠道签发凭据。"""
        self.upstream_hooks.append(hook)

    def add_response_hook(self, hook: ResponseHook) -> None:
        """登记响应钩子，改写上游返回的响应。"""
        self.response_hooks.append(hook)

    def add_request_observer(self, observer: RequestObserver) -> None:
        """登记请求观察者；只读，异常被吞掉。"""
        self.request_observers.append(observer)

    def add_model_catalog_hook(self, hook: ModelCatalogHook) -> None:
        """登记模型目录钩子，为匹配的渠道补充模型。"""
        self.model_catalog_hooks.append(hook)


@dataclass(frozen=True, slots=True)
class PluginDefinition:
    """一个可注册插件：清单加注册函数。"""

    manifest: PluginManifest
    register: Callable[[PluginContext], None]
    # builtin：随 Lens 发布；external：用户放在插件目录里。
    source: str = "builtin"
    path: str = ""
