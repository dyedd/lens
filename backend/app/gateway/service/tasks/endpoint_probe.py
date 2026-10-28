from __future__ import annotations

from time import perf_counter

import httpx

from ....models.endpoint_probe import EndpointProbeRequest, EndpointProbeResult
from ...upstream_request import resolve_proxy_url
from ..app_state import app_state
from ..routing_plan import elapsed_ms
from ..upstream_support import (
    default_lens_user_agent,
    format_transport_error,
    resolve_http_client,
)

# Any HTTP answer proves the address is reachable, so the probe stops at the
# response headers instead of downloading a model list or an error page.
_PROBE_TIMEOUT_SECONDS = 15.0


async def probe_endpoint(payload: EndpointProbeRequest) -> EndpointProbeResult:
    """Time one upstream address until it answers with response headers."""
    runtime = await app_state.settings_repo.get_runtime_settings()
    proxy_url = resolve_proxy_url(
        payload.proxy_mode, payload.channel_proxy, runtime["proxy_url"]
    )
    client = resolve_http_client(proxy_url)
    target_url = str(payload.base_url)
    # HEAD skips the payload, but some gateways reject it, so a transport
    # failure falls back to GET before the address counts as unreachable.
    transport_error: httpx.HTTPError | None = None
    started_at = perf_counter()

    for method in ("HEAD", "GET"):
        try:
            response = await client.send(
                client.build_request(
                    method,
                    target_url,
                    headers={"user-agent": default_lens_user_agent()},
                    timeout=_PROBE_TIMEOUT_SECONDS,
                ),
                stream=True,
            )
        except httpx.HTTPError as exc:
            transport_error = exc
            continue
        try:
            return EndpointProbeResult(
                success=True,
                status_code=response.status_code,
                latency_ms=elapsed_ms(started_at),
            )
        finally:
            await response.aclose()

    return EndpointProbeResult(
        success=False,
        latency_ms=elapsed_ms(started_at),
        error_message=format_transport_error(transport_error, target_url),
    )
