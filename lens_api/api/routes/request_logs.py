from __future__ import annotations

from fastapi import FastAPI


def register(app: FastAPI, service_module) -> None:
    app.add_api_route(
        "/api/admin/request-logs",
        service_module.request_logs,
        methods=["GET"],
        response_model=list[service_module.RequestLogItem],
    )
    app.add_api_route(
        "/api/admin/request-logs",
        service_module.clear_request_logs,
        methods=["DELETE"],
        status_code=204,
    )
    app.add_api_route(
        "/api/admin/request-logs/{log_id}",
        service_module.request_log_detail,
        methods=["GET"],
        response_model=service_module.RequestLogDetail,
    )
