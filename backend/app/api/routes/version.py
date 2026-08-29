from fastapi import FastAPI

from ...gateway.service.auth import check_version
from ...models.auth import VersionCheckResult


def register(app: FastAPI) -> None:
    app.add_api_route(
        "/api/admin/version-check",
        check_version,
        methods=["GET"],
        response_model=VersionCheckResult,
    )
