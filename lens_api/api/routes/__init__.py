
from fastapi import FastAPI

from . import admin_auth, backups, cronjobs, gateway_api_keys, model_groups, model_prices, overview, proxy, public, request_logs, routing, settings, sites, ui_static, version


def include_routes(app: FastAPI, service_module) -> None:
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
        ui_static,
    ):
        module.register(app, service_module)
