from __future__ import annotations

from fastapi import FastAPI


def register(app: FastAPI, service_module) -> None:
    app.add_api_route(
        "/api/admin/cronjobs",
        service_module.list_cronjobs,
        methods=["GET"],
        response_model=list[service_module.CronjobItem],
    )
    app.add_api_route(
        "/api/admin/cronjobs/{task_id}",
        service_module.update_cronjob,
        methods=["PUT"],
        response_model=service_module.CronjobItem,
    )
    app.add_api_route(
        "/api/admin/cronjobs/{task_id}/runs",
        service_module.run_cronjob,
        methods=["POST"],
        response_model=service_module.CronjobRunResult,
    )
