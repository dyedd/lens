from __future__ import annotations

from fastapi import FastAPI


def register(app: FastAPI, service_module) -> None:
    app.add_api_route("/healthz", service_module.healthz, methods=["GET"])
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
