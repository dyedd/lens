from __future__ import annotations

from fastapi import FastAPI


def register(app: FastAPI, service_module) -> None:
    app.add_api_route(
        "/api/admin/session",
        service_module.login,
        methods=["POST"],
        response_model=service_module.AuthTokenResponse,
    )
    app.add_api_route(
        "/api/admin/session",
        service_module.current_admin,
        methods=["GET"],
        response_model=service_module.AdminProfile,
    )
    app.add_api_route(
        "/api/admin/password",
        service_module.change_password,
        methods=["PUT"],
        status_code=204,
    )
