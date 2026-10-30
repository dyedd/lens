from __future__ import annotations

import asyncio
import inspect
import json
import math
import re
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from ..core.errors import LensError, ResourceNotFoundError
from ..models.model_groups import MODEL_GROUP_STRATEGY_MAX_LENGTH
from ..models.plugins import (
    PluginCronjobView,
    PluginSettingView,
    PluginState,
    PluginView,
)
from ..models.settings import SettingItem
from ..persistence.cronjob_store import CronjobSpec
from ..persistence.settings_keys import (
    SETTING_PLUGINS_CONFIG,
    SETTING_PLUGINS_DISABLED,
)
from .contract import (
    EXT_MODEL_CATALOG,
    EXT_REQUEST_OBSERVER,
    EXT_REQUEST_REWRITE,
    EXT_RESPONSE_EVENT,
    EXT_ROUTE_STRATEGY,
    EXT_UPSTREAM_CREDENTIAL,
    EXT_UPSTREAM_REQUEST,
    EXT_UPSTREAM_RESPONSE,
    PLUGIN_API_VERSION,
    SETTING_TYPE_BOOL,
    SETTING_TYPE_ENUM,
    SETTING_TYPE_FLOAT,
    SETTING_TYPE_INT,
    SETTING_TYPE_STRING,
    SETTING_TYPES,
    PluginContext,
    PluginDefinition,
    PluginHook,
    PluginHookSet,
    PluginManifest,
    PluginSetting,
    RecordSink,
    RouteStrategy,
    TaskHandler,
    UpstreamHook,
)
from .discovery import PluginLoadFailure

if TYPE_CHECKING:
    import logging

    from ..gateway.service.app_state import AppState
    from .stats import PluginStats

_PLUGIN_ID_PATTERN = re.compile(r"[a-z0-9][a-z0-9_]{0,63}")
_STRATEGY_NAME_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*")
# 卸载回调有问题时不能卡住重载与停机。
_DISPOSE_TIMEOUT_SECONDS = 10.0


class PluginSettingsError(LensError):
    """插件设置的键或值不被插件声明的 schema 接受。"""

    def __init__(self, message: str) -> None:
        super().__init__(message, status_code=400, error_type="invalid_plugin_setting")


@dataclass(frozen=True, slots=True)
class _Registration:
    """一次成功注册的结果；设置或依赖变化时整体替换。"""

    context: PluginContext
    settings: dict[str, Any]
    upstream_credential: tuple[UpstreamHook, ...]
    upstream_request: tuple[UpstreamHook, ...]
    # name -> 策略；同名时插件里最后登记的生效。
    strategies: dict[str, RouteStrategy]


@dataclass(slots=True)
class _PluginEntry:
    definition: PluginDefinition
    state: PluginState
    error: str = ""
    registration: _Registration | None = None


