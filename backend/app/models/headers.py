def canonicalize_header_map(headers: dict[str, str]) -> dict[str, str]:
    canonical_headers: dict[str, str] = {}
    lower_to_key: dict[str, str] = {}
    for raw_key, raw_value in headers.items():
        key = str(raw_key).strip()
        if not key:
            continue
        lower_key = key.lower()
        existing_key = lower_to_key.get(lower_key)
        if existing_key is not None:
            canonical_headers.pop(existing_key, None)
        lower_to_key[lower_key] = key
        canonical_headers[key] = str(raw_value).strip()
    return canonical_headers
