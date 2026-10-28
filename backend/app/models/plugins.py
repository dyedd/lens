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
    cronjobs: list[PluginCronjobView] = Field(default_factory=list)


class PluginUpdate(StrictBaseModel):
    enabled: bool
