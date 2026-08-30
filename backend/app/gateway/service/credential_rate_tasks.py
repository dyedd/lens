from __future__ import annotations

from datetime import UTC, datetime
from math import isfinite
from typing import Any

import httpx

from ...core.runtime_channel_ids import protocol_config_id_from_runtime_channel_id
from ...core.upstream_endpoints import (
    resolve_newapi_pricing_url,
    resolve_sub2api_billing_url,
)
from ...core.upstream_rules import request_rule_context
from ...models.channels import ChannelConfig
from ...models.protocols import ChannelStatus
from ...models.sites import SiteConfig, SiteCredential
from ..upstream_request import (
    build_upstream_headers,
    resolve_channel_api_key,
    resolve_upstream_proxy_url,
)
from .app_state import AppState
from .model_sync import _channel_for_credential
from .upstream_support import (
    _default_lens_user_agent,
    _format_http_response_error,
)


class CredentialRateSyncError(Exception):
    """Raised when an upstream credential rate cannot be synchronized."""


class CredentialRateNotConfiguredError(CredentialRateSyncError):
    """Raised when a credential has no configured rate source."""


class CredentialRateConflictError(CredentialRateSyncError):
    """Raised when a credential rate configuration changes during sync."""


def _site_credential(site: SiteConfig, credential_id: str) -> SiteCredential | None:
    return next(
        (item for item in site.credentials if item.id == credential_id),
        None,
    )


def _nonnegative_number(value: Any, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"Invalid {label}")
    number = float(value)
    if not isfinite(number) or number < 0:
        raise ValueError(f"Invalid {label}")
    return number


def _parse_sub2api_rate(payload: dict[str, Any]) -> tuple[float, str]:
    schema_version = payload.get("schema_version")
    if (
        payload.get("object") != "sub2api.key_billing"
        or not isinstance(schema_version, int)
        or isinstance(schema_version, bool)
        or schema_version != 1
        or payload.get("billing_scope") != "token"
        or not isinstance(payload.get("peak_rate_enabled"), bool)
    ):
        raise ValueError("Invalid Sub2API billing response")
    _nonnegative_number(
        payload.get("group_rate_multiplier"), "Sub2API group rate multiplier"
    )
    user_rate = payload.get("user_rate_multiplier")
    if user_rate is not None:
        _nonnegative_number(user_rate, "Sub2API user rate multiplier")
    _nonnegative_number(
        payload.get("resolved_rate_multiplier"), "Sub2API resolved rate multiplier"
    )
    observed_at = str(payload.get("observed_at") or "").strip()
    if not observed_at:
        raise ValueError("Sub2API billing response is missing observed_at")
    return (
        _nonnegative_number(
            payload.get("effective_rate_multiplier"),
            "Sub2API effective rate multiplier",
        ),
        observed_at,
    )


def _parse_newapi_rate(
    payload: dict[str, Any], group_name: str, observed_at: str
) -> tuple[float, str]:
    if payload.get("success") is not True:
        raise ValueError("NewAPI pricing response was not successful")
    group_ratios = payload.get("group_ratio")
    if not isinstance(group_ratios, dict) or group_name not in group_ratios:
        raise ValueError(f"NewAPI pricing response has no group: {group_name}")
    return (
        _nonnegative_number(group_ratios[group_name], "NewAPI group rate multiplier"),
        observed_at,
    )


def _rate_channel(
    state: AppState, site: SiteConfig, credential: SiteCredential
) -> ChannelConfig:
    protocol_config_id = credential.rate_protocol_config_id
    protocol_config = next(
        (item for item in site.protocols if item.id == protocol_config_id), None
    )
    if protocol_config is None or credential.id not in protocol_config.credential_ids:
        raise CredentialRateSyncError("Credential rate channel is no longer available")

    for channel in state.channel_store._flatten_site(site):
        if protocol_config_id_from_runtime_channel_id(channel.id) != protocol_config_id:
            continue
        target = _channel_for_credential(channel, credential.id)
        if target is not None and target.status == ChannelStatus.ENABLED:
            return target
    raise CredentialRateSyncError("Credential rate channel is disabled or unavailable")


