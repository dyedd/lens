from __future__ import annotations

import json
import re
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from ..core.errors import LensError, ResourceNotFoundError
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
    PLUGIN_API_VERSION,
    SETTING_TYPE_BOOL,
    SETTING_TYPE_ENUM,
    SETTING_TYPE_INT,
    SETTING_TYPES,
    ModelCatalogHook,
    PluginContext,
    PluginDefinition,
    PluginSetting,
    RequestObserver,
    ResponseHook,
    TaskHandler,
    UpstreamHook,
)

if TYPE_CHECKING:
    import logging

    from ..gateway.service.app_state import AppState

_PLUGIN_ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9_]{0,63}$")


class PluginSettingsError(LensError):
    """插件设置的键或值不被插件声明的 schema 接受。"""

    def __init__(self, message: str) -> None:
        super().__init__(message, status_code=400, error_type="invalid_plugin_setting")


@dataclass(slots=True)
class _PluginEntry:
    definition: PluginDefinition
    state: PluginState
    error: str = ""
    context: PluginContext | None = None


class PluginRegistry:
    """组合已注册插件，按启用状态与依赖决定哪些扩展点生效。

    单个插件失败只影响自己；依赖未满足的插件进入 pending。
    """

    def __init__(
        self,
        definitions: Sequence[PluginDefinition],
        *,
        state: AppState,
        logger: logging.Logger,
    ) -> None:
        self._definitions = list(definitions)
        self._state = state
        self._logger = logger
        self._disabled_ids: set[str] = set()
        self._config: dict[str, dict[str, Any]] = {}
        self._entries: dict[str, _PluginEntry] = {}
        self._cronjob_specs: tuple[CronjobSpec, ...] = ()
        self._cronjob_handlers: dict[str, TaskHandler] = {}
        self._upstream_hooks: list[UpstreamHook] = []
        self._response_hooks: list[ResponseHook] = []
        self._request_observers: list[RequestObserver] = []
        self._model_catalog_hooks: list[ModelCatalogHook] = []
        self._reconcile()

    # --- 读取 ---

    def views(self) -> list[PluginView]:
        return [self._view(entry) for entry in self._entries.values()]

    def cronjob_specs(self) -> tuple[CronjobSpec, ...]:
        return self._cronjob_specs

    def cronjob_handlers(self) -> dict[str, TaskHandler]:
        return dict(self._cronjob_handlers)

    def upstream_hooks(self) -> list[UpstreamHook]:
        return list(self._upstream_hooks)

    def response_hooks(self) -> list[ResponseHook]:
        return list(self._response_hooks)

    def request_observers(self) -> list[RequestObserver]:
        return list(self._request_observers)

    def model_catalog_hooks(self) -> list[ModelCatalogHook]:
        return list(self._model_catalog_hooks)

    # --- 变更 ---

    async def load(self) -> None:
        """读取持久化的停用清单与设置，重建生效插件。"""
        items = await self._state.settings_repo.list_settings()
        values = {item.key: item.value for item in items}
        self._disabled_ids = _parse_disabled_ids(
            values.get(SETTING_PLUGINS_DISABLED, ""), logger=self._logger
        )
        self._config = _parse_config(values.get(SETTING_PLUGINS_CONFIG, ""))
        self._reconcile()

    async def set_enabled(self, plugin_id: str, *, enabled: bool) -> PluginView:
        if plugin_id not in self._entries:
            raise ResourceNotFoundError(plugin_id)
        if enabled:
            self._disabled_ids.discard(plugin_id)
        else:
            self._disabled_ids.add(plugin_id)
        await self._persist(
            SettingItem(
                key=SETTING_PLUGINS_DISABLED,
                value=_dump_disabled_ids(self._disabled_ids),
            )
        )
        self._reconcile()
        return self._view(self._entries[plugin_id])

    async def set_settings(
        self, plugin_id: str, values: Mapping[str, Any]
    ) -> PluginView:
        """校验并保存插件设置；返回刷新后的状态。"""
        entry = self._entries.get(plugin_id)
        if entry is None:
            raise ResourceNotFoundError(plugin_id)
        schema = {
            setting.key: setting for setting in entry.definition.manifest.settings
        }
        if not schema:
            raise PluginSettingsError("该插件没有声明任何设置")
        current = dict(self._config.get(plugin_id, {}))
        for key, raw_value in values.items():
            setting = schema.get(key)
            if setting is None:
                raise PluginSettingsError(f"未知设置项：{key}")
            current[key] = _coerce_setting(setting, raw_value)
        self._config[plugin_id] = current
        await self._persist(
            SettingItem(
                key=SETTING_PLUGINS_CONFIG,
                value=json.dumps(self._config, ensure_ascii=False),
            )
        )
        self._reconcile()
        return self._view(self._entries[plugin_id])

    def reload(self, definitions: Sequence[PluginDefinition]) -> None:
        """替换插件定义（如用户新增/修改插件文件后）并重建。"""
        self._definitions = list(definitions)
        self._reconcile()

    def definitions(self) -> list[PluginDefinition]:
        return list(self._definitions)

    async def _persist(self, item: SettingItem) -> None:
        await self._state.settings_repo.upsert_settings([item])

    # --- 组合 ---

    def _reconcile(self) -> None:
        entries: dict[str, _PluginEntry] = {}
        by_id = {d.manifest.id: d for d in self._definitions}
        for definition in self._definitions:
            manifest = definition.manifest
            if manifest.id in entries:
                self._logger.error("Duplicate plugin id ignored: %s", manifest.id)
                continue
            entry = _PluginEntry(definition=definition, state=PluginState.ACTIVE)
            entries[manifest.id] = entry
            if not _PLUGIN_ID_PATTERN.match(manifest.id):
                entry.state = PluginState.FAILED
                entry.error = f"插件标识不合法：{manifest.id}"
                continue
            if manifest.api_version != PLUGIN_API_VERSION:
                entry.state = PluginState.FAILED
                entry.error = (
                    f"插件 API 版本不兼容：需要 {PLUGIN_API_VERSION}，"
                    f"实际 {manifest.api_version}"
                )
                continue
            if manifest.id in self._disabled_ids:
                entry.state = PluginState.DISABLED

        # 依赖拓扑：按依赖顺序反复激活，未满足的进入 pending。
        active: set[str] = set()
        pending = True
        while pending:
            pending = False
            for plugin_id, entry in entries.items():
                if entry.state is not PluginState.ACTIVE or plugin_id in active:
                    continue
                requires = entry.definition.manifest.requires
                missing = [r for r in requires if r not in by_id]
                if missing:
                    entry.state = PluginState.FAILED
                    entry.error = f"依赖的插件不存在：{'、'.join(missing)}"
                    pending = True
                    continue
                unmet = [r for r in requires if r not in active]
                if unmet:
                    continue
                if not self._register(entry):
                    continue
                active.add(plugin_id)
                pending = True

        for entry in entries.values():
            if entry.state is PluginState.ACTIVE and entry.context is None:
                unresolved = [
                    r for r in entry.definition.manifest.requires if r not in active
                ]
                entry.state = PluginState.PENDING
                entry.error = f"等待依赖：{'、'.join(unresolved)}"

        self._entries = entries
        self._cronjob_specs, self._cronjob_handlers = self._compose_cronjobs(entries)
        contexts = [e.context for e in entries.values() if e.context is not None]
        self._upstream_hooks = [h for c in contexts for h in c.upstream_hooks]
        self._response_hooks = [h for c in contexts for h in c.response_hooks]
        self._request_observers = [o for c in contexts for o in c.request_observers]
        self._model_catalog_hooks = [m for c in contexts for m in c.model_catalog_hooks]

    def _register(self, entry: _PluginEntry) -> bool:
        manifest = entry.definition.manifest
        settings = self._settings_for(manifest.id, manifest.settings)
        context = PluginContext(self._state, settings=settings)
        try:
            entry.definition.register(context)
        except Exception as exc:
            entry.state = PluginState.FAILED
            entry.error = str(exc) or exc.__class__.__name__
            self._logger.exception("Plugin registration failed: %s", manifest.id)
            return False
        entry.context = context
        return True

    def _settings_for(
        self, plugin_id: str, schema: Sequence[PluginSetting]
    ) -> dict[str, Any]:
        declared = {s.key: s for s in schema if s.type in SETTING_TYPES}
        stored = self._config.get(plugin_id, {})
        resolved: dict[str, Any] = {}
        for key, setting in declared.items():
            if key in stored:
                try:
                    resolved[key] = _coerce_setting(setting, stored[key])
                    continue
                except PluginSettingsError:
                    self._logger.warning(
                        "Ignoring invalid stored setting %s.%s", plugin_id, key
                    )
            resolved[key] = setting.default
        return resolved

    def _compose_cronjobs(
        self, entries: dict[str, _PluginEntry]
    ) -> tuple[tuple[CronjobSpec, ...], dict[str, TaskHandler]]:
        specs: list[CronjobSpec] = []
        handlers: dict[str, TaskHandler] = {}
        for entry in entries.values():
            if entry.context is None:
                continue
            for contribution in entry.context.cronjobs:
                if contribution.spec.id in handlers:
                    self._logger.error(
                        "Duplicate cronjob id ignored: %s (%s)",
                        contribution.spec.id,
                        entry.definition.manifest.id,
                    )
                    continue
                specs.append(contribution.spec)
                handlers[contribution.spec.id] = contribution.handler
        return tuple(specs), handlers

    def _view(self, entry: _PluginEntry) -> PluginView:
        manifest = entry.definition.manifest
        context = entry.context
        resolved = self._settings_for(manifest.id, manifest.settings)
        settings_views = [
            PluginSettingView(
                key=s.key,
                label=s.label,
                type=s.type,
                description=s.description,
                options=list(s.options),
                value=resolved.get(s.key, s.default),
            )
            for s in manifest.settings
        ]
        cronjobs = (
            [
                PluginCronjobView(id=item.spec.id, name=item.spec.name)
                for item in context.cronjobs
            ]
            if context is not None
            else []
        )
        extensions: list[str] = []
        if context is not None:
            extensions = sorted(
                {h.extension() for h in context.upstream_hooks}
                | {h.extension() for h in context.response_hooks}
                | {o.extension() for o in context.request_observers}
                | {h.extension() for h in context.model_catalog_hooks}
            )
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
            extensions=extensions,
            settings=settings_views,
            cronjobs=cronjobs,
        )


def _coerce_setting(setting: PluginSetting, raw: Any) -> Any:
    if setting.type == SETTING_TYPE_BOOL:
        if isinstance(raw, bool):
            return raw
        if isinstance(raw, str) and raw.strip().lower() in {"1", "true", "yes", "on"}:
            return True
        if isinstance(raw, str) and raw.strip().lower() in {"0", "false", "no", "off"}:
            return False
        raise PluginSettingsError(f"{setting.key} 需要布尔值")
    if setting.type == SETTING_TYPE_INT:
        try:
            value = int(raw)
        except (TypeError, ValueError) as exc:
            raise PluginSettingsError(f"{setting.key} 需要整数") from exc
        return value
    text = str(raw if raw is not None else "")
    if setting.type == SETTING_TYPE_ENUM:
        if setting.options and text not in setting.options:
            raise PluginSettingsError(
                f"{setting.key} 只能是 {'、'.join(setting.options)}"
            )
        return text
    return text


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
