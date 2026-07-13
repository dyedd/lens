from urllib.parse import urlencode, urlsplit, urlunsplit


def normalize_base_url(value: str) -> str:
    """Normalize an upstream base URL by removing API version suffixes."""
    text = str(value).strip()
    parsed = urlsplit(text)
    path = parsed.path.rstrip("/")

    if path.endswith("/v1beta"):
        path = path[:-7]
    elif path.endswith("/v1"):
        path = path[:-3]

    return _urlunsplit_preserving_empty_components(
        text,
        parsed.scheme,
        parsed.netloc,
        path,
        parsed.query,
        parsed.fragment,
    )


def append_url_path(
    base_url: str,
    *segments: str,
    query_params: dict[str, str] | None = None,
) -> str:
    """Append path segments and query parameters to a base URL."""
    parsed = urlsplit(base_url)
    path_parts = [parsed.path.rstrip("/")]
    path_parts.extend(segment.strip("/") for segment in segments if segment.strip("/"))
    path = "/".join(part for part in path_parts if part)

    if parsed.path.startswith("/") and not path.startswith("/"):
        path = f"/{path}"
    if not path:
        path = parsed.path

    query = parsed.query
    if query_params:
        encoded_params = urlencode(query_params)
        query = f"{query}&{encoded_params}" if query else encoded_params

    return _urlunsplit_preserving_empty_components(
        base_url,
        parsed.scheme,
        parsed.netloc,
        path,
        query,
        parsed.fragment,
    )


def _urlunsplit_preserving_empty_components(
    source: str,
    scheme: str,
    netloc: str,
    path: str,
    query: str,
    fragment: str,
) -> str:
    rebuilt = urlunsplit((scheme, netloc, path, query, fragment))
    before_fragment, fragment_separator, _ = source.partition("#")
    has_empty_query = "?" in before_fragment and query == ""
    has_empty_fragment = bool(fragment_separator) and fragment == ""

    if has_empty_query:
        if "#" in rebuilt:
            rebuilt = rebuilt.replace("#", "?#", 1)
        else:
            rebuilt += "?"
    if has_empty_fragment and "#" not in rebuilt:
        rebuilt += "#"

    return rebuilt
