from __future__ import annotations

from fastapi import FastAPI


def register(app: FastAPI, service_module) -> None:
    app.add_api_route(
        "/api/admin/version-check",
        service_module.check_version,
        methods=["GET"],
        response_model=service_module.VersionCheckResult,
    )
