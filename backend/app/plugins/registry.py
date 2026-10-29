from __future__ import annotations

import json
import re
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING

from ..core.errors import ResourceNotFoundError
from ..models.plugins import PluginCronjobView, PluginState, PluginView
from ..models.settings import SettingItem
from ..persistence.cronjob_store import CronjobSpec
from ..persistence.settings_keys import SETTING_PLUGINS_DISABLED
from .contract import (
    PLUGIN_API_VERSION,
    ModelCatalogHook,
    PluginContext,
    PluginDefinition,
    RequestObserver,
    TaskHandler,
    UpstreamHook,
)

if TYPE_CHECKING:
    import logging

    from ..gateway.service.app_state import AppState

_PLUGIN_ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9_]{0,63}$")


@dataclass(slots=True)
class _PluginEntry:
    definition: PluginDefinition
    state: PluginState
    error: str = ""
    context: PluginContext | None = None


class PluginRegistry:
    """组合已注册插件，按启用状态决定哪些扩展点生效。

    单个插件注册失败只把自己标记为 failed，其余插件照常生效。
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
        self._entries: dict[str, _PluginEntry] = {}
        self._cronjob_specs: tuple[CronjobSpec, ...] = ()
        self._cronjob_handlers: dict[str, TaskHandler] = {}
        self._upstream_hooks: list[UpstreamHook] = []
        self._request_observers: list[RequestObserver] = []
        self._model_catalog_hooks: list[ModelCatalogHook] = []
        self._reconcile()

    def views(self) -> list[PluginView]:
        """按注册顺序列出插件及其状态。"""
        return [self._view(entry) for entry in self._entries.values()]

    def cronjob_specs(self) -> tuple[CronjobSpec, ...]:
        """当前生效插件追加的计划任务定义。"""
        return self._cronjob_specs

    def cronjob_handlers(self) -> dict[str, TaskHandler]:
        """当前生效插件追加的计划任务执行函数。"""
        return dict(self._cronjob_handlers)

    def upstream_hooks(self) -> list[UpstreamHook]:
        """当前生效的出站请求钩子。"""
        return list(self._upstream_hooks)

    def request_observers(self) -> list[RequestObserver]:
        """当前生效的请求观察者。"""
        return list(self._request_observers)

    def model_catalog_hooks(self) -> list[ModelCatalogHook]:
        """当前生效的模型目录钩子。"""
        return list(self._model_catalog_hooks)

    async def load(self) -> None:
        """读取持久化的停用清单，重建生效插件。"""
        items = await self._state.settings_repo.list_settings()
        raw_value = next(
            (item.value for item in items if item.key == SETTING_PLUGINS_DISABLED),
            "",
        )
        self._disabled_ids = _parse_disabled_ids(raw_value, logger=self._logger)
        self._reconcile()

    async def set_enabled(self, plugin_id: str, *, enabled: bool) -> PluginView:
        """启用或停用插件并持久化；返回刷新后的状态。"""
        if plugin_id not in self._entries:
            raise ResourceNotFoundError(plugin_id)
        if enabled:
            self._disabled_ids.discard(plugin_id)
        else:
            self._disabled_ids.add(plugin_id)
        await self._state.settings_repo.upsert_settings(
            [
                SettingItem(
                    key=SETTING_PLUGINS_DISABLED,
                    value=_dump_disabled_ids(self._disabled_ids),
                )
            ]
        )
        self._reconcile()
        return self._view(self._entries[plugin_id])

    def _reconcile(self) -> None:
        entries: dict[str, _PluginEntry] = {}
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
            if manifest.id in self._disabled_ids:
                entry.state = PluginState.DISABLED
                continue
            if manifest.api_version != PLUGIN_API_VERSION:
                entry.state = PluginState.FAILED
                entry.error = (
                    f"插件 API 版本不兼容：需要 {PLUGIN_API_VERSION}，"
                    f"实际 {manifest.api_version}"
                )
                continue
            context = PluginContext(self._state)
            try:
                definition.register(context)
            except Exception as exc:
                entry.state = PluginState.FAILED
                entry.error = str(exc) or exc.__class__.__name__
                self._logger.exception("Plugin registration failed: %s", manifest.id)
                continue
            entry.context = context

        self._entries = entries
        self._cronjob_specs, self._cronjob_handlers = self._compose_cronjobs(entries)
        active = [entry.context for entry in entries.values() if entry.context]
        self._upstream_hooks = [h for ctx in active for h in ctx.upstream_hooks]
        self._request_observers = [o for ctx in active for o in ctx.request_observers]
        self._model_catalog_hooks = [
            m for ctx in active for m in ctx.model_catalog_hooks
        ]

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

    @staticmethod
    def _view(entry: _PluginEntry) -> PluginView:
        manifest = entry.definition.manifest
        context = entry.context
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
                {hook.extension() for hook in context.upstream_hooks}
                | {observer.extension() for observer in context.request_observers}
                | {hook.extension() for hook in context.model_catalog_hooks}
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
            extensions=extensions,
            cronjobs=cronjobs,
        )


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
