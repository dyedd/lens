from fastapi import FastAPI

from ...gateway.service.admin.request_logs import (
    clear_request_logs,
    get_request_log_detail,
    list_request_logs,
)
from ...models.request_logs import RequestLogDetail, RequestLogPage


def register(app: FastAPI) -> None:
    app.add_api_route(
        "/api/admin/request-logs/page",
        list_request_logs,
        methods=["GET"],
        response_model=RequestLogPage,
    )
    app.add_api_route(
        "/api/admin/request-logs",
        clear_request_logs,
        methods=["DELETE"],
        status_code=204,
    )
    app.add_api_route(
        "/api/admin/request-logs/{log_id}",
        get_request_log_detail,
        methods=["GET"],
        response_model=RequestLogDetail,
    )