class PluginRegistry:
    """组合已注册插件，按启用状态与依赖决定哪些扩展点生效。

    单个插件失败只影响自己；依赖未满足的插件进入 pending。
    变更在一把锁里串行执行；没有变化的插件保留原来的注册。
    """

    def __init__(
        self,
        definitions: Sequence[PluginDefinition | PluginLoadFailure],
        *,
        state: AppState,
        stats: PluginStats,
        record_sink: RecordSink,
        logger: logging.Logger,
        reserved_cronjob_ids: frozenset[str] = frozenset(),
    ) -> None:
        self._definitions = list(definitions)
        # 平台自身计划任务的 id；插件的同名任务被跳过，不顶替平台的处理函数。
        self._reserved_cronjob_ids = reserved_cronjob_ids
        self._state = state
        self._stats = stats
        self._record_sink = record_sink
        self._logger = logger
        self._lock = asyncio.Lock()
        self._disabled_ids: set[str] = set()
        self._config: dict[str, dict[str, Any]] = {}
        self._entries: dict[str, _PluginEntry] = {}
        # 生效插件的注册顺序：依赖在前；同一轮内按定义顺序（内置在前，外部在后）。
        self._order: list[str] = []
        self._hook_set = PluginHookSet(stats=stats, record_sink=record_sink)
        self._cronjob_specs: tuple[CronjobSpec, ...] = ()
        self._cronjob_handlers: dict[str, TaskHandler] = {}

    # --- 读取 ---

    def hook_set(self) -> PluginHookSet:
        return self._hook_set

    def views(self) -> list[PluginView]:
        return [self._view(entry) for entry in self._entries.values()]

    def strategy_ids(self) -> list[str]:
        return list(self._hook_set.route_strategies)

    def cronjob_specs(self) -> tuple[CronjobSpec, ...]:
        return self._cronjob_specs

    def cronjob_handlers(self) -> dict[str, TaskHandler]:
        return dict(self._cronjob_handlers)

    # --- 变更 ---

    async def load(
        self, definitions: Sequence[PluginDefinition | PluginLoadFailure] | None = None
    ) -> None:
        """读取持久化的停用清单与设置（可同时替换插件定义），重建生效插件。"""
        async with self._lock:
            items = await self._state.settings_repo.list_settings()
            values = {item.key: item.value for item in items}
            self._disabled_ids = _parse_disabled_ids(
                values.get(SETTING_PLUGINS_DISABLED, ""), logger=self._logger
            )
            self._config = _parse_config(values.get(SETTING_PLUGINS_CONFIG, ""))
            if definitions is not None:
                self._definitions = list(definitions)
            await self._reconcile()

    async def reload(
        self, definitions: Sequence[PluginDefinition | PluginLoadFailure]
    ) -> None:
        """替换插件定义（如用户新增/修改插件文件后）并重建。"""
        async with self._lock:
            self._definitions = list(definitions)
            await self._reconcile()

    async def set_enabled(self, plugin_id: str, *, enabled: bool) -> PluginView:
        async with self._lock:
            if plugin_id not in self._entries:
                raise ResourceNotFoundError(plugin_id)
            disabled_ids = set(self._disabled_ids)
            if enabled:
                disabled_ids.discard(plugin_id)
            else:
                disabled_ids.add(plugin_id)
            await self._persist(
                SettingItem(
                    key=SETTING_PLUGINS_DISABLED,
                    value=_dump_disabled_ids(disabled_ids),
                )
            )
            self._disabled_ids = disabled_ids
            await self._reconcile()
            return self._view(self._entries[plugin_id])

    async def set_settings(
        self, plugin_id: str, values: Mapping[str, Any]
    ) -> PluginView:
        """校验并保存插件设置；null 恢复默认值，密钥传 "" 保持原值。"""
        async with self._lock:
            entry = self._entries.get(plugin_id)
            if entry is None:
                raise ResourceNotFoundError(plugin_id)
            declared = entry.definition.manifest.settings
            if schema_error := _find_schema_error(declared):
                raise PluginSettingsError(schema_error)
            schema = {setting.key: setting for setting in declared}
            if not schema:
                raise PluginSettingsError("该插件没有声明任何设置")
            current = dict(self._config.get(plugin_id, {}))
            for key, raw_value in values.items():
                setting = schema.get(key)
                if setting is None:
                    raise PluginSettingsError(f"未知设置项：{key}")
                if raw_value is None:
                    current.pop(key, None)
                elif setting.secret and raw_value == "":
                    continue
                else:
                    current[key] = _coerce_setting(setting, raw_value)
            config = {**self._config, plugin_id: current}
            await self._persist(
                SettingItem(
                    key=SETTING_PLUGINS_CONFIG,
                    value=json.dumps(config, ensure_ascii=False),
                )
            )
            self._config = config
            await self._reconcile()
            return self._view(self._entries[plugin_id])

    async def aclose(self) -> None:
        """停用全部插件：依赖方先于被依赖方卸载。"""
        async with self._lock:
            for plugin_id in reversed(self._order):
                registration = self._entries[plugin_id].registration
                if registration is not None:
                    await self._dispose(plugin_id, registration.context)
            self._publish({}, [])

    async def _persist(self, item: SettingItem) -> None:
        await self._state.settings_repo.upsert_settings([item])

    # --- 组合 ---

    async def _reconcile(self) -> None:
        previous, previous_order = self._entries, self._order
        entries = self._build_entries()
        going = self._find_going(previous, previous_order, entries)
        kept_order = [pid for pid in previous_order if pid not in going]
        for plugin_id in kept_order:
            entries[plugin_id].registration = previous[plugin_id].registration
            entries[plugin_id].state = PluginState.ACTIVE
        if going:
            # 先撤下要卸载的插件，新请求不再拿到它们，再等它们的卸载回调。
            self._publish(entries, kept_order)
            for plugin_id in reversed(previous_order):
                registration = previous[plugin_id].registration
                if plugin_id in going and registration is not None:
                    await self._dispose(plugin_id, registration.context)
        order = await self._place(entries)
        self._publish(entries, order)

    def _build_entries(self) -> dict[str, _PluginEntry]:
        entries: dict[str, _PluginEntry] = {}
        for item in self._definitions:
            definition = (
                _build_failed_definition(item)
                if isinstance(item, PluginLoadFailure)
                else item
            )
            manifest = definition.manifest
            if manifest.id in entries:
                self._logger.error("Duplicate plugin id ignored: %s", manifest.id)
                continue
            entry = _PluginEntry(definition=definition, state=PluginState.PENDING)
            entries[manifest.id] = entry
            if isinstance(item, PluginLoadFailure):
                entry.state = PluginState.FAILED
                entry.error = item.error
            elif not _PLUGIN_ID_PATTERN.fullmatch(manifest.id):
                entry.state = PluginState.FAILED
                entry.error = f"插件标识不合法：{manifest.id}"
            elif manifest.api_version != PLUGIN_API_VERSION:
                entry.state = PluginState.FAILED
                entry.error = (
                    f"插件 API 版本不兼容：需要 {PLUGIN_API_VERSION}，"
                    f"实际 {manifest.api_version}"
                )
            elif schema_error := _find_schema_error(manifest.settings):
                entry.state = PluginState.FAILED
                entry.error = schema_error
            elif manifest.id in self._disabled_ids:
                entry.state = PluginState.DISABLED
        return entries

    def _find_going(
        self,
        previous: Mapping[str, _PluginEntry],
        previous_order: Sequence[str],
        entries: Mapping[str, _PluginEntry],
    ) -> set[str]:
        """找出需要卸载的生效插件：定义、设置或所依赖的插件变了，或不再需要。"""
        going: set[str] = set()
        # 依赖总排在依赖方之前，一次正序遍历即可传递。
        for plugin_id in previous_order:
            registration = previous[plugin_id].registration
            entry = entries.get(plugin_id)
            if (
                registration is None
                or entry is None
                or entry.state is not PluginState.PENDING
                or entry.definition is not previous[plugin_id].definition
                or self._resolve_settings(entry.definition.manifest)
                != registration.settings
                or any(r in going for r in entry.definition.manifest.requires)
            ):
                going.add(plugin_id)
        return going

    async def _place(self, entries: Mapping[str, _PluginEntry]) -> list[str]:
        """按依赖顺序注册等待中的插件，返回生效插件的顺序。"""
        order: list[str] = []
        placed: set[str] = set()
        progressed = True
        while progressed:
            progressed = False
            for plugin_id, entry in entries.items():
                if plugin_id in placed or entry.state not in (
                    PluginState.PENDING,
                    PluginState.ACTIVE,
                ):
                    continue
                requires = entry.definition.manifest.requires
                missing = [r for r in requires if r not in entries]
                if missing:
                    entry.state = PluginState.FAILED
                    entry.error = f"依赖的插件不存在：{'、'.join(missing)}"
                    continue
                if any(r not in placed for r in requires):
                    continue
                if entry.registration is None and not await self._register(entry):
                    continue
                entry.state = PluginState.ACTIVE
                entry.error = ""
                order.append(plugin_id)
                placed.add(plugin_id)
                progressed = True
        for entry in entries.values():
            if entry.state is PluginState.PENDING:
                unresolved = [
                    r for r in entry.definition.manifest.requires if r not in placed
                ]
                entry.error = f"等待依赖：{'、'.join(unresolved)}"
        return order

    async def _register(self, entry: _PluginEntry) -> bool:
        manifest = entry.definition.manifest
        settings = self._resolve_settings(manifest, should_warn=True)
        context = PluginContext(self._state, settings=settings)
        try:
            entry.definition.register(context)
            registration = self._build_registration(manifest.id, context, settings)
        except Exception as exc:
            self._logger.exception("Plugin registration failed: %s", manifest.id)
            await self._dispose(manifest.id, context)
            entry.state = PluginState.FAILED
            entry.error = str(exc) or exc.__class__.__name__
            return False
        entry.registration = registration
        return True

    def _build_registration(
        self, plugin_id: str, context: PluginContext, settings: dict[str, Any]
    ) -> _Registration:
        credential: list[UpstreamHook] = []
        request: list[UpstreamHook] = []
        for hook in context.upstream_hooks:
            if hook.extension() == EXT_UPSTREAM_CREDENTIAL:
                credential.append(hook)
            else:
                request.append(hook)
        strategies: dict[str, RouteStrategy] = {}
        for strategy in context.route_strategies:
            name = getattr(strategy, "name", None)
            if reason := _find_strategy_name_error(plugin_id, name):
                # 原因记进 stats（stats 会写日志），作者能在插件页看到策略为何缺席。
                self._stats.record(
                    plugin_id,
                    EXT_ROUTE_STRATEGY,
                    outcome="invalid",
                    elapsed_ms=0,
                    error=ValueError(reason),
                )
                continue
            strategies[name] = strategy
        return _Registration(
            context=context,
            settings=settings,
            upstream_credential=tuple(credential),
            upstream_request=tuple(request),
            strategies=strategies,
        )

    async def _dispose(self, plugin_id: str, context: PluginContext) -> None:
        """按登记的逆序调用卸载回调；单个失败只记录，其余照常执行。"""
        disposers, context.disposers = list(context.disposers), []
        for disposer in reversed(disposers):
            try:
                outcome = disposer()
                if inspect.isawaitable(outcome):
                    async with asyncio.timeout(_DISPOSE_TIMEOUT_SECONDS):
                        await outcome
            except Exception:
                self._logger.exception("Plugin dispose failed: %s", plugin_id)

    def _resolve_settings(
        self, manifest: PluginManifest, *, should_warn: bool = False
    ) -> dict[str, Any]:
        """声明默认值叠加已保存的值；保存值不合法时用默认值。"""
        stored = self._config.get(manifest.id, {})
        resolved: dict[str, Any] = {}
        for setting in manifest.settings:
            if setting.key in stored:
                try:
                    resolved[setting.key] = _coerce_setting(
                        setting, stored[setting.key]
                    )
                    continue
                except PluginSettingsError:
                    if should_warn:
                        self._logger.warning(
                            "Ignoring invalid stored setting %s.%s",
                            manifest.id,
                            setting.key,
                        )
            resolved[setting.key] = _default_value(setting)
        return resolved

    def _publish(self, entries: dict[str, _PluginEntry], order: list[str]) -> None:
        """换上新的插件状态与扩展点快照；进行中的请求继续用旧快照。"""
        active = [
            (plugin_id, registration)
            for plugin_id in order
            if (registration := entries[plugin_id].registration) is not None
        ]
        self._entries = entries
        self._order = order
        self._hook_set = _build_hook_set(active, self._stats, self._record_sink)
        self._cronjob_specs, self._cronjob_handlers = self._compose_cronjobs(active)

    def _compose_cronjobs(
        self, active: Sequence[tuple[str, _Registration]]
    ) -> tuple[tuple[CronjobSpec, ...], dict[str, TaskHandler]]:
        specs: list[CronjobSpec] = []
        handlers: dict[str, TaskHandler] = {}
        for plugin_id, registration in active:
            for contribution in registration.context.cronjobs:
                cronjob_id = contribution.spec.id
                if cronjob_id in self._reserved_cronjob_ids or cronjob_id in handlers:
                    self._logger.error(
                        "Duplicate cronjob id ignored: %s (%s)", cronjob_id, plugin_id
                    )
                    continue
                specs.append(contribution.spec)
                handlers[contribution.spec.id] = contribution.handler
        return tuple(specs), handlers

    def _view(self, entry: _PluginEntry) -> PluginView:
        manifest = entry.definition.manifest
        registration = entry.registration
        stored = self._config.get(manifest.id, {})
        # 设置声明本身不合法时不生成表单，原因见 error。
        declared = () if _find_schema_error(manifest.settings) else manifest.settings
        resolved = self._resolve_settings(manifest) if declared else {}
        settings_views = [
            PluginSettingView(
                key=s.key,
                label=s.label,
                type=s.type,
                description=s.description,
                options=list(s.options),
                min_value=s.min_value,
                max_value=s.max_value,
                secret=s.secret,
                is_set=_is_setting_stored(s, stored),
                # 密钥只说明是否已设置，从不回显。
                value="" if s.secret else resolved[s.key],
            )
            for s in declared
        ]
        cronjobs: list[PluginCronjobView] = []
        strategies: list[str] = []
        if registration is not None:
            cronjobs = [
                PluginCronjobView(id=item.spec.id, name=item.spec.name)
                for item in registration.context.cronjobs
                if item.spec.id not in self._reserved_cronjob_ids
            ]
            strategies = [f"{manifest.id}/{name}" for name in registration.strategies]
        return PluginView(
            id=manifest.id,
            name=manifest.name,
            description=manifest.description,
            version=manifest.version,
            author=manifest.author,
            homepage=manifest.homepage,
            source=entry.definition.source,
            state=entry.state,
            error=entry.error,
            requires=list(manifest.requires),
            extensions=_list_extensions(registration),
            settings=settings_views,
            cronjobs=cronjobs,
            strategies=strategies,
            stats=self._stats.views(manifest.id),
        )


