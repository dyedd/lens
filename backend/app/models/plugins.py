from enum import Enum
from typing import Any

from pydantic import Field

from .validation import StrictBaseModel


class PluginState(str, Enum):
    ACTIVE = "active"
    PENDING = "pending"
    DISABLED = "disabled"
    FAILED = "failed"


class PluginCronjobView(StrictBaseModel):
    id: str
    name: str


class PluginSettingView(StrictBaseModel):
    key: str
    label: str
    type: str
    description: str = ""
    options: list[str] = Field(default_factory=list)
    min_value: int | float | None = None
    max_value: int | float | None = None
    secret: bool = False
    # 密钥设置不回显值，只说明是否已设置。
    is_set: bool = False
    value: Any = ""


class PluginExtensionStatsView(StrictBaseModel):
    extension: str
    calls: int = 0
    failures: int = 0
    avg_ms: float = 0.0
    last_outcome: str = ""
    last_error: str = ""
    dropped: int = 0


class PluginView(StrictBaseModel):
    id: str
    name: str
    description: str = ""
    version: str
    author: str = ""
    homepage: str = ""
    source: str = "builtin"
    state: PluginState
    error: str = ""
    requires: list[str] = Field(default_factory=list)
    extensions: list[str] = Field(default_factory=list)
    settings: list[PluginSettingView] = Field(default_factory=list)
    cronjobs: list[PluginCronjobView] = Field(default_factory=list)
    # 本插件当前提供的路由策略标识 `<插件 id>/<name>`。
    strategies: list[str] = Field(default_factory=list)
    stats: list[PluginExtensionStatsView] = Field(default_factory=list)


class PluginUpdate(StrictBaseModel):
    enabled: bool


class PluginSettingsUpdate(StrictBaseModel):
    # null 恢复默认值；密钥设置传 "" 表示保持原值。
    values: dict[str, Any] = Field(default_factory=dict)
