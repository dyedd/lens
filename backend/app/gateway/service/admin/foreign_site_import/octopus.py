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
from .....models.upstream_rules import HeaderRule, ParamOverrideRule
from .parsed import ParsedForeignSites

# 协议位与 octopus 的 Protocol 位掩码一致, 落库且不可再变更。
_PROTOCOL_BITS: dict[int, ProtocolKind] = {
    1 << 1: ProtocolKind.OPENAI_CHAT,
    1 << 2: ProtocolKind.OPENAI_RESPONSES,
    1 << 3: ProtocolKind.ANTHROPIC,
}


def parse_octopus_sites(payload: dict[str, Any]) -> ParsedForeignSites:
    """Convert an octopus DB dump (version 5 channel/grant tables) into Lens sites."""
    parsed = ParsedForeignSites()
    channels = _rows(payload.get("channels"))
    if not channels:
        parsed.warn("octopus backup has no channels")
        return parsed

    keys_by_channel = _group_by(_rows(payload.get("channel_keys")), "channel_id")
    models_by_channel = _group_by(_rows(payload.get("channel_models")), "channel_id")
    grants_by_model = _group_by(
        _rows(payload.get("channel_grants")), "channel_model_id"
    )

    for channel in channels:
        channel_id = channel.get("id")
        name = str(channel.get("name") or "").strip()
        if not name:
            parsed.skip(f"channel #{channel_id}", "missing name")
            continue
        base_url = str(channel.get("base_url") or "").strip()
        if not base_url:
            parsed.skip(name, "missing base URL")
            continue
        credentials = _build_credentials(keys_by_channel.get(channel_id, []))
        if not credentials:
            parsed.skip(name, "no API keys")
            continue
        proxy_url = str(channel.get("channel_proxy") or "").strip()

        channel_models = models_by_channel.get(channel_id, [])
        model_names = [
            model_name
            for model_name in (
                str(model.get("name") or "").strip() for model in channel_models
            )
            if model_name
        ]
        try:
            parsed.sites.append(
                SiteImportItem(
                    name=name,
                    enabled=bool(channel.get("enabled", True)),
                    base_urls=[SiteImportBaseUrlInput(ref="u0", url=base_url)],
                    credentials=credentials,
                    protocols=[
                        SiteImportProtocolInput(
                            name=protocol.value,
                            protocol=protocol,
                            headers=_parse_custom_headers(channel.get("custom_header")),
                            param_override=_parse_param_override(
                                channel.get("param_override")
                            ),
                            proxy_mode=ChannelProxyMode.CUSTOM
                            if proxy_url
                            else ChannelProxyMode.INHERIT,
                            channel_proxy=proxy_url,
                            base_url_ref="u0",
                            credential_refs=[
                                credential.ref for credential in credentials
                            ],
                            models=[
                                SiteImportModelInput(
                                    model_name=model_name,
                                    credential_ref=credentials[0].ref,
                                )
                                for model_name in model_names
                            ],
                        )
                        for protocol in _channel_protocols(
                            channel_models, grants_by_model
                        )
                    ],
                )
            )
        except ValueError as exc:
            parsed.skip(name, f"invalid channel data ({exc})")
    return parsed


def _rows(section: Any) -> list[dict[str, Any]]:
    if not isinstance(section, list):
        return []
    return [row for row in section if isinstance(row, dict)]


def _group_by(
    rows: list[dict[str, Any]],
    key: str,
) -> dict[Any, list[dict[str, Any]]]:
    grouped: dict[Any, list[dict[str, Any]]] = {}
    for row in rows:
        grouped.setdefault(row.get(key), []).append(row)
    return grouped


def _build_credentials(keys: list[dict[str, Any]]) -> list[SiteImportCredentialInput]:
    credentials: list[SiteImportCredentialInput] = []
    used_names: set[str] = set()
    for index, key in enumerate(keys):
        api_key = str(key.get("key") or "").strip()
        if not api_key or not key.get("enabled", True):
            continue
        name = str(key.get("name") or "").strip() or f"Key {index + 1}"
        suffix = 2
        while name.lower() in used_names:
            name = f"{name} {suffix}"
            suffix += 1
        used_names.add(name.lower())
        credentials.append(
            SiteImportCredentialInput(
                ref=f"c{key.get('id', index)}",
                name=name,
                api_key=api_key,
            )
        )
    return credentials


def _channel_protocols(
    channel_models: list[dict[str, Any]],
    grants_by_model: dict[Any, list[dict[str, Any]]],
) -> list[ProtocolKind]:
    """Collect the protocols this channel actually serves via its grants."""
    protocols: list[ProtocolKind] = []
    for model_id in {model.get("id") for model in channel_models}:
        for grant in grants_by_model.get(model_id, []):
            bits = grant.get("protocols")
            if not isinstance(bits, int):
                continue
            for bit, protocol in _PROTOCOL_BITS.items():
                if bits & bit and protocol not in protocols:
                    protocols.append(protocol)
    return protocols


def _parse_custom_headers(raw: Any) -> list[HeaderRule]:
    if not isinstance(raw, list):
        return []
    headers: list[HeaderRule] = []
    for header in raw:
        if not isinstance(header, dict):
            continue
        name = str(header.get("header_key") or "").strip()
        value = str(header.get("header_value") or "")
        if not name or not value:
            continue
        headers.append(HeaderRule(name=name, action="override", value=value))
    return headers


def _parse_param_override(raw: Any) -> list[ParamOverrideRule]:
    if not isinstance(raw, str) or not raw.strip():
        return []
    try:
        overrides = json.loads(raw)
    except json.JSONDecodeError:
        return []
    if not isinstance(overrides, dict):
        return []
    rules: list[ParamOverrideRule] = []
    for key, value in overrides.items():
        path = str(key).strip()
        if not path or path in {"model", "stream"}:
            continue
        rules.append(ParamOverrideRule(path=path, action="set", value=value))
    return rules
