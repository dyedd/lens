from __future__ import annotations

from .runtime_context import (
    AppState,
    AsyncIterator,
    FastAPI,
    HTTPBearer,
    OverviewDailyPoint,
    app_state,
    asynccontextmanager,
    asyncio,
    datetime,
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


def _overview_window_minutes(
    days: int, daily_points: list[OverviewDailyPoint], time_zone_name: str
) -> int:
    time_zone = resolve_time_zone(time_zone_name)
    now = datetime.now(time_zone)
    if days == -1:
        start_at = now.replace(hour=0, minute=0, second=0, microsecond=0)
        return max(int((now - start_at).total_seconds() // 60), 1)
    if days > 0:
        return max(days * 24 * 60, 1)
    if daily_points:
        try:
            start_at = datetime.strptime(daily_points[0].date, "%Y%m%d").replace(
                tzinfo=time_zone
            )
        except ValueError:
            return max(len(daily_points) * 24 * 60, 1)
        return max(int((now - start_at).total_seconds() // 60), 1)
    return 0


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
