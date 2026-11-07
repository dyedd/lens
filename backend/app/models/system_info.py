from .validation import StrictBaseModel


class PublicBranding(StrictBaseModel):
    site_name: str
    logo_url: str = ""


class AppInfo(StrictBaseModel):
    system_version: str
    site_name: str
    logo_url: str = ""
    time_zone: str


class VersionCheckResult(StrictBaseModel):
    current_version: str
    latest_version: str
    release_url: str
    has_update: bool
    checked_at: str