async def _fetch_credential_rate(
    state: AppState, channel: ChannelConfig, credential: SiteCredential
) -> tuple[float, str]:
    runtime = await state.settings_repo.get_runtime_settings()
    proxy_url = resolve_upstream_proxy_url(channel, str(runtime["proxy_url"]))
    client = state.get_http_client(proxy_url)
    synced_at = datetime.now(UTC).isoformat()

    if credential.rate_source == "sub2api":
        api_key = resolve_channel_api_key(channel, credential.id)
        endpoint = resolve_sub2api_billing_url(str(channel.base_url))
        default_headers = {
            "Accept": "application/json",
            "Authorization": f"Bearer {api_key}",
            "x-api-key": api_key,
        }
    elif credential.rate_source == "newapi":
        endpoint = resolve_newapi_pricing_url(str(channel.base_url))
        default_headers = {"Accept": "application/json"}
    else:
        raise CredentialRateSyncError("Credential rate source is disabled")

    headers = build_upstream_headers(
        default_headers,
        channel.headers,
        user_agent=_default_lens_user_agent(),
        upstream_headers_config=runtime["upstream_headers_config"],
        context=request_rule_context(
            endpoint, model_name="", protocol=channel.protocol
        ),
    )
    try:
        response = await client.get(endpoint, headers=headers, timeout=30)
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, dict):
            raise TypeError("Credential rate response must be an object")
        if credential.rate_source == "sub2api":
            return _parse_sub2api_rate(payload)
        return _parse_newapi_rate(payload, credential.rate_group, synced_at)
    except httpx.HTTPStatusError as exc:
        detail = _format_http_response_error(exc.response)
        raise CredentialRateSyncError(
            f"Credential rate source returned HTTP {exc.response.status_code}: {detail}"
        ) from exc
    except httpx.HTTPError as exc:
        raise CredentialRateSyncError(
            f"Credential rate source request failed: {type(exc).__name__}"
        ) from exc
    except (TypeError, ValueError) as exc:
        raise CredentialRateSyncError(
            "Credential rate source returned invalid data"
        ) from exc


async def _sync_credential_rate_target(
    state: AppState, site: SiteConfig, credential: SiteCredential
) -> bool:
    try:
        multiplier, observed_at = await _fetch_credential_rate(
            state, _rate_channel(state, site, credential), credential
        )
    except CredentialRateSyncError as exc:
        recorded = await state.site_credential_rate_repo.record_failure(
            credential.id,
            str(exc),
            protocol_config_id=credential.rate_protocol_config_id,
            source=credential.rate_source,
            group_name=credential.rate_group,
        )
        if recorded:
            raise
        return False
    return await state.site_credential_rate_repo.record_success(
        credential.id,
        multiplier=multiplier,
        observed_at=observed_at,
        synced_at=datetime.now(UTC).isoformat(),
        protocol_config_id=credential.rate_protocol_config_id,
        source=credential.rate_source,
        group_name=credential.rate_group,
    )


async def sync_site_credential_rate(
    state: AppState, site_id: str, credential_id: str
) -> SiteCredential:
    site = await state.channel_store.get_site(site_id)
    credential = _site_credential(site, credential_id)
    if credential is None:
        raise KeyError(credential_id)
    if credential.rate_source == "none":
        raise CredentialRateNotConfiguredError("Credential rate source is disabled")
    recorded = await _sync_credential_rate_target(state, site, credential)
    refreshed = await state.channel_store.get_site(site_id)
    current = _site_credential(refreshed, credential_id)
    if current is None:
        raise KeyError(credential_id)
    if not recorded:
        raise CredentialRateConflictError(
            "Credential rate configuration changed during sync"
        )
    return current


async def sync_all_site_credential_rates(state: AppState) -> None:
    failures: list[str] = []
    for site in await state.channel_store.list_sites():
        if not site.enabled:
            continue
        for credential in site.credentials:
            if not credential.enabled or credential.rate_source == "none":
                continue
            try:
                await _sync_credential_rate_target(state, site, credential)
            except CredentialRateSyncError:
                failures.append(f"{site.name}/{credential.name}")
    if failures:
        raise CredentialRateSyncError(
            "Credential rate sync failed for: " + ", ".join(failures)
        )
