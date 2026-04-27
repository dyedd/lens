from __future__ import annotations

from fastapi import FastAPI


def register(app: FastAPI, service_module) -> None:
    app.add_api_route(
        "/api/admin/settings",
        service_module.list_settings,
        methods=["GET"],
        response_model=list[service_module.SettingItem],
    )
    app.add_api_route(
        "/api/admin/settings",
        service_module.update_settings,
        methods=["PUT"],
        response_model=list[service_module.SettingItem],
    )
