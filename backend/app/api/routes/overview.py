from fastapi import FastAPI

from ...gateway.service.admin.overview import (
    get_overview_model_analytics,
    get_overview_summary,
    list_overview_daily,
)
from ...models.overview import (
    OverviewDailyPoint,
    OverviewModelAnalytics,
    OverviewSummary,
)


def register(app: FastAPI) -> None:
    app.add_api_route(
        "/api/admin/overview-summary",
        get_overview_summary,
        methods=["GET"],
        response_model=OverviewSummary,
    )
    app.add_api_route(
        "/api/admin/overview-daily",
        list_overview_daily,
        methods=["GET"],
        response_model=list[OverviewDailyPoint],
    )
    app.add_api_route(
        "/api/admin/overview-models",
        get_overview_model_analytics,
        methods=["GET"],
        response_model=OverviewModelAnalytics,
    )
