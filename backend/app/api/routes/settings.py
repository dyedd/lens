from fastapi import FastAPI

from ...gateway.service.admin.settings import list_settings, update_settings
from ...models.settings import SettingItem


def register(app: FastAPI) -> None:
    app.add_api_route(
        "/api/admin/settings",
        list_settings,
        methods=["GET"],
        response_model=list[SettingItem],
    )
    app.add_api_route(
        "/api/admin/settings",
        update_settings,
        methods=["PUT"],
        response_model=list[SettingItem],
    )