def _build_failed_definition(failure: PluginLoadFailure) -> PluginDefinition:
    """为加载失败的插件生成占位定义，让它带着原因出现在插件列表里。"""

    def register(_: PluginContext) -> None:
        raise RuntimeError(failure.error)

    return PluginDefinition(
        manifest=PluginManifest(
            id=failure.plugin_id, name=failure.plugin_id, version=""
        ),
        register=register,
        source="external",
        path=failure.path,
    )


def _is_valid_name(name: object, pattern: re.Pattern[str]) -> bool:
    return isinstance(name, str) and pattern.fullmatch(name) is not None


def _find_strategy_name_error(plugin_id: str, name: object) -> str:
    """返回策略被忽略的原因；合法时为空。"""
    if not _is_valid_name(name, _STRATEGY_NAME_PATTERN):
        return f"路由策略名不合法，已忽略：{name!r}"
    strategy_id = f"{plugin_id}/{name}"
    if len(strategy_id) > MODEL_GROUP_STRATEGY_MAX_LENGTH:
        return (
            f"路由策略标识超过 {MODEL_GROUP_STRATEGY_MAX_LENGTH} 个字符，"
            f"已忽略：{strategy_id}"
        )
    return ""


def _list_extensions(registration: _Registration | None) -> list[str]:
    if registration is None:
        return []
    context = registration.context
    contributions: dict[str, Sequence[object]] = {
        EXT_REQUEST_REWRITE: context.request_rewrite_hooks,
        EXT_UPSTREAM_CREDENTIAL: registration.upstream_credential,
        EXT_UPSTREAM_REQUEST: registration.upstream_request,
        EXT_UPSTREAM_RESPONSE: context.response_hooks,
        EXT_RESPONSE_EVENT: context.response_event_hooks,
        EXT_REQUEST_OBSERVER: context.request_observers,
        EXT_MODEL_CATALOG: context.model_catalog_hooks,
        EXT_ROUTE_STRATEGY: tuple(registration.strategies.values()),
    }
    return sorted(extension for extension, items in contributions.items() if items)


