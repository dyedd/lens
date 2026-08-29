from fastapi import FastAPI

from ...gateway.service.admin.model_groups import (
    create_model_group,
    delete_model_group,
    ensure_model_groups_from_site,
    get_model_group,
    list_model_group_candidates,
    list_model_groups,
    test_model_group_model,
    update_model_group,
)
from ...models.model_groups import (
    ModelGroupCandidatesResponse,
    ModelGroupEnsureFromSiteResponse,
    ModelGroupView,
)
from ...models.sites import SiteModelTestResult


def register(app: FastAPI) -> None:
    app.add_api_route(
        "/api/admin/model-group-candidates",
        list_model_group_candidates,
        methods=["POST"],
        response_model=ModelGroupCandidatesResponse,
    )
    app.add_api_route(
        "/api/admin/model-groups",
        list_model_groups,
        methods=["GET"],
        response_model=list[ModelGroupView],
    )
    app.add_api_route(
        "/api/admin/model-groups",
        create_model_group,
        methods=["POST"],
        response_model=ModelGroupView,
        status_code=201,
    )
    app.add_api_route(
        "/api/admin/model-groups/ensure-from-site",
        ensure_model_groups_from_site,
        methods=["POST"],
        response_model=ModelGroupEnsureFromSiteResponse,
    )
    app.add_api_route(
        "/api/admin/model-groups/{group_id}/model-tests",
        test_model_group_model,
        methods=["POST"],
        response_model=SiteModelTestResult,
    )
    app.add_api_route(
        "/api/admin/model-groups/{group_id}",
        get_model_group,
        methods=["GET"],
        response_model=ModelGroupView,
    )
    app.add_api_route(
        "/api/admin/model-groups/{group_id}",
        update_model_group,
        methods=["PUT"],
        response_model=ModelGroupView,
    )
    app.add_api_route(
        "/api/admin/model-groups/{group_id}",
        delete_model_group,
        methods=["DELETE"],
        status_code=204,
    )
