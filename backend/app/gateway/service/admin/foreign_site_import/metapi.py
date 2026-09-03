from __future__ import annotations

import json
from typing import Any

from .....models.protocols import ChannelProxyMode, ProtocolKind
from .....models.site_import import (
    SiteImportBaseUrlInput,
    SiteImportCredentialInput,
    SiteImportItem,
    SiteImportModelInput,
    SiteImportProtocolInput,
)
from .....models.upstream_rules import HeaderRule
from .parsed import ParsedForeignSites

_PLATFORM_PROTOCOLS: dict[str, ProtocolKind] = {
    "openai": ProtocolKind.OPENAI_CHAT,
    "claude": ProtocolKind.ANTHROPIC,
    "gemini": ProtocolKind.GEMINI,
    "gemini-cli": ProtocolKind.GEMINI,
    "codex": ProtocolKind.OPENAI_RESPONSES,
}
_DEFAULT_PROTOCOL = ProtocolKind.OPENAI_CHAT

_METAPI_ROW_SECTIONS = (
    "sites",
    "siteApiEndpoints",
    "accounts",
    "accountTokens",
    "manualModels",
    "routeChannels",
)


def parse_metapi_sites(payload: dict[str, Any]) -> ParsedForeignSites:
    """Convert a metapi backup (version 2 accounts section) into Lens sites."""
    parsed = ParsedForeignSites()
    accounts_section = payload.get("accounts")
    if not isinstance(accounts_section, dict):
        parsed.warn("metapi backup has no accounts section")
        return parsed

    rows = {key: _as_rows(accounts_section.get(key)) for key in _METAPI_ROW_SECTIONS}
    endpoints_by_site = _group_by(rows["siteApiEndpoints"], "siteId")
    accounts_by_site = _group_by(rows["accounts"], "siteId")
    tokens_by_account = _group_by(rows["accountTokens"], "accountId")
    models_by_site = _collect_site_models(rows["accounts"], rows)

    for site in rows["sites"]:
        site_id = site.get("id")
        name = str(site.get("name") or "").strip()
        if not name:
            parsed.skip(f"site #{site_id}", "missing name")
            continue

        primary_url = str(site.get("url") or "").strip()
        if not primary_url:
            parsed.skip(name, "missing base URL")
            continue

        credentials = _build_credentials(
            site,
            accounts_by_site.get(site_id, []),
            tokens_by_account,
        )
        if not credentials:
            parsed.skip(name, "no API keys (session-only accounts)")
            continue

        base_urls = _build_base_urls(primary_url, endpoints_by_site.get(site_id, []))
        headers, header_warning = _parse_custom_headers(site.get("customHeaders"))
        platform = _site_platform(site)
        try:
            parsed.sites.append(
                SiteImportItem(
                    name=name,
                    enabled=site.get("status") != "disabled",
                    tags=[platform] if platform else [],
                    base_urls=base_urls,
                    credentials=credentials,
                    protocols=[
                        _build_protocol_config(
                            site,
                            base_url_ref=base_urls[0].ref,
                            credential_refs=[
                                credential.ref for credential in credentials
                            ],
                            model_names=models_by_site.get(site_id, []),
                            headers=headers,
                        )
                    ],
                )
            )
        except ValueError as exc:
            parsed.skip(name, f"invalid site data ({exc})")
            continue
        if header_warning:
            parsed.warn(f"{name}: {header_warning}")
    return parsed


def _site_platform(site: dict[str, Any]) -> str:
    return str(site.get("platform") or "").strip()


def _site_protocol(site: dict[str, Any]) -> ProtocolKind:
    return _PLATFORM_PROTOCOLS.get(_site_platform(site), _DEFAULT_PROTOCOL)


