from __future__ import annotations

from fastapi import FastAPI


def register(app: FastAPI, service_module) -> None:
    app.add_api_route(
        "/api/admin/model-group-stats",
        service_module.list_model_group_stats,
        methods=["GET"],
        response_model=list[service_module.ModelGroupStats],
    )
    app.add_api_route(
        "/api/admin/model-group-candidates",
        service_module.model_group_candidates,
        methods=["POST"],
        response_model=service_module.ModelGroupCandidatesResponse,
    )
    app.add_api_route(
        "/api/admin/model-groups",
        service_module.list_model_groups,
        methods=["GET"],
        response_model=list[service_module.ModelGroup],
    )
    app.add_api_route(
        "/api/admin/model-groups",
        service_module.create_model_group,
        methods=["POST"],
        response_model=service_module.ModelGroup,
        status_code=201,
    )
    app.add_api_route(
        "/api/admin/model-groups/{group_id}",
        service_module.get_model_group,
        methods=["GET"],
        response_model=service_module.ModelGroup,
    )
    app.add_api_route(
        "/api/admin/model-groups/{group_id}",
        service_module.update_model_group,
        methods=["PUT"],
        response_model=service_module.ModelGroup,
    )
    app.add_api_route(
        "/api/admin/model-groups/{group_id}",
        service_module.delete_model_group,
        methods=["DELETE"],
        status_code=204,
    )
