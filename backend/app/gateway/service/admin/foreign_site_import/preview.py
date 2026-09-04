from __future__ import annotations

from .....models.foreign_imports import ForeignSiteImportPreview, ForeignSitePreview
from .....models.site_import import SiteBatchImportRequest, SiteImportItem
from .all_api_hub import parse_all_api_hub_sites
from .ccload import parse_ccload_sites
from .cli_proxy_api import parse_cli_proxy_api_sites
from .detection import UnknownForeignFormatError, detect_foreign_format
from .metapi import parse_metapi_sites
from .octopus import parse_octopus_sites
from .parsed import ParsedForeignSites
from .sub2api import parse_sub2api_sites

_LENS_BACKUP_WARNING = (
    "This is a Lens backup file; restore it with the Lens backup import instead"
)

# 各格式解析函数的输入形状由 detection 保证: ccload 收 CSV 文本, 其余收结构化对象。
_PARSERS = {
    "metapi": parse_metapi_sites,
    "sub2api": parse_sub2api_sites,
    "octopus": parse_octopus_sites,
    "all_api_hub": parse_all_api_hub_sites,
    "cli_proxy_api": parse_cli_proxy_api_sites,
}


def build_foreign_site_import_preview(raw: bytes) -> ForeignSiteImportPreview:
    """Detect a foreign backup file and build the preview plus import payload."""
    format_id, content = detect_foreign_format(raw)
    if format_id == "lens":
        return ForeignSiteImportPreview(
            format="lens",
            sites=[],
            warnings=[_LENS_BACKUP_WARNING],
            payload=None,
        )

    if format_id == "ccload":
        parsed = parse_ccload_sites(str(content))
    else:
        parser = _PARSERS.get(format_id)
        if parser is None or not isinstance(content, dict):
            raise UnknownForeignFormatError("Unrecognized backup file format")
        parsed = parser(content)
    return _build_preview(format_id, parsed)


def _build_preview(
    format_id: str,
    parsed: ParsedForeignSites,
) -> ForeignSiteImportPreview:
    return ForeignSiteImportPreview(
        format=format_id,  # type: ignore[arg-type] # detection 限定了合法值
        sites=[_build_site_preview(item) for item in parsed.sites],
        warnings=parsed.warnings + parsed.skipped,
        payload=SiteBatchImportRequest(sites=parsed.sites) if parsed.sites else None,
    )


def _build_site_preview(item: SiteImportItem) -> ForeignSitePreview:
    protocols: list = []
    for protocol_config in item.protocols:
        if protocol_config.protocol not in protocols:
            protocols.append(protocol_config.protocol)
    return ForeignSitePreview(
        name=item.name,
        enabled=item.enabled,
        tags=list(item.tags),
        base_urls=[str(base_url.url) for base_url in item.base_urls],
        credential_count=len(item.credentials),
        model_count=sum(len(config.models) for config in item.protocols),
        protocols=protocols,
    )