def _as_rows(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [row for row in value if isinstance(row, dict)]


def _group_by(
    rows: list[dict[str, Any]],
    key: str,
) -> dict[Any, list[dict[str, Any]]]:
    grouped: dict[Any, list[dict[str, Any]]] = {}
    for row in rows:
        grouped.setdefault(row.get(key), []).append(row)
    return grouped


def _collect_site_models(
    accounts: list[dict[str, Any]],
    rows: dict[str, list[dict[str, Any]]],
) -> dict[Any, list[str]]:
    site_by_account = {account.get("id"): account.get("siteId") for account in accounts}
    models_by_site: dict[Any, list[str]] = {}
    for manual_model in rows["manualModels"]:
        model_name = str(manual_model.get("modelName") or "").strip()
        site_id = site_by_account.get(manual_model.get("accountId"))
        if model_name and site_id is not None:
            models_by_site.setdefault(site_id, []).append(model_name)
    for channel in rows["routeChannels"]:
        model_name = str(channel.get("sourceModel") or "").strip()
        if not model_name or any(wildcard in model_name for wildcard in "*?[]"):
            continue
        site_id = site_by_account.get(channel.get("accountId"))
        if site_id is not None:
            models_by_site.setdefault(site_id, []).append(model_name)
    return {
        site_id: list(dict.fromkeys(names)) for site_id, names in models_by_site.items()
    }


def _build_base_urls(
    primary_url: str,
    endpoints: list[dict[str, Any]],
) -> list[SiteImportBaseUrlInput]:
    base_urls = [SiteImportBaseUrlInput(ref="u0", url=primary_url)]
    for index, endpoint in enumerate(endpoints, start=1):
        url = str(endpoint.get("url") or "").strip()
        if not url or not endpoint.get("enabled", True):
            continue
        base_urls.append(SiteImportBaseUrlInput(ref=f"u{index}", url=url))
    return base_urls


def _build_credentials(
    site: dict[str, Any],
    accounts: list[dict[str, Any]],
    tokens_by_account: dict[Any, list[dict[str, Any]]],
) -> list[SiteImportCredentialInput]:
    credentials: list[SiteImportCredentialInput] = []
    seen_token_values: set[str] = set()
    used_names: set[str] = set()

    def _unique_name(candidate: str) -> str:
        name = candidate or f"Key {len(used_names) + 1}"
        suffix = 2
        while name.lower() in used_names:
            name = f"{candidate or 'Key'} {suffix}"
            suffix += 1
        used_names.add(name.lower())
        return name

    site_api_key = str(site.get("apiKey") or "").strip()
    if site_api_key:
        credentials.append(
            SiteImportCredentialInput(
                ref="c-site",
                name=_unique_name("Site key"),
                api_key=site_api_key,
            )
        )

    for account in accounts:
        is_account_active = account.get("status") != "disabled"
        for token in tokens_by_account.get(account.get("id"), []):
            token_value = str(token.get("token") or "").strip()
            if (
                not token_value
                or not token.get("enabled", True)
                or not is_account_active
                or token_value in seen_token_values
            ):
                continue
            seen_token_values.add(token_value)
            candidate_name = str(
                token.get("name") or account.get("username") or ""
            ).strip()
            credentials.append(
                SiteImportCredentialInput(
                    ref=f"c-{token.get('id')}",
                    name=_unique_name(candidate_name),
                    api_key=token_value,
                    enabled=is_account_active,
                )
            )
    return credentials


def _parse_custom_headers(custom_headers: Any) -> tuple[list[HeaderRule], str]:
    if not isinstance(custom_headers, str) or not custom_headers.strip():
        return [], ""
    try:
        raw_headers = json.loads(custom_headers)
    except json.JSONDecodeError:
        return [], "custom headers ignored (invalid JSON)"
    if not isinstance(raw_headers, dict):
        return [], "custom headers ignored (invalid JSON)"
    headers = [
        HeaderRule(name=str(key), action="override", value=str(value))
        for key, value in raw_headers.items()
        if str(key).strip()
    ]
    return headers, ""


def _build_protocol_config(
    site: dict[str, Any],
    base_url_ref: str,
    credential_refs: list[str],
    model_names: list[str],
    headers: list[HeaderRule],
) -> SiteImportProtocolInput:
    protocol = _site_protocol(site)
    proxy_url = str(site.get("proxyUrl") or "").strip()
    return SiteImportProtocolInput(
        name=protocol.value,
        protocol=protocol,
        headers=headers,
        proxy_mode=ChannelProxyMode.CUSTOM if proxy_url else ChannelProxyMode.INHERIT,
        channel_proxy=proxy_url,
        base_url_ref=base_url_ref,
        credential_refs=credential_refs,
        models=[
            SiteImportModelInput(
                model_name=model_name, credential_ref=credential_refs[0]
            )
            for model_name in model_names
        ],
    )
