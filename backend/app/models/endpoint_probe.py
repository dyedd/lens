from pydantic import Field, HttpUrl

from .protocols import ChannelProxyMode
from .validation import StrictBaseModel


class EndpointProbeRequest(StrictBaseModel):
    """One upstream address to time, using the channel's proxy settings."""

    base_url: HttpUrl
    proxy_mode: ChannelProxyMode = ChannelProxyMode.INHERIT
    channel_proxy: str = ""


class EndpointProbeResult(StrictBaseModel):
    """Round-trip timing until the upstream answers with response headers."""

    success: bool
    status_code: int | None = None
    latency_ms: int = Field(default=0, ge=0)
    error_message: str = ""
