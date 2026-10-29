from enum import Enum

from pydantic import Field

from .validation import StrictBaseModel


class PluginState(str, Enum):
    ACTIVE = "active"
    DISABLED = "disabled"
    FAILED = "failed"


class PluginCronjobView(StrictBaseModel):
    id: str
    name: str


class PluginView(StrictBaseModel):
    id: str
    name: str
    description: str = ""
    version: str
    state: PluginState
    error: str = ""
    # 插件挂到的扩展点标识，例如 upstream_headers / upstream_credential。
    extensions: list[str] = Field(default_factory=list)
    cronjobs: list[PluginCronjobView] = Field(default_factory=list)


class PluginUpdate(StrictBaseModel):
    enabled: bool
