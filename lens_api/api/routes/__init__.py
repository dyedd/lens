from __future__ import annotations

from fastapi import FastAPI

from . import admin_auth, backups, cronjobs, gateway_api_keys, model_groups, model_prices, overview, proxy, public, request_logs, routing, settings, sites, ui_static


def include_routes(app: FastAPI, service_module) -> None:
    public.register(app, service_module)
    admin_auth.register(app, service_module)
    sites.register(app, service_module)
    routing.register(app, service_module)
    overview.register(app, service_module)
    request_logs.register(app, service_module)
    model_groups.register(app, service_module)
    model_prices.register(app, service_module)
    cronjobs.register(app, service_module)
    gateway_api_keys.register(app, service_module)
    backups.register(app, service_module)
    settings.register(app, service_module)
    proxy.register(app, service_module)
    ui_static.register(app, service_module)
