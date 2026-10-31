from __future__ import annotations

import asyncio
import contextlib
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.security import HTTPBearer

from ...core.auth import validate_auth_secret_key
from ...core.config import settings
from ...core.time_zone import load_time_zone
from .app_state import AppState, app_state
from .tasks.model_group_reconcile import run_model_group_reconcile

logger = logging.getLogger(__name__)


async def _prime_model_catalog(state: AppState) -> None:
    """Warm the shared catalog so channel models can show detected sizes.

    Warm-up is best effort: an offline host keeps the empty snapshot and the
    channel editor falls back to the manual and upstream values.
    """
    try:
        await state.refresh_model_catalog()
    except Exception:
        logger.exception("Model catalog warm-up failed")


async def _startup_app_state(state: AppState) -> None:
    validate_auth_secret_key(settings.auth_secret_key)
    load_time_zone(None)
    if state.http.is_closed:
        state.http = state._create_http_client()
    await state.request_log_store.maintenance.fail_running_request_logs()
    await run_model_group_reconcile(state, should_raise=True)


async def _close_app_state(state: AppState) -> None:
    await state.close_http_clients()
    await state.engine.dispose()


@asynccontextmanager
async def _managed_lifespan(state: AppState) -> AsyncIterator[None]:
    await _startup_app_state(state)
    await state.cronjob_runner.start()
    warm_up = asyncio.create_task(_prime_model_catalog(state))
    try:
        yield
    except asyncio.CancelledError:
        # Uvicorn on Windows cancels the lifespan receive loop during Ctrl+C; treat as normal shutdown.
        pass
    finally:
        warm_up.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await warm_up
        await state.cronjob_runner.stop()
        await _close_app_state(state)


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    async with _managed_lifespan(app_state):
        yield


auth_scheme = HTTPBearer(auto_error=False)
