from .common import StrictBaseModel

class SettingItem(StrictBaseModel):
    key: str
    value: str


class SettingsUpdate(StrictBaseModel):
    items: list[SettingItem]
