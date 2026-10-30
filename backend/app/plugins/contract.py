"""插件契约：清单、注册上下文、各扩展点协议与请求期数据。

插件只依赖本模块；网关通过 `runtime` 调用扩展点，不关心插件怎么实现。
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping, Sequence
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Any, Protocol

from ..core.errors import LensError
from ..models.channels import ChannelConfig
from ..persistence.cronjob_store import CronjobSpec

if TYPE_CHECKING:
    from ..gateway.service.app_state import AppState
    from .stats import PluginStats

PLUGIN_API_VERSION = 1

TaskHandler = Callable[[], Awaitable[None]]
Disposer = Callable[[], Awaitable[None] | None]

# 扩展点标识。插件通过这些标识声明自己挂在哪里。
EXT_REQUEST_REWRITE = "request_rewrite"  # 路由前改写或拒绝请求
EXT_UPSTREAM_REQUEST = "upstream_request"  # 改写即将发出的请求
EXT_UPSTREAM_CREDENTIAL = "upstream_credential"  # 为渠道签发凭据
EXT_UPSTREAM_RESPONSE = "upstream_response"  # 改写非流式回复
EXT_RESPONSE_EVENT = "response_event"  # 改写或丢弃流式回复的单个事件
EXT_REQUEST_OBSERVER = "request_observer"  # 只读观察已完成的请求
EXT_MODEL_CATALOG = "model_catalog"  # 为渠道补充模型
EXT_ROUTE_STRATEGY = "route_strategy"  # 决定同优先级候选的尝试顺序

SETTING_TYPE_BOOL = "bool"
SETTING_TYPE_INT = "int"
SETTING_TYPE_FLOAT = "float"
SETTING_TYPE_STRING = "string"
SETTING_TYPE_ENUM = "enum"
SETTING_TYPES = frozenset(
    {
        SETTING_TYPE_BOOL,
        SETTING_TYPE_INT,
        SETTING_TYPE_FLOAT,
        SETTING_TYPE_STRING,
        SETTING_TYPE_ENUM,
    }
)


@dataclass(frozen=True, slots=True)
class PluginSetting:
    """插件声明的一项设置，用于生成设置表单。"""

    key: str
    label: str
    type: str = SETTING_TYPE_STRING
    default: str | int | float | bool = ""
    description: str = ""
    options: tuple[str, ...] = ()
    min_value: int | float | None = None
    max_value: int | float | None = None
    # 密钥：管理端不回显值，只显示是否已设置。
    secret: bool = False


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
class InboundRequest:
    """客户端请求的只读事实。不含请求头、密钥与来源地址。"""

    # ProtocolKind 的值。
    protocol: str
    path: str
    model: str
    is_stream: bool
    user_agent: str = ""


class HookContext:
    """一次请求里传给某个插件钩子的上下文。

    `state` 是该插件在这次请求里的私有字典，同一插件的各个钩子共享它。
    """

    __slots__ = ("request", "state")

    def __init__(self, request: InboundRequest, state: dict[str, Any]) -> None:
        self.request = request
        self.state = state


class PluginRejection(LensError):
    """插件拒绝请求；客户端按其协议收到这个状态码与消息。"""

    def __init__(
        self, status_code: int = 403, message: str = "Rejected by a plugin"
    ) -> None:
        code = status_code if isinstance(status_code, int) else 403
        super().__init__(
            str(message) or "Rejected by a plugin",
            status_code=code if 400 <= code <= 599 else 403,
            error_type="plugin_rejected",
        )


@dataclass(frozen=True, slots=True)
class UpstreamCall:
    """一次即将发往上游的请求，插件可读可改。"""

    channel: ChannelConfig
    protocol: str
    url: str
    headers: dict[str, str]
    body: dict[str, Any]
    credential_id: str | None = None
    model_name: str | None = None


@dataclass(frozen=True, slots=True)
class UpstreamResponse:
    """非流式回复，已转换成客户端协议；状态码只读。"""

    channel: ChannelConfig
    # 客户端协议（ProtocolKind 的值）。
    protocol: str
    status_code: int
    headers: dict[str, str]
    content: bytes


class StreamEventAction(Enum):
    DROP = "drop"


# `ResponseEventHook.rewrite` 返回它表示丢弃这个事件。
DROP_EVENT = StreamEventAction.DROP


@dataclass(frozen=True, slots=True)
class ResponseEvent:
    """流式回复里的一个 SSE 事件；data 是唯一一行 JSON 对象。"""

    # `event:` 行的名字；Chat 与 Gemini 流没有这一行，为 ""。
    name: str
    data: dict[str, Any]


@dataclass(frozen=True, slots=True)
class RequestRecord:
    """一次已完成请求的只读摘要。只含白名单字段：没有请求体、提示词或错误原文。"""

    channel_id: str
    channel_name: str
    protocol: str
    model: str
    status_code: int
    success: bool
    is_stream: bool
    latency_ms: int
    total_tokens: int
    finished_at: str = ""  # UTC ISO 8601
    lifecycle_status: str = ""
    requested_model: str = ""
    resolved_group_name: str = ""
    credential_id: str = ""
    gateway_key_id: str = ""
    first_token_latency_ms: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_input_tokens: int = 0
    cache_write_input_tokens: int = 0
    total_cost_usd: float = 0.0
    attempt_count: int = 0
    # 没有任何上游尝试就失败（例如被插件拒绝）。
    is_rejected: bool = False


@dataclass(frozen=True, slots=True)
class CatalogEntry:
    """插件为渠道补充的一个模型。"""

    model_name: str
    enabled: bool = True


@dataclass(frozen=True, slots=True)
class RouteSeat:
    """路由策略看到的一个候选，只读。"""

    channel_id: str
    channel_name: str
    credential_id: str | None
    credential_name: str
    model_name: str | None
    rate_multiplier: float | None
    context_window: int | None
    health_score: float


class RequestRewriteHook(Protocol):
    """路由前改写请求，可改模型、流式与工具；抛 `PluginRejection` 拒绝。"""

    def extension(self) -> str: ...

    async def rewrite(
        self, body: dict[str, Any], ctx: HookContext
    ) -> dict[str, Any] | None: ...


class UpstreamHook(Protocol):
    """出站请求扩展点：改写请求，或接手渠道鉴权。返回 None 表示不改。"""

    def extension(self) -> str: ...

    def matches(self, call: UpstreamCall) -> bool: ...

    async def apply(
        self, call: UpstreamCall, ctx: HookContext
    ) -> UpstreamCall | None: ...


class ResponseHook(Protocol):
    """非流式回复扩展点：改写回复内容与响应头。返回 None 表示不改。"""

    def extension(self) -> str: ...

    def matches(self, response: UpstreamResponse) -> bool: ...

    async def apply(
        self, response: UpstreamResponse, ctx: HookContext
    ) -> UpstreamResponse | None: ...


class ResponseEventHook(Protocol):
    """流式回复扩展点：替换事件数据（返回 dict）、丢弃（`DROP_EVENT`）或不改（None）。

    可选：`events` 属性，只接收列出的事件名；空元组表示不接收。
    """

    def extension(self) -> str: ...

    async def rewrite(
        self, event: ResponseEvent, ctx: HookContext
    ) -> dict[str, Any] | StreamEventAction | None: ...


class RequestObserver(Protocol):
    """请求观察者：只读，不能改变请求或响应。"""

    def extension(self) -> str: ...

    async def completed(self, record: RequestRecord) -> None: ...


class ModelCatalogHook(Protocol):
    """模型目录扩展点：为渠道补充平台未发现的模型。"""

    def extension(self) -> str: ...

    def matches(self, channel: ChannelConfig) -> bool: ...

    async def models(self, channel: ChannelConfig) -> Sequence[CatalogEntry]: ...


class RouteStrategy(Protocol):
    """路由策略：只决定同优先级候选的尝试顺序，返回下标的一个排列。

    `name` 需匹配 ^[A-Za-z0-9][A-Za-z0-9._-]*$；
    模型组用 `<插件 id>/<name>` 选中它。
    `order` 在路由锁内同步调用：必须很快（超过 20 ms 按原顺序），且不能回调
    路由器，否则会死锁。最高优先级档的 `pool` 是路由键，更低优先级档是
    `<路由键>#fallback`；每个 pool 对应一组候选。
    """

    name: str

    def extension(self) -> str: ...

    def order(self, pool: str, seats: Sequence[RouteSeat]) -> Sequence[int]: ...


@dataclass(frozen=True, slots=True)
class CronjobContribution:
    """插件追加的计划任务。"""

    spec: CronjobSpec
    handler: TaskHandler


class PluginContext:
    """插件注册时拿到的依赖入口，收集它向各扩展点提交的内容。"""

    def __init__(
        self, app_state: AppState, settings: Mapping[str, Any] | None = None
    ) -> None:
        self.app_state = app_state
        # 本插件当前生效的设置值（声明默认值叠加用户保存值）。
        self.settings: dict[str, Any] = dict(settings or {})
        self.cronjobs: list[CronjobContribution] = []
        self.request_rewrite_hooks: list[RequestRewriteHook] = []
        self.upstream_hooks: list[UpstreamHook] = []
        self.response_hooks: list[ResponseHook] = []
        self.response_event_hooks: list[ResponseEventHook] = []
        self.request_observers: list[RequestObserver] = []
        self.model_catalog_hooks: list[ModelCatalogHook] = []
        self.route_strategies: list[RouteStrategy] = []
        self.disposers: list[Disposer] = []

    def add_cronjob(self, spec: CronjobSpec, handler: TaskHandler) -> None:
        """追加一个计划任务。"""
        self.cronjobs.append(CronjobContribution(spec=spec, handler=handler))

    def add_request_rewrite_hook(self, hook: RequestRewriteHook) -> None:
        self.request_rewrite_hooks.append(hook)

    def add_upstream_hook(self, hook: UpstreamHook) -> None:
        """登记出站请求钩子：改写请求，或为渠道签发凭据。"""
        self.upstream_hooks.append(hook)

    def add_response_hook(self, hook: ResponseHook) -> None:
        """登记响应钩子，改写非流式回复。"""
        self.response_hooks.append(hook)

    def add_response_event_hook(self, hook: ResponseEventHook) -> None:
        self.response_event_hooks.append(hook)

    def add_request_observer(self, observer: RequestObserver) -> None:
        """登记请求观察者；只读，异常被吞掉。"""
        self.request_observers.append(observer)

    def add_model_catalog_hook(self, hook: ModelCatalogHook) -> None:
        """登记模型目录钩子，为匹配的渠道补充模型。"""
        self.model_catalog_hooks.append(hook)

    def add_route_strategy(self, strategy: RouteStrategy) -> None:
        self.route_strategies.append(strategy)

    def on_dispose(self, disposer: Disposer) -> None:
        """插件停用、设置变化或重新加载时调用，按登记的逆序执行。"""
        self.disposers.append(disposer)


@dataclass(frozen=True, slots=True)
class PluginDefinition:
    """一个可注册插件：清单加注册函数。"""

    manifest: PluginManifest
    register: Callable[[PluginContext], None]
    # builtin：随 Lens 发布；external：用户放在插件目录里。
    source: str = "builtin"
    path: str = ""


@dataclass(frozen=True, slots=True)
class PluginHook[HookT]:
    """一个扩展点实现及其所属插件。"""

    plugin_id: str
    hook: HookT


class RecordSink(Protocol):
    """把已完成请求的摘要交给观察者；不阻塞请求。"""

    def submit(
        self,
        record: RequestRecord,
        observers: Sequence[PluginHook[RequestObserver]],
    ) -> None: ...


@dataclass(frozen=True, slots=True)
class PluginHookSet:
    """某一时刻生效的全部扩展点，按插件注册顺序排列。

    每个请求开始时取一份快照；插件重载不影响进行中的请求。
    """

    stats: PluginStats
    record_sink: RecordSink | None = None
    request_rewrite: tuple[PluginHook[RequestRewriteHook], ...] = ()
    upstream_credential: tuple[PluginHook[UpstreamHook], ...] = ()
    upstream_request: tuple[PluginHook[UpstreamHook], ...] = ()
    upstream_response: tuple[PluginHook[ResponseHook], ...] = ()
    response_event: tuple[PluginHook[ResponseEventHook], ...] = ()
    request_observer: tuple[PluginHook[RequestObserver], ...] = ()
    model_catalog: tuple[PluginHook[ModelCatalogHook], ...] = ()
    # `<插件 id>/<name>` -> 策略。
    route_strategies: Mapping[str, PluginHook[RouteStrategy]] = field(
        default_factory=dict
    )
