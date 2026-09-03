from __future__ import annotations

import csv
import io
import json
import re
from typing import Any

from .....models.protocols import ProtocolKind
from .....models.site_import import (
    SiteImportBaseUrlInput,
    SiteImportCredentialInput,
    SiteImportItem,
    SiteImportModelInput,
    SiteImportProtocolInput,
)
from .parsed import ParsedForeignSites

_URL_PROTOCOLS: dict[str, ProtocolKind] = {
    "anthropic": ProtocolKind.ANTHROPIC,
    "openai": ProtocolKind.OPENAI_CHAT,
    "codex": ProtocolKind.OPENAI_RESPONSES,
    "gemini": ProtocolKind.GEMINI,
}
_DEFAULT_PROTOCOLS = [ProtocolKind.OPENAI_CHAT, ProtocolKind.ANTHROPIC]
_MODEL_SEPARATORS = re.compile(r"[,;|\n\t]+")
_TRUE_VALUES = {"true", "1", "yes", "y", "on", "enabled", "启用"}


def parse_ccload_sites(text: str) -> ParsedForeignSites:
    """Convert a ccLoad channel CSV export into Lens sites."""
    parsed = ParsedForeignSites()
    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames:
        parsed.warn("CSV file has no header row")
        return parsed
    reader.fieldnames = [name.strip().lower() for name in reader.fieldnames]

    warned_about_redirects = False
    defaulted_protocol_sites = 0
    for line_number, row in enumerate(reader, start=2):
        name = (row.get("name") or "").strip()
        if not name:
            parsed.skip(f"row {line_number}", "missing name")
            continue
        if (row.get("auth_type") or "api_key").strip() not in ("", "api_key"):
            parsed.skip(name, "OAuth channels are not importable")
            continue

        urls = _parse_urls(row.get("urls"))
        if not urls:
            parsed.skip(name, "no usable base URLs")
            continue
        api_keys = [
            key.strip() for key in (row.get("api_key") or "").split(",") if key.strip()
        ]
        if not api_keys:
            parsed.skip(name, "no API keys")
            continue
        model_names = list(
            dict.fromkeys(
                name.strip()
                for name in _MODEL_SEPARATORS.split(row.get("models") or "")
                if name.strip()
            )
        )
        if row.get("model_redirects") and not warned_about_redirects:
            warned_about_redirects = True
            parsed.warn("ccLoad model redirects are not migrated")
        protocols = _declared_protocols(urls)
        if not protocols:
            defaulted_protocol_sites += 1
            protocols = list(_DEFAULT_PROTOCOLS)

        try:
            parsed.sites.append(
                _build_site(name, row, urls, api_keys, model_names, protocols)
            )
        except ValueError as exc:
            parsed.skip(name, f"invalid row data ({exc})")

    if defaulted_protocol_sites:
        parsed.warn(
            "channels without declared URL protocols default to "
            "openai chat and anthropic"
        )
    return parsed


def _parse_urls(raw: Any) -> list[dict[str, Any]]:
    try:
        urls = json.loads(raw) if isinstance(raw, str) else None
    except json.JSONDecodeError:
        return []
    if not isinstance(urls, list):
        return []
    return [
        url
        for url in urls
        if isinstance(url, dict) and str(url.get("url") or "").strip()
    ]


def _build_site(
    name: str,
    row: dict[str, str],
    urls: list[dict[str, Any]],
    api_keys: list[str],
    model_names: list[str],
    protocols: list[ProtocolKind],
) -> SiteImportItem:
    base_urls = [
        SiteImportBaseUrlInput(ref=f"u{index}", url=str(url["url"]).strip())
        for index, url in enumerate(urls)
    ]
    credentials = [
        SiteImportCredentialInput(ref=f"c{index}", name=f"Key {index + 1}", api_key=key)
        for index, key in enumerate(api_keys)
    ]
    protocol_configs = [
        SiteImportProtocolInput(
            name=protocol.value,
            protocol=protocol,
            base_url_ref=_first_url_ref_for(urls, protocol),
            credential_refs=[credential.ref for credential in credentials],
            models=[
                SiteImportModelInput(
                    model_name=model_name, credential_ref=credentials[0].ref
                )
                for model_name in model_names
            ],
        )
        for protocol in protocols
    ]
    return SiteImportItem(
        name=name,
        enabled=_parse_bool(row.get("enabled"), default=True),
        base_urls=base_urls,
        credentials=credentials,
        protocols=protocol_configs,
    )


def _declared_protocols(urls: list[dict[str, Any]]) -> list[ProtocolKind]:
    declared: list[ProtocolKind] = []
    for url in urls:
        for entry in url.get("protocols") or []:
            protocol = _URL_PROTOCOLS.get(str(entry).strip().lower())
            if protocol and protocol not in declared:
                declared.append(protocol)
    return declared or list(_DEFAULT_PROTOCOLS)


def _first_url_ref_for(urls: list[dict[str, Any]], protocol: ProtocolKind) -> str:
    for index, url in enumerate(urls):
        declared = {
            _URL_PROTOCOLS.get(str(entry).strip().lower())
            for entry in url.get("protocols") or []
        }
        if protocol in declared:
            return f"u{index}"
    return "u0"


def _parse_bool(value: Any, default: bool) -> bool:
    if value is None or not str(value).strip():
        return default
    return str(value).strip().lower() in _TRUE_VALUES
