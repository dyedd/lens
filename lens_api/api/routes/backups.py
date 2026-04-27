from __future__ import annotations

from fastapi import FastAPI


def register(app: FastAPI, service_module) -> None:
    app.add_api_route(
        "/api/admin/backups/export",
        service_module.export_settings_bundle,
        methods=["GET"],
    )
    app.add_api_route(
        "/api/admin/backups/import",
        service_module.import_settings_bundle,
        methods=["POST"],
        response_model=service_module.ConfigImportResult,
    )
