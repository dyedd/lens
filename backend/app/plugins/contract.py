from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING

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
class CronjobContribution:
    """插件贡献的一个计划任务。"""

    spec: CronjobSpec
    handler: TaskHandler


class PluginContext:
    """插件注册时拿到的依赖入口，收集它向各扩展点提交的内容。"""

    def __init__(self, state: AppState) -> None:
        self.state = state
        self.cronjobs: list[CronjobContribution] = []

    def add_cronjob(self, spec: CronjobSpec, handler: TaskHandler) -> None:
        """贡献一个计划任务；`handler` 由调度器在到点时调用。"""
        self.cronjobs.append(CronjobContribution(spec=spec, handler=handler))


@dataclass(frozen=True, slots=True)
class PluginDefinition:
    """一个可注册插件：清单加注册函数。"""

    manifest: PluginManifest
    register: Callable[[PluginContext], None]
