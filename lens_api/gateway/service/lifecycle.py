from __future__ import annotations

from .runtime_context import (
    AppState,
    AsyncIterator,
    FastAPI,
    HTTPBearer,
    app_state,
    asynccontextmanager,
    asyncio,
    resolve_time_zone,
    settings,
)


async def _startup_app_state(state: AppState) -> None:
    if not settings.auth_secret_key.strip():
        raise RuntimeError("LENS_AUTH_SECRET_KEY is required")
    resolve_time_zone(None)
    if state.http.is_closed:
        state.http = state._create_http_client()
    await state.domain_store.fail_running_request_logs(
        interrupted_latency_cap_ms=_running_request_latency_cap_ms()
    )


async def _close_app_state(state: AppState) -> None:
    if not state.http.is_closed:
        await state.http.aclose()
    await state.engine.dispose()


def _running_request_latency_cap_ms() -> int:
    return int(max(settings.request_timeout_seconds, 0) * 1000)


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
