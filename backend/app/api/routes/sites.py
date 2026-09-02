from fastapi import FastAPI

from ...gateway.service.admin.sites import (
    create_site,
    create_site_with_model_groups,
    delete_site,
    fetch_site_models,
    import_sites,
    list_model_health,
    list_sites,
    sync_channel_models,
    sync_site_credential_rate,
    test_site_model,
    update_site,
    update_site_enabled,
    update_site_with_model_groups,
)
from ...models.channels import ChannelModelSyncResponse
from ...models.health import HealthSummary
from ...models.site_import import SiteBatchImportResult
from ...models.site_model_test import SiteModelFetchItem, SiteModelTestResult
from ...models.sites import SiteCredential, SiteModelGroupSaveResponse


def register(app: FastAPI) -> None:
    app.add_api_route("/api/admin/sites", list_sites, methods=["GET"])
    app.add_api_route(
        "/api/admin/model-health",
        list_model_health,
        methods=["GET"],
        response_model=HealthSummary,
    )
    app.add_api_route(
        "/api/admin/sites",
        create_site,
        methods=["POST"],
        status_code=201,
    )
    app.add_api_route(
        "/api/admin/sites/with-model-groups",
        create_site_with_model_groups,
        methods=["POST"],
        response_model=SiteModelGroupSaveResponse,
        status_code=201,
    )
    app.add_api_route(
        "/api/admin/sites/import",
        import_sites,
        methods=["POST"],
        response_model=SiteBatchImportResult,
    )
    app.add_api_route("/api/admin/sites/{site_id}", update_site, methods=["PUT"])
    app.add_api_route(
        "/api/admin/sites/{site_id}/with-model-groups",
        update_site_with_model_groups,
        methods=["PUT"],
        response_model=SiteModelGroupSaveResponse,
    )
    app.add_api_route(
        "/api/admin/sites/{site_id}/enabled",
        update_site_enabled,
        methods=["PUT"],
    )
    app.add_api_route(
        "/api/admin/sites/{site_id}",
        delete_site,
        methods=["DELETE"],
        status_code=204,
    )
    app.add_api_route(
        "/api/admin/site-model-discoveries",
        fetch_site_models,
        methods=["POST"],
        response_model=list[SiteModelFetchItem],
    )
    app.add_api_route(
        "/api/admin/site-model-tests",
        test_site_model,
        methods=["POST"],
        response_model=SiteModelTestResult,
    )
    app.add_api_route(
        "/api/admin/channel-model-sync",
        sync_channel_models,
        methods=["POST"],
        response_model=ChannelModelSyncResponse,
    )
    app.add_api_route(
        "/api/admin/sites/{site_id}/credentials/{credential_id}/rate-sync",
        sync_site_credential_rate,
        methods=["POST"],
        response_model=SiteCredential,
    )
