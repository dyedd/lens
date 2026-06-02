from types import ModuleType

from fastapi import FastAPI


def register(app: FastAPI, service_module: ModuleType) -> None:
    app.add_api_route(
        "/api/public/branding",
        service_module.public_branding,
        methods=["GET"],
        response_model=service_module.PublicBranding,
    )
    app.add_api_route(
        "/api/admin/app-info",
        service_module.app_info,
        methods=["GET"],
        response_model=service_module.AppInfo,
    )
