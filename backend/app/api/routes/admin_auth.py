from fastapi import FastAPI

from ...gateway.service.auth import (
    change_password,
    get_current_admin_profile,
    login,
    update_profile,
)
from ...models.auth import (
    AdminProfile,
    AdminProfileUpdateResponse,
    AuthTokenResponse,
)


def register(app: FastAPI) -> None:
    app.add_api_route(
        "/api/admin/session",
        login,
        methods=["POST"],
        response_model=AuthTokenResponse,
    )
    app.add_api_route(
        "/api/admin/session",
        get_current_admin_profile,
        methods=["GET"],
        response_model=AdminProfile,
    )
    app.add_api_route(
        "/api/admin/profile",
        update_profile,
        methods=["PUT"],
        response_model=AdminProfileUpdateResponse,
    )
    app.add_api_route(
        "/api/admin/password",
        change_password,
        methods=["PUT"],
        status_code=204,
    )
