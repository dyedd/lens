from __future__ import annotations

from typing import Any

from .....models.protocols import ProtocolKind
from .....models.site_import import (
    SiteImportBaseUrlInput,
    SiteImportCredentialInput,
    SiteImportItem,
    SiteImportProtocolInput,
)
from .parsed import ParsedForeignSites

_API_TYPE_PROTOCOLS: dict[str, ProtocolKind] = {
    "anthropic": ProtocolKind.ANTHROPIC,
    "google": ProtocolKind.GEMINI,
}


def parse_all_api_hub_sites(payload: dict[str, Any]) -> ParsedForeignSites:
    """Convert an all-api-hub backup (API credential profiles) into Lens sites."""
    parsed = ParsedForeignSites()
    tag_names = _collect_tag_names(payload.get("tagStore"))
    profiles = _profile_rows(payload.get("apiCredentialProfiles"))

    for profile in profiles:
        name = str(profile.get("name") or "").strip()
        if not name:
            parsed.skip("unnamed credential profile", "missing name")
            continue
        base_url = str(profile.get("baseUrl") or "").strip()
        if not base_url:
            parsed.skip(name, "missing base URL")
            continue
        api_key = str(profile.get("apiKey") or "").strip()
        if not api_key:
            parsed.skip(name, "missing API key")
            continue

        api_type = str(profile.get("apiType") or "").strip().lower()
        protocol = _API_TYPE_PROTOCOLS.get(api_type, ProtocolKind.OPENAI_CHAT)
        try:
            parsed.sites.append(
                SiteImportItem(
                    name=name,
                    enabled=True,
                    tags=_profile_tags(profile.get("tagIds"), tag_names),
                    base_urls=[SiteImportBaseUrlInput(ref="u0", url=base_url)],
                    credentials=[
                        SiteImportCredentialInput(
                            ref="c0", name="API key", api_key=api_key
                        )
                    ],
                    protocols=[
                        SiteImportProtocolInput(
                            name=protocol.value,
                            protocol=protocol,
                            base_url_ref="u0",
                            credential_refs=["c0"],
                        )
                    ],
                )
            )
        except ValueError as exc:
            parsed.skip(name, f"invalid profile data ({exc})")

    dashboard_accounts = _dashboard_account_count(payload.get("accounts"))
    if dashboard_accounts:
        parsed.warn(
            f"{dashboard_accounts} dashboard site accounts skipped "
            "(browser session credentials, no model API keys)"
        )
    return parsed


def _profile_rows(section: Any) -> list[dict[str, Any]]:
    if not isinstance(section, dict) or not isinstance(section.get("profiles"), list):
        return []
    return [row for row in section["profiles"] if isinstance(row, dict)]


def _collect_tag_names(tag_store: Any) -> dict[str, str]:
    if not isinstance(tag_store, dict) or not isinstance(
        tag_store.get("tagsById"), dict
    ):
        return {}
    names: dict[str, str] = {}
    for tag_id, tag in tag_store["tagsById"].items():
        if isinstance(tag, dict) and str(tag.get("name") or "").strip():
            names[str(tag_id)] = str(tag["name"]).strip()
    return names


def _profile_tags(tag_ids: Any, tag_names: dict[str, str]) -> list[str]:
    if not isinstance(tag_ids, list):
        return []
    tags: list[str] = []
    for tag_id in tag_ids:
        name = tag_names.get(str(tag_id))
        if name and name not in tags:
            tags.append(name)
    return tags


def _dashboard_account_count(accounts_section: Any) -> int:
    if isinstance(accounts_section, dict):
        accounts = accounts_section.get("accounts")
    else:
        accounts = accounts_section
    if not isinstance(accounts, list):
        return 0
    return sum(isinstance(account, dict) for account in accounts)
