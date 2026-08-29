from fastapi import FastAPI

from ...gateway.service.auth import get_app_info, get_public_branding
from ...models.auth import AppInfo, PublicBranding


def register(app: FastAPI) -> None:
    app.add_api_route(
        "/api/public/branding",
        get_public_branding,
        methods=["GET"],
        response_model=PublicBranding,
    )
    app.add_api_route(
        "/api/admin/app-info",
        get_app_info,
        methods=["GET"],
        response_model=AppInfo,
    )
