from __future__ import annotations

from typing import Any

from fastapi import Depends, HTTPException, UploadFile

from ....models.foreign_imports import ForeignSiteImportPreview
from ..auth import get_current_admin
from .foreign_site_import import (
    UnknownForeignFormatError,
    build_foreign_site_import_preview,
)


async def preview_foreign_site_import(
    file: UploadFile, _: Any = Depends(get_current_admin)
) -> ForeignSiteImportPreview:
    """Detect a foreign backup file and preview the sites it would import."""
    raw = await file.read()
    try:
        return build_foreign_site_import_preview(raw)
    except UnknownForeignFormatError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
