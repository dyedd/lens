from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.security import HTTPBearer

from ...core.auth import validate_auth_secret_key
from ...core.config import settings
from ...core.time_zone import resolve_time_zone
from .app_state import AppState, app_state


async def _startup_app_state(state: AppState) -> None:
    validate_auth_secret_key(settings.auth_secret_key)
    resolve_time_zone(None)
    if state.http.is_closed:
        state.http = state._create_http_client()
    await state.request_log_store.fail_running_request_logs()


async def _close_app_state(state: AppState) -> None:
    await state.close_http_clients()
    await state.engine.dispose()


@asynccontextmanager
async def _managed_lifespan(state: AppState) -> AsyncIterator[None]:
    await _startup_app_state(state)
    await state.cronjob_runner.start()
    try:
        yield
    except asyncio.CancelledError:
        # Uvicorn on Windows cancels the lifespan receive loop during Ctrl+C; treat as normal shutdown.
        pass
    finally:
        await state.cronjob_runner.stop()
        await _close_app_state(state)


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    async with _managed_lifespan(app_state):
        yield


auth_scheme = HTTPBearer(auto_error=False)
