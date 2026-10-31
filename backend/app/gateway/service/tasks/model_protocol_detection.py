"""Detect the upstream protocol of channel models.

Facts come first and cost nothing: the endpoint purpose, the listing protocol
of a native Anthropic or Gemini endpoint, a model name that only fits an
embedding, rerank or image API, and NewAPI-style declared endpoint types.
Chat models left open are probed with the model-test request in
`chat_protocol_order`; the first protocol that answers wins.
"""

from __future__ import annotations

import asyncio

from fastapi import HTTPException

from ....core.model_protocols import (
    ENDPOINT_KIND_PROTOCOLS,
    chat_protocol_order,
    resolve_known_protocol,
)
from ....models.channels import ChannelConfig
from ....models.protocols import ProtocolKind
from ....models.site_model_test import (
    SiteModelProtocolDetectionRequest,
    SiteModelProtocolDetectionResult,
    SiteModelTestRequest,
)
from ..upstream_support import format_channel_error
from .model_discovery import (
    NATIVE_LISTING_PROTOCOLS,
    UpstreamModel,
    fetch_upstream_model_list,
)
from .site_model_probe import run_site_model_probe

# Probes run a few at a time so a relay's rate limit is not mistaken for an
# unsupported protocol.
_PROBE_CONCURRENCY = 4
_PROBE_TIMEOUT_SECONDS = 20.0
_PROBE_PROMPT = "hi"
# Answers that say nothing about protocol support stop the fallback.
_INCONCLUSIVE_STATUS_CODES = frozenset({429, 504})


async def detect_model_protocols(
    payload: SiteModelProtocolDetectionRequest,
) -> list[SiteModelProtocolDetectionResult]:
    """Resolve each requested model's protocol, probing only what facts leave open."""
    pinned = ENDPOINT_KIND_PROTOCOLS.get(payload.endpoint_kind)
    listed: dict[str, UpstreamModel] = {}
    if pinned is None:
        try:
            model_list = await fetch_upstream_model_list(_listing_channel(payload))
        except HTTPException:
            # A relay without a model list can still be probed.
            pass
        else:
            listed = {model.name: model for model in model_list.models}
            if model_list.protocol in NATIVE_LISTING_PROTOCOLS:
                pinned = model_list.protocol

    semaphore = asyncio.Semaphore(_PROBE_CONCURRENCY)

    async def detect(model_name: str) -> SiteModelProtocolDetectionResult:
        upstream_model = listed.get(model_name)
        known = resolve_known_protocol(
            model_name,
            pinned=pinned,
            declared=upstream_model.protocols if upstream_model else (),
        )
        if known is not None:
            return SiteModelProtocolDetectionResult(
                model_name=model_name, protocol=known
            )
        async with semaphore:
            return await _probe_chat_protocol(payload, model_name)

    return list(await asyncio.gather(*map(detect, payload.model_names)))


async def _probe_chat_protocol(
    payload: SiteModelProtocolDetectionRequest, model_name: str
) -> SiteModelProtocolDetectionResult:
    errors: list[str] = []
    for protocol in chat_protocol_order(model_name):
        result = await run_site_model_probe(
            _probe_request(payload, model_name, protocol),
            None,
            timeout_seconds=_PROBE_TIMEOUT_SECONDS,
        )
        if result.success:
            return SiteModelProtocolDetectionResult(
                model_name=model_name, protocol=protocol
            )
        errors.append(f"{protocol.value}: {format_channel_error(result.error_message)}")
        if result.status_code in _INCONCLUSIVE_STATUS_CODES:
            break
    return SiteModelProtocolDetectionResult(
        model_name=model_name, error_message="; ".join(errors)
    )


def _probe_request(
    payload: SiteModelProtocolDetectionRequest,
    model_name: str,
    protocol: ProtocolKind,
) -> SiteModelTestRequest:
    return SiteModelTestRequest(
        protocol=protocol,
        base_url=payload.base_url,
        headers=payload.headers,
        proxy_mode=payload.proxy_mode,
        channel_proxy=payload.channel_proxy,
        param_override=payload.param_override,
        credential=payload.credential,
        model_name=model_name,
        prompt=_PROBE_PROMPT,
    )


def _listing_channel(payload: SiteModelProtocolDetectionRequest) -> ChannelConfig:
    credential = payload.credential
    return ChannelConfig(
        id="protocol-detection",
        name=credential.name or "protocol-detection",
        protocol=ProtocolKind.OPENAI_CHAT,
        base_url=payload.base_url,
        api_key=credential.api_key,
        headers=payload.headers,
        keys=[{"id": credential.id, "key": credential.api_key}],
        proxy_mode=payload.proxy_mode,
        channel_proxy=payload.channel_proxy,
    )
