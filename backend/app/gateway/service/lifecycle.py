from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator
from contextlib import AsyncExitStack, asynccontextmanager

from fastapi import FastAPI
from fastapi.security import HTTPBearer

from ...core.auth import validate_auth_secret_key
from ...core.config import settings
from ...core.time_zone import load_time_zone
from ...plugins.discovery import resolve_plugins_dir
from ...plugins.watcher import PluginDirectoryWatcher
from .app_state import AppState, bind_app_state, reset_app_state
from .tasks.model_group_reconcile import run_model_group_reconcile

logger = logging.getLogger(__name__)


async def _startup_app_state(state: AppState) -> None:
    validate_auth_secret_key(settings.auth_secret_key)
    load_time_zone(None)
    if state.http.is_closed:
        state.http = state._create_http_client()
    state.apply_router_settings(await state.settings_repo.get_runtime_settings())
    await state.request_log_store.maintenance.fail_running_request_logs()
    await state.load_plugins()
    await run_model_group_reconcile(state, should_raise=True)


@asynccontextmanager
async def _managed_lifespan(state: AppState) -> AsyncIterator[None]:
    async with AsyncExitStack() as cleanup:
        cleanup.push_async_callback(state.engine.dispose)
        cleanup.push_async_callback(state.close_http_clients)
        # 插件卸载回调可能使用数据库和 HTTP 客户端，先于它们关闭。
        cleanup.push_async_callback(state.close_plugins)
        await _startup_app_state(state)
        cleanup.push_async_callback(state.cronjob_runner.stop)
        await state.cronjob_runner.start()
        root = resolve_plugins_dir()
        if root is not None:
            watcher = PluginDirectoryWatcher(
                root, on_change=state.reload_plugins, logger=logger
            )
            cleanup.push_async_callback(watcher.stop)
            await watcher.start()
        try:
            yield
        except asyncio.CancelledError:
            # Windows 上的 Uvicorn 用取消 lifespan 接收循环处理 Ctrl+C。
            pass


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    state = getattr(app.state, "app_state", None)
    if state is None:
        state = AppState()
        app.state.app_state = state
    token = bind_app_state(state)
    try:
        async with _managed_lifespan(state):
            yield
    finally:
        reset_app_state(token)


auth_scheme = HTTPBearer(auto_error=False)
