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
from .app_state import AppState, bind_app_state, reset_app_state
from .tasks.model_group_reconcile import run_model_group_reconcile

logger = logging.getLogger(__name__)


async def _prime_model_catalog(state: AppState) -> None:
    """Warm the shared catalog so channel models can show detected sizes.

    Warm-up is best effort: an offline host keeps the empty snapshot and the
    channel editor falls back to the manual and upstream values.
    """
    try:
        await state.refresh_model_catalog()
    except Exception as exc:
        logger.warning("Model catalog warm-up skipped: %s", exc)


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
    try:
        await asyncio.wait_for(_prime_model_catalog(state), timeout=5)
    except TimeoutError:
        logger.warning("Model catalog warm-up timed out")
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
