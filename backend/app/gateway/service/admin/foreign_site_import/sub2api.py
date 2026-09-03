from __future__ import annotations

from typing import Any
from urllib.parse import quote

from .....models.protocols import ChannelProxyMode, ProtocolKind
from .....models.site_import import (
    SiteImportBaseUrlInput,
    SiteImportCredentialInput,
    SiteImportItem,
    SiteImportProtocolInput,
)
from .parsed import ParsedForeignSites

_PLATFORM_PROTOCOLS: dict[str, ProtocolKind] = {
    "anthropic": ProtocolKind.ANTHROPIC,
    "openai": ProtocolKind.OPENAI_CHAT,
    "gemini": ProtocolKind.GEMINI,
    "kimi": ProtocolKind.OPENAI_CHAT,
    "zhipu": ProtocolKind.OPENAI_CHAT,
    "deepseek": ProtocolKind.OPENAI_CHAT,
    "grok": ProtocolKind.OPENAI_CHAT,
    "antigravity": ProtocolKind.GEMINI,
}
_API_PROTOCOL_OVERRIDES: dict[str, ProtocolKind] = {
    "chat_completions": ProtocolKind.OPENAI_CHAT,
    "anthropic": ProtocolKind.ANTHROPIC,
    "responses": ProtocolKind.OPENAI_RESPONSES,
}
_PLATFORM_DEFAULT_BASE_URLS: dict[str, str] = {
    "anthropic": "https://api.anthropic.com",
    "openai": "https://api.openai.com",
    "gemini": "https://generativelanguage.googleapis.com",
    "kimi": "https://api.moonshot.cn",
    "zhipu": "https://open.bigmodel.cn",
    "deepseek": "https://api.deepseek.com",
    "grok": "https://api.x.ai",
}


def parse_sub2api_sites(payload: dict[str, Any]) -> ParsedForeignSites:
    """Convert a sub2api data export (accounts + proxies) into Lens sites."""
    parsed = ParsedForeignSites()
    proxies = _build_proxy_urls(payload.get("proxies"))

    for account in _as_rows(payload.get("accounts")):
        name = str(account.get("name") or "").strip()
        if not name:
            parsed.skip("unnamed account", "missing name")
            continue

        platform = str(account.get("platform") or "").strip().lower()
        account_type = str(account.get("type") or "").strip().lower()
        credentials = account.get("credentials")
        if not isinstance(credentials, dict):
            credentials = {}

        if account_type == "oauth":
            parsed.skip(name, "OAuth session credentials cannot be imported")
            continue
        api_key = _extract_api_key(account_type, credentials)
        if not api_key:
            parsed.skip(name, f"missing API key ({account_type or 'unknown'} account)")
            continue

        base_url = _credential_text(credentials.get("base_url")) or (
            _PLATFORM_DEFAULT_BASE_URLS.get(platform, "")
        )
        if not base_url:
            parsed.skip(name, f"no base URL for platform {platform or 'unknown'}")
            continue

        protocol = _API_PROTOCOL_OVERRIDES.get(
            _credential_text(credentials.get("api_protocol")),
        ) or _PLATFORM_PROTOCOLS.get(platform, ProtocolKind.OPENAI_CHAT)
        try:
            parsed.sites.append(
                SiteImportItem(
                    name=name,
                    enabled=True,
                    tags=[platform] if platform else [],
                    base_urls=[_base_url_input(base_url)],
                    credentials=[
                        SiteImportCredentialInput(
                            ref="c0", name="API key", api_key=api_key
                        )
                    ],
                    protocols=[
                        _protocol_config(
                            protocol,
                            proxy_url=proxies.get(
                                _credential_text(account.get("proxy_key")), ""
                            ),
                        )
                    ],
                )
            )
        except ValueError as exc:
            parsed.skip(name, f"invalid account data ({exc})")
    return parsed


def _as_rows(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [row for row in value if isinstance(row, dict)]


def _credential_text(value: Any) -> str:
    return str(value).strip() if value is not None else ""


def _extract_api_key(account_type: str, credentials: dict[str, Any]) -> str:
    if account_type == "setup-token":
        return _credential_text(
            credentials.get("token") or credentials.get("access_token")
        )
    return _credential_text(credentials.get("api_key"))


def _base_url_input(url: str) -> SiteImportBaseUrlInput:
    return SiteImportBaseUrlInput(ref="u0", url=url)


def _protocol_config(
    protocol: ProtocolKind,
    proxy_url: str,
) -> SiteImportProtocolInput:
    return SiteImportProtocolInput(
        name=protocol.value,
        protocol=protocol,
        proxy_mode=ChannelProxyMode.CUSTOM if proxy_url else ChannelProxyMode.INHERIT,
        channel_proxy=proxy_url,
        base_url_ref="u0",
        credential_refs=["c0"],
    )


def _build_proxy_urls(proxies: Any) -> dict[str, str]:
    urls: dict[str, str] = {}
    for proxy in _as_rows(proxies):
        host = _credential_text(proxy.get("host"))
        port = proxy.get("port")
        scheme = _credential_text(proxy.get("protocol")) or "http"
        if not host or not isinstance(port, int):
            continue
        authority = f"{host}:{port}"
        username = _credential_text(proxy.get("username"))
        password = _credential_text(proxy.get("password"))
        if username:
            authority = (
                f"{quote(username, safe='')}:{quote(password, safe='')}@{authority}"
            )
        urls[_credential_text(proxy.get("proxy_key"))] = f"{scheme}://{authority}"
    return urls
