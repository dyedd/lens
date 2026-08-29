from fastapi import FastAPI

from ...gateway.service.admin.backups import (
    export_settings_bundle,
    import_settings_bundle,
)
from ...models.backups import ConfigImportResult


def register(app: FastAPI) -> None:
    app.add_api_route(
        "/api/admin/backups/export",
        export_settings_bundle,
        methods=["GET"],
    )
    app.add_api_route(
        "/api/admin/backups/import",
        import_settings_bundle,
        methods=["POST"],
        response_model=ConfigImportResult,
    )