def _build_hook_set(
    active: Sequence[tuple[str, _Registration]],
    stats: PluginStats,
    record_sink: RecordSink,
) -> PluginHookSet:
    def collect[HookT](
        select: Callable[[_Registration], Iterable[HookT]],
    ) -> tuple[PluginHook[HookT], ...]:
        return tuple(
            PluginHook(plugin_id=plugin_id, hook=hook)
            for plugin_id, registration in active
            for hook in select(registration)
        )

    return PluginHookSet(
        stats=stats,
        record_sink=record_sink,
        request_rewrite=collect(lambda r: r.context.request_rewrite_hooks),
        upstream_credential=collect(lambda r: r.upstream_credential),
        upstream_request=collect(lambda r: r.upstream_request),
        upstream_response=collect(lambda r: r.context.response_hooks),
        response_event=collect(lambda r: r.context.response_event_hooks),
        request_observer=collect(lambda r: r.context.request_observers),
        model_catalog=collect(lambda r: r.context.model_catalog_hooks),
        route_strategies={
            f"{plugin_id}/{name}": PluginHook(plugin_id=plugin_id, hook=strategy)
            for plugin_id, registration in active
            for name, strategy in registration.strategies.items()
        },
    )


def _find_schema_error(settings: Sequence[PluginSetting]) -> str:
    """检查插件声明的设置；返回第一个问题，没有问题时为空。"""
    keys: set[str] = set()
    for setting in settings:
        if not isinstance(setting, PluginSetting):
            return f"设置声明不合法：{setting!r}"
        if not isinstance(setting.key, str) or not setting.key or setting.key in keys:
            return f"设置项键名为空或重复：{setting.key!r}"
        keys.add(setting.key)
        if setting.type not in SETTING_TYPES:
            return f"设置项 {setting.key} 的类型不受支持：{setting.type}"
        if setting.secret and setting.type != SETTING_TYPE_STRING:
            return f"设置项 {setting.key} 只有字符串类型可以设为密钥"
        bounds = (setting.min_value, setting.max_value)
        if any(bound is not None for bound in bounds) and (
            setting.type not in (SETTING_TYPE_INT, SETTING_TYPE_FLOAT)
            or not all(bound is None or _is_number(bound) for bound in bounds)
        ):
            return f"设置项 {setting.key} 的取值范围只能用于数值类型"
        try:
            _coerce_setting(setting, setting.default)
        except PluginSettingsError as exc:
            return f"设置项 {setting.key} 的默认值不合法：{exc.public_message}"
    return ""


