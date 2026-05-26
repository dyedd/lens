from types import ModuleType

from fastapi import FastAPI


def register(app: FastAPI, service_module: ModuleType) -> None:
    app.add_api_route(
        "/api/admin/version-check",
        service_module.check_version,
        methods=["GET"],
        response_model=service_module.VersionCheckResult,
    )
