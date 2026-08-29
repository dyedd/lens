from __future__ import annotations

import re

from httpx import URL

from .urls import append_url_path, canonicalize_base_url


def _remove_endpoint(parsed_url: URL, endpoint: str) -> URL:
    path = parsed_url.path.rstrip("/")
    if path.endswith(endpoint):
        path = path[: -len(endpoint)] or "/"
    return parsed_url.copy_with(path=path)


def resolve_sub2api_billing_url(base_url: str) -> str:
    """Build the Sub2API billing endpoint from an upstream base URL."""
    parsed_url = URL(canonicalize_base_url(base_url))
    path = parsed_url.path.rstrip("/")
    if path.endswith("/sub2api/billing"):
        return str(parsed_url.copy_with(path=path))
    root_url = _remove_endpoint(parsed_url, "/api/pricing")
    root_path = root_url.path.rstrip("/")
    path_parts = [part for part in root_path.split("/") if part]
    if path_parts and re.fullmatch(r"v\d+", path_parts[-1]):
        return append_url_path(str(root_url), "sub2api", "billing")
    return append_url_path(str(root_url), "v1", "sub2api", "billing")


def resolve_newapi_pricing_url(base_url: str) -> str:
    """Build the NewAPI pricing endpoint from an upstream base URL."""
    parsed_url = URL(canonicalize_base_url(base_url))
    path = parsed_url.path.rstrip("/")
    if path.endswith("/api/pricing"):
        return str(parsed_url.copy_with(path=path))
    root_url = _remove_endpoint(parsed_url, "/sub2api/billing")
    root_path = root_url.path.rstrip("/")
    path_parts = [part for part in root_path.split("/") if part]
    if path_parts and re.fullmatch(r"v\d+", path_parts[-1]):
        root_url = root_url.copy_with(path="/" + "/".join(path_parts[:-1]))
    return append_url_path(str(root_url), "api", "pricing")
