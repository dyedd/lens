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
    value: Any = ""


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


class PluginUpdate(StrictBaseModel):
    enabled: bool


class PluginSettingsUpdate(StrictBaseModel):
    values: dict[str, Any] = Field(default_factory=dict)
