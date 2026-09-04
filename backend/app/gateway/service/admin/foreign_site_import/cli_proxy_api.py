from __future__ import annotations

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

# 各 key 段一个站点: 段名即 Lens 协议 (openai-compatibility 段是第三方 openai 兼容)。
# openai-compatibility 排在最前: 它是配置里最主要的第三方供应商, 预览列表从它开始读。
_PROVIDER_PROTOCOLS: dict[str, ProtocolKind] = {
    "openai-compatibility": ProtocolKind.OPENAI_CHAT,
    "claude-api-key": ProtocolKind.ANTHROPIC,
    "gemini-api-key": ProtocolKind.GEMINI,
    "codex-api-key": ProtocolKind.OPENAI_RESPONSES,
    "xai-api-key": ProtocolKind.OPENAI_RESPONSES,
    "vertex-api-key": ProtocolKind.GEMINI,
}

# anthropic 与 gemini 的 key 允许省略 base-url, 兜底到官方端点。
_PROVIDER_DEFAULT_BASE_URLS = {
    ProtocolKind.ANTHROPIC: "https://api.anthropic.com",
    ProtocolKind.GEMINI: "https://generativelanguage.googleapis.com",
}


def parse_cli_proxy_api_sites(payload: dict[str, Any]) -> ParsedForeignSites:
    """Convert a CLIProxyAPI config.yaml provider sections into Lens sites."""
    parsed = ParsedForeignSites()
    for section, protocol in _PROVIDER_PROTOCOLS.items():
        rows = payload.get(section)
        if not isinstance(rows, list):
            continue
        for index, row in enumerate(rows):
            if isinstance(row, dict):
                _append_provider_site(parsed, section, index, row, protocol)
    return parsed


def _append_provider_site(
    parsed: ParsedForeignSites,
    section: str,
    index: int,
    row: dict[str, Any],
    protocol: ProtocolKind,
) -> None:
    name = _provider_name(section, index, row)
    api_keys = _provider_api_keys(row)
    if not api_keys:
        parsed.skip(name, "missing api-key")
        return

    base_url = str(row.get("base-url") or "").strip() or (
        _PROVIDER_DEFAULT_BASE_URLS.get(protocol, "")
    )
    if not base_url:
        parsed.skip(name, "missing base-url")
        return

    headers = _provider_headers(row.get("headers"))
    proxy_url = _proxy_url(row) or _proxy_url(api_keys[0])
    models = _provider_models(row)
    key_count = len(api_keys)

    try:
        parsed.sites.append(
            SiteImportItem(
                name=name,
                enabled=not row.get("disabled", False),
                base_urls=[SiteImportBaseUrlInput(ref="u0", url=base_url)],
                credentials=[
                    SiteImportCredentialInput(
                        ref=f"c{key_index}",
                        name=f"Key {key_index + 1}",
                        api_key=api_keys[key_index]["api-key"],
                    )
                    for key_index in range(key_count)
                ],
                protocols=[
                    SiteImportProtocolInput(
                        name=protocol.value,
                        protocol=protocol,
                        headers=headers,
                        proxy_mode=ChannelProxyMode.CUSTOM
                        if proxy_url
                        else ChannelProxyMode.INHERIT,
                        channel_proxy=proxy_url,
                        base_url_ref="u0",
                        credential_refs=[
                            f"c{key_index}" for key_index in range(key_count)
                        ],
                        models=models,
                    )
                ],
            )
        )
    except ValueError as exc:
        parsed.skip(name, f"invalid provider data ({exc})")


def _provider_api_keys(row: dict[str, Any]) -> list[dict[str, Any]]:
    """Key rows per section: openai-compatibility nests them in api-key-entries."""
    raw_entries = row.get("api-key-entries")
    if not isinstance(raw_entries, list):
        single = str(row.get("api-key") or "").strip()
        return [{"api-key": single}] if single else []
    return [entry for entry in raw_entries if isinstance(entry, dict)]


def _provider_name(section: str, index: int, row: dict[str, Any]) -> str:
    if section == "openai-compatibility":
        return str(row.get("name") or "").strip() or f"openai-compatibility {index + 1}"
    return f"{section.removesuffix('-api-key')} {index + 1}"


def _provider_headers(raw: Any) -> list[HeaderRule]:
    if not isinstance(raw, dict):
        return []
    headers: list[HeaderRule] = []
    for key, value in raw.items():
        name = str(key).strip()
        value_text = str(value or "")
        if not name or value_text.startswith("$") or not value_text:
            continue
        headers.append(HeaderRule(name=name, action="override", value=value_text))
    return headers


def _proxy_url(row: dict[str, Any]) -> str:
    proxy_url = str(row.get("proxy-url") or "").strip()
    if not proxy_url or proxy_url in {"direct", "none"}:
        return ""
    return proxy_url


def _provider_models(row: dict[str, Any]) -> list[SiteImportModelInput]:
    models: list[SiteImportModelInput] = []
    for raw_model in row.get("models") or []:
        if not isinstance(raw_model, dict):
            continue
        model_name = str(raw_model.get("name") or "").strip()
        if model_name:
            models.append(
                SiteImportModelInput(model_name=model_name, credential_ref="c0")
            )
    return models
