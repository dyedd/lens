from typing import Literal

from .protocols import ProtocolKind
from .site_import import SiteBatchImportRequest
from .validation import StrictBaseModel

ForeignSiteFormat = Literal[
    "lens", "metapi", "sub2api", "ccload", "all_api_hub", "octopus", "cli_proxy_api"
]


class ForeignSitePreview(StrictBaseModel):
    name: str
    enabled: bool
    tags: list[str]
    base_urls: list[str]
    credential_count: int
    model_count: int
    protocols: list[ProtocolKind]


class ForeignSiteImportPreview(StrictBaseModel):
    format: ForeignSiteFormat
    sites: list[ForeignSitePreview]
    warnings: list[str]
    payload: SiteBatchImportRequest | None
