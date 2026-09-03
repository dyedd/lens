"""Import channels from a foreign gateway backup into the configured Lens database.

Supports the same formats as the backups-page migration card: Octopus, metapi,
Sub2API, ccLoad (CSV), and All API Hub. The import is additive: existing
channels are never modified, and channels whose name already exists are skipped.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

from app.core.config import settings
from app.core.db import create_engine, create_session_factory
from app.gateway.service.admin.foreign_site_import import (
    UnknownForeignFormatError,
    build_foreign_site_import_preview,
)
from app.models.site_import import SiteBatchImportRequest
from app.persistence.channel_store import ChannelStore


def print_import_preview(
    export_path: Path,
) -> tuple[str, SiteBatchImportRequest | None]:
    """Detect the backup format and print the channels it would import."""
    preview = build_foreign_site_import_preview(export_path.read_bytes())
    print(f"format: {preview.format}")
    for warning in preview.warnings:
        print(f"warning: {warning}")
    for site in preview.sites:
        protocols = ", ".join(protocol.value for protocol in site.protocols)
        print(
            f"channel: {site.name} | {site.base_urls[0] if site.base_urls else '-'}"
            f" | {site.credential_count} keys | {site.model_count} models"
            f" | {protocols}"
        )
    return preview.format, preview.payload


async def commit_import(payload: SiteBatchImportRequest) -> int:
    """Write the recognized channels to the database and report per-item results."""
    engine = create_engine(settings.database_url)
    try:
        channel_store = ChannelStore(create_session_factory(engine))
        result = await channel_store.import_sites(payload)
    finally:
        await engine.dispose()

    for item in result.items:
        if item.status == "created":
            continue
        detail = item.reason or "; ".join(
            f"{error.field}: {error.message}" for error in item.errors
        )
        print(f"{item.status}: {item.name} ({detail})")
    print(
        f"created={result.created_count} skipped={result.skipped_count}"
        f" errors={result.error_count} not_committed={result.not_committed_count}"
    )
    return 0 if result.error_count == 0 and result.not_committed_count == 0 else 1


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__,
    )
    parser.add_argument("export", type=Path, help="path to the foreign backup file")
    parser.add_argument(
        "--commit",
        action="store_true",
        help="write the recognized channels; without this flag only a preview is printed",
    )
    args = parser.parse_args()

    try:
        export_format, payload = print_import_preview(args.export)
    except UnknownForeignFormatError as exc:
        raise SystemExit(f"error: {exc}") from exc
    except OSError as exc:
        raise SystemExit(f"error: cannot read {args.export}: {exc}") from exc

    if export_format == "lens":
        raise SystemExit(
            "this is a Lens backup file; restore it on the backups page instead"
        )
    if payload is None:
        raise SystemExit("no importable channels were found in this file")
    if not args.commit:
        print("preview only; re-run with --commit to import these channels")
        return

    exit_code = asyncio.run(
        commit_import(payload),
        loop_factory=(asyncio.SelectorEventLoop if sys.platform == "win32" else None),
    )
    raise SystemExit(exit_code)


if __name__ == "__main__":
    main()
