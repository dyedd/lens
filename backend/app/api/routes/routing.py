from fastapi import FastAPI

from ...gateway.service.admin.routing import get_router_snapshot


def register(app: FastAPI) -> None:
    app.add_api_route(
        "/api/admin/routes",
        get_router_snapshot,
        methods=["GET"],
    )
