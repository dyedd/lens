from __future__ import annotations

from fastapi import FastAPI

from ..gateway.service.admin.foreign_imports import preview_foreign_site_import
from ..gateway.service.admin.model_groups import (
    create_model_group,
    delete_model_group,
    ensure_model_groups_from_site,
    get_model_group,
    list_model_group_candidates,
    list_model_groups,
    test_model_group_model,
    update_model_group,
)
from ..gateway.service.admin.ops import (
    clear_request_logs,
    create_gateway_api_key,
    delete_gateway_api_key,
    export_settings_bundle,
    get_overview_model_analytics,
    get_overview_summary,
    get_request_log_detail,
    get_router_snapshot,
    import_settings_bundle,
    list_cronjobs,
    list_gateway_api_keys,
    list_overview_daily,
    list_request_logs,
    list_settings,
    run_cronjob,
    sync_model_prices,
    update_cronjob,
    update_gateway_api_key,
    update_model_price,
    update_settings,
)
from ..gateway.service.admin.sites import (
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
from ..gateway.service.auth import (
    change_password,
    check_version,
    get_app_info,
    get_current_admin_profile,
    get_public_branding,
    login,
    update_profile,
)
from ..gateway.service.proxy_routes import (
    list_gateway_models,
    list_gemini_models,
    proxy_anthropic_messages,
    proxy_gemini_generate_content,
    proxy_gemini_stream_generate_content,
    proxy_openai_chat,
    proxy_openai_embeddings,
    proxy_openai_image_edits,
    proxy_openai_image_generations,
    proxy_openai_responses,
    proxy_rerank,
)
from ..models.auth import (
    AdminProfile,
    AdminProfileUpdateResponse,
    AppInfo,
    AuthTokenResponse,
    PublicBranding,
    VersionCheckResult,
)
from ..models.backups import ConfigImportResult
from ..models.channels import ChannelModelSyncResponse
from ..models.cronjobs import CronjobItem, CronjobRunResult
from ..models.foreign_imports import ForeignSiteImportPreview
from ..models.gateway_keys import GatewayApiKey
from ..models.health import HealthSummary
from ..models.model_groups import (
    ModelGroupCandidatesResponse,
    ModelGroupEnsureFromSiteResponse,
    ModelGroupView,
)
from ..models.model_prices import ModelPriceItem, ModelPriceListResponse
from ..models.overview import (
    OverviewDailyPoint,
    OverviewModelAnalytics,
    OverviewSummary,
)
from ..models.request_logs import RequestLogDetail, RequestLogPage
from ..models.settings import SettingItem
from ..models.site_import import SiteBatchImportResult
from ..models.site_model_test import SiteModelFetchItem, SiteModelTestResult
from ..models.sites import SiteCredential, SiteModelGroupSaveResponse
from . import ui_static


def register_public(app: FastAPI) -> None:
    app.add_api_route(
        "/api/public/branding",
        get_public_branding,
        methods=["GET"],
        response_model=PublicBranding,
    )
    app.add_api_route(
        "/api/admin/app-info",
        get_app_info,
        methods=["GET"],
        response_model=AppInfo,
    )


def register_admin_auth(app: FastAPI) -> None:
    app.add_api_route(
        "/api/admin/session",
        login,
        methods=["POST"],
        response_model=AuthTokenResponse,
    )
    app.add_api_route(
        "/api/admin/session",
        get_current_admin_profile,
        methods=["GET"],
        response_model=AdminProfile,
    )
    app.add_api_route(
        "/api/admin/profile",
        update_profile,
        methods=["PUT"],
        response_model=AdminProfileUpdateResponse,
    )
    app.add_api_route(
        "/api/admin/password",
        change_password,
        methods=["PUT"],
        status_code=204,
    )


def register_sites(app: FastAPI) -> None:
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
    app.add_api_route(
        "/api/admin/sites/import/preview",
        preview_foreign_site_import,
        methods=["POST"],
        response_model=ForeignSiteImportPreview,
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


def register_version(app: FastAPI) -> None:
    app.add_api_route(
        "/api/admin/version-check",
        check_version,
        methods=["GET"],
        response_model=VersionCheckResult,
    )


def register_routing(app: FastAPI) -> None:
    app.add_api_route(
        "/api/admin/routes",
        get_router_snapshot,
        methods=["GET"],
    )


def register_overview(app: FastAPI) -> None:
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


def register_request_logs(app: FastAPI) -> None:
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


def register_model_groups(app: FastAPI) -> None:
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


def register_model_prices(app: FastAPI) -> None:
    app.add_api_route(
        "/api/admin/model-prices/{model_key}",
        update_model_price,
        methods=["PUT"],
        response_model=ModelPriceItem,
    )
    app.add_api_route(
        "/api/admin/model-price-sync-jobs",
        sync_model_prices,
        methods=["POST"],
        response_model=ModelPriceListResponse,
    )


def register_cronjobs(app: FastAPI) -> None:
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


def register_gateway_api_keys(app: FastAPI) -> None:
    app.add_api_route(
        "/api/admin/gateway-api-keys",
        list_gateway_api_keys,
        methods=["GET"],
        response_model=list[GatewayApiKey],
    )
    app.add_api_route(
        "/api/admin/gateway-api-keys",
        create_gateway_api_key,
        methods=["POST"],
        response_model=GatewayApiKey,
    )
    app.add_api_route(
        "/api/admin/gateway-api-keys/{key_id}",
        update_gateway_api_key,
        methods=["PUT"],
        response_model=GatewayApiKey,
    )
    app.add_api_route(
        "/api/admin/gateway-api-keys/{key_id}",
        delete_gateway_api_key,
        methods=["DELETE"],
        status_code=204,
    )


def register_backups(app: FastAPI) -> None:
    app.add_api_route(
        "/api/admin/backups/export",
        export_settings_bundle,
        methods=["GET"],
    )
    app.add_api_route(
        "/api/admin/backups/import",
        import_settings_bundle,
        methods=["POST"],
        response_model=ConfigImportResult,
    )


def register_settings(app: FastAPI) -> None:
    app.add_api_route(
        "/api/admin/settings",
        list_settings,
        methods=["GET"],
        response_model=list[SettingItem],
    )
    app.add_api_route(
        "/api/admin/settings",
        update_settings,
        methods=["PUT"],
        response_model=list[SettingItem],
    )


def register_proxy(app: FastAPI) -> None:
    app.add_api_route("/v1/chat/completions", proxy_openai_chat, methods=["POST"])
    app.add_api_route("/v1/responses", proxy_openai_responses, methods=["POST"])
    app.add_api_route("/v1/embeddings", proxy_openai_embeddings, methods=["POST"])
    app.add_api_route(
        "/v1/images/generations",
        proxy_openai_image_generations,
        methods=["POST"],
    )
    app.add_api_route("/v1/images/edits", proxy_openai_image_edits, methods=["POST"])
    app.add_api_route("/v1/rerank", proxy_rerank, methods=["POST"])
    app.add_api_route("/v1/messages", proxy_anthropic_messages, methods=["POST"])
    app.add_api_route("/v1/models", list_gateway_models, methods=["GET"])
    app.add_api_route("/v1beta/models", list_gemini_models, methods=["GET"])
    app.add_api_route(
        "/v1beta/models/{model_name}:generateContent",
        proxy_gemini_generate_content,
        methods=["POST"],
    )
    app.add_api_route(
        "/v1beta/models/{model_name}:streamGenerateContent",
        proxy_gemini_stream_generate_content,
        methods=["POST"],
    )


def include_routes(app: FastAPI, *, ui_static_dir: str = "") -> None:
    """Register all public, administrative, proxy, and UI routes on the app."""
    for register in (
        register_public,
        register_admin_auth,
        register_sites,
        register_version,
        register_routing,
        register_overview,
        register_request_logs,
        register_model_groups,
        register_model_prices,
        register_cronjobs,
        register_gateway_api_keys,
        register_backups,
        register_settings,
        register_proxy,
    ):
        register(app)

    ui_static.register(app, ui_static_dir)


__all__ = ["include_routes"]
