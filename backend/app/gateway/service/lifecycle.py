from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.security import HTTPBearer

from ...core.auth import validate_auth_secret_key
from ...core.config import settings
from ...core.time_zone import load_time_zone
from ...plugins.discovery import resolve_plugins_dir
from ...plugins.watcher import PluginDirectoryWatcher
from .app_state import AppState, app_state
from .tasks.model_group_reconcile import run_model_group_reconcile

logger = logging.getLogger(__name__)


async def _startup_app_state(state: AppState) -> None:
    validate_auth_secret_key(settings.auth_secret_key)
    load_time_zone(None)
    if state.http.is_closed:
        state.http = state._create_http_client()
    await state.request_log_store.maintenance.fail_running_request_logs()
    await state.load_plugins()
    await run_model_group_reconcile(state, should_raise=True)


async def _close_app_state(state: AppState) -> None:
    # 插件的卸载回调可能还要用数据库与 HTTP 客户端，先于它们关闭。
    await state.close_plugins()
    await state.close_http_clients()
    await state.engine.dispose()


def _build_plugin_watcher(state: AppState) -> PluginDirectoryWatcher | None:
    root = resolve_plugins_dir()
    if root is None:
        return None
    return PluginDirectoryWatcher(root, on_change=state.reload_plugins, logger=logger)


@asynccontextmanager
async def _managed_lifespan(state: AppState) -> AsyncIterator[None]:
    await _startup_app_state(state)
    plugin_watcher = _build_plugin_watcher(state)
    await state.cronjob_runner.start()
    if plugin_watcher is not None:
        await plugin_watcher.start()
    try:
        yield
    except asyncio.CancelledError:
        # Uvicorn on Windows cancels the lifespan receive loop during Ctrl+C; treat as normal shutdown.
        pass
    finally:
        if plugin_watcher is not None:
            await plugin_watcher.stop()
        await state.cronjob_runner.stop()
        await _close_app_state(state)


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    async with _managed_lifespan(app_state):
        yield


auth_scheme = HTTPBearer(auto_error=False)
