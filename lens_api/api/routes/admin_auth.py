from types import ModuleType

from fastapi import FastAPI


def register(app: FastAPI, service_module: ModuleType) -> None:
    app.add_api_route(
        "/api/admin/session",
        service_module.login,
        methods=["POST"],
        response_model=service_module.AuthTokenResponse,
    )
    app.add_api_route(
        "/api/admin/session",
        service_module.get_current_admin_profile,
        methods=["GET"],
        response_model=service_module.AdminProfile,
    )
    app.add_api_route(
        "/api/admin/profile",
        service_module.update_profile,
        methods=["PUT"],
        response_model=service_module.AdminProfileUpdateResponse,
    )
    app.add_api_route(
        "/api/admin/password",
        service_module.change_password,
        methods=["PUT"],
        status_code=204,
    )
