from types import ModuleType

from fastapi import FastAPI

from . import (
    admin_auth,
    backups,
    cronjobs,
    gateway_api_keys,
    model_groups,
    model_prices,
    overview,
    proxy,
    public,
    request_logs,
    routing,
    settings,
    sites,
    ui_static,
    version,
)


def include_routes(
    app: FastAPI, service_module: ModuleType, *, ui_static_dir: str = ""
) -> None:
    """Register all public, administrative, proxy, and UI routes on the app."""
    for module in (
        public,
        admin_auth,
        sites,
        version,
        routing,
        overview,
        request_logs,
        model_groups,
        model_prices,
        cronjobs,
        gateway_api_keys,
        backups,
        settings,
        proxy,
    ):
        module.register(app, service_module)
    ui_static.register(app, ui_static_dir)
