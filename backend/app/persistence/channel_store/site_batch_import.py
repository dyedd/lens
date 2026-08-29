from __future__ import annotations

from dataclasses import dataclass

from ...models.sites import (
    SiteBatchImportFieldError,
    SiteBatchImportItemResult,
    SiteBatchImportResult,
    SiteImportItem,
)
from .site_import_preparation import PreparedSiteImport, prepare_site_import


@dataclass
class PreparedSiteBatch:
    sites: dict[int, PreparedSiteImport]
    item_results: dict[int, SiteBatchImportItemResult]


def prepare_site_batch(
    sites: list[SiteImportItem],
    existing_names: set[str],
) -> PreparedSiteBatch:
    prepared_sites: dict[int, PreparedSiteImport] = {}
    item_results: dict[int, SiteBatchImportItemResult] = {}
    seen_names: set[str] = set()

    for index, site in enumerate(sites):
        name = site.name.strip()
        if not name:
            item_results[index] = SiteBatchImportItemResult(
                index=index,
                name=name,
                status="error",
                reason="",
                site=None,
                errors=[
                    SiteBatchImportFieldError(
                        field="name",
                        message="Site name is required",
                    )
                ],
            )
            continue

        name_key = name.lower()
        if name_key in existing_names:
            item_results[index] = SiteBatchImportItemResult(
                index=index,
                name=name,
                status="skipped",
                reason="duplicate_name",
                site=None,
                errors=[],
            )
            continue
        if name_key in seen_names:
            item_results[index] = SiteBatchImportItemResult(
                index=index,
                name=name,
                status="skipped",
                reason="duplicate_in_file",
                site=None,
                errors=[],
            )
            continue
        seen_names.add(name_key)

        prepared_site, errors = prepare_site_import(site)
        if errors:
            item_results[index] = SiteBatchImportItemResult(
                index=index,
                name=name,
                status="error",
                reason="",
                site=None,
                errors=errors,
            )
            continue
        assert prepared_site is not None
        prepared_sites[index] = prepared_site

    if any(result.status == "error" for result in item_results.values()):
        for index, prepared_site in prepared_sites.items():
            item_results[index] = SiteBatchImportItemResult(
                index=index,
                name=prepared_site.payload.name,
                status="not_committed",
                reason="batch_validation_failed",
                site=None,
                errors=[],
            )
        prepared_sites = {}

    return PreparedSiteBatch(sites=prepared_sites, item_results=item_results)


def build_site_batch_import_result(
    item_results: dict[int, SiteBatchImportItemResult],
) -> SiteBatchImportResult:
    items = [item_results[index] for index in sorted(item_results)]
    return SiteBatchImportResult(
        committed=any(item.status == "created" for item in items),
        created_count=sum(item.status == "created" for item in items),
        skipped_count=sum(item.status == "skipped" for item in items),
        error_count=sum(item.status == "error" for item in items),
        not_committed_count=sum(item.status == "not_committed" for item in items),
        items=items,
    )