def _default_value(setting: PluginSetting) -> Any:
    try:
        return _coerce_setting(setting, setting.default)
    except PluginSettingsError:
        # 默认值不合法的插件已标为 failed；这里只为展示。
        return setting.default


def _coerce_setting(setting: PluginSetting, raw: Any) -> Any:
    if setting.type == SETTING_TYPE_BOOL:
        if isinstance(raw, bool):
            return raw
        if isinstance(raw, str) and raw.strip().lower() in {"1", "true", "yes", "on"}:
            return True
        if isinstance(raw, str) and raw.strip().lower() in {"0", "false", "no", "off"}:
            return False
        raise PluginSettingsError(f"{setting.key} 需要布尔值")
    if setting.type in (SETTING_TYPE_INT, SETTING_TYPE_FLOAT):
        return _coerce_number(setting, raw)
    if setting.type not in (SETTING_TYPE_STRING, SETTING_TYPE_ENUM):
        raise PluginSettingsError(f"{setting.key} 的类型不受支持：{setting.type}")
    if isinstance(raw, bool) or not isinstance(raw, str | int | float):
        raise PluginSettingsError(f"{setting.key} 需要字符串")
    text = str(raw)
    if (
        setting.type == SETTING_TYPE_ENUM
        and setting.options
        and text not in setting.options
    ):
        raise PluginSettingsError(f"{setting.key} 只能是 {'、'.join(setting.options)}")
    return text


