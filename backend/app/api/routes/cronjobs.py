from fastapi import FastAPI

from ...gateway.service.admin.cronjobs import (
    list_cronjobs,
    run_cronjob,
    update_cronjob,
)
from ...models.cronjobs import CronjobItem, CronjobRunResult


def register(app: FastAPI) -> None:
    app.add_api_route(
        "/api/admin/cronjobs",
        list_cronjobs,
        methods=["GET"],
        response_model=list[CronjobItem],
    )
    app.add_api_route(
        "/api/admin/cronjobs/{task_id}",
        update_cronjob,
        methods=["PUT"],
        response_model=CronjobItem,
    )
    app.add_api_route(
        "/api/admin/cronjobs/{task_id}/runs",
        run_cronjob,
        methods=["POST"],
        response_model=CronjobRunResult,
    )
