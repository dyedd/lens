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
    author: str = ""
    homepage: str = ""
    # builtin：随 Lens 发布；external：用户放在插件目录里。
    source: str = "builtin"
    state: PluginState
    error: str = ""
    # 插件挂到的扩展点标识，如 upstream_request / upstream_credential。
    extensions: list[str] = Field(default_factory=list)
    cronjobs: list[PluginCronjobView] = Field(default_factory=list)


class PluginUpdate(StrictBaseModel):
    enabled: bool