def _coerce_number(setting: PluginSetting, raw: Any) -> int | float:
    is_int = setting.type == SETTING_TYPE_INT
    label = "整数" if is_int else "数字"
    if isinstance(raw, bool) or not isinstance(raw, int | float | str):
        raise PluginSettingsError(f"{setting.key} 需要{label}")
    try:
        number = float(raw)
    except (OverflowError, ValueError) as exc:
        raise PluginSettingsError(f"{setting.key} 需要{label}") from exc
    if not math.isfinite(number) or (is_int and not number.is_integer()):
        raise PluginSettingsError(f"{setting.key} 需要{label}")
    if not is_int:
        value: int | float = number
    elif isinstance(raw, int):
        value = raw
    else:
        value = int(number)
    if _is_number(setting.min_value) and value < setting.min_value:
        raise PluginSettingsError(f"{setting.key} 不能小于 {setting.min_value}")
    if _is_number(setting.max_value) and value > setting.max_value:
        raise PluginSettingsError(f"{setting.key} 不能大于 {setting.max_value}")
    return value


def _is_number(value: object) -> bool:
    return isinstance(value, int | float) and not isinstance(value, bool)


def _is_setting_stored(setting: PluginSetting, stored: Mapping[str, Any]) -> bool:
    """是否已保存一个合法且非空的值。"""
    if setting.key not in stored:
        return False
    try:
        return _coerce_setting(setting, stored[setting.key]) != ""
    except PluginSettingsError:
        return False


def _parse_disabled_ids(raw_value: str, *, logger: logging.Logger) -> set[str]:
    if not raw_value.strip():
        return set()
    try:
        parsed = json.loads(raw_value)
    except ValueError:
        logger.warning("Ignoring unreadable plugin state: %s", raw_value)
        return set()
    if not isinstance(parsed, list):
        logger.warning("Ignoring plugin state that is not a list")
        return set()
    return {value for value in parsed if isinstance(value, str)}


def _dump_disabled_ids(plugin_ids: Iterable[str]) -> str:
    return json.dumps(sorted(plugin_ids), ensure_ascii=False)


def _parse_config(raw_value: str) -> dict[str, dict[str, Any]]:
    if not raw_value.strip():
        return {}
    try:
        parsed = json.loads(raw_value)
    except ValueError:
        return {}
    if not isinstance(parsed, dict):
        return {}
    config: dict[str, dict[str, Any]] = {}
    for plugin_id, values in parsed.items():
        if isinstance(plugin_id, str) and isinstance(values, dict):
            config[plugin_id] = dict(values)
    return config
