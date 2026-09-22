from collections.abc import Sequence


def credential_ids_for_url(
    credentials: Sequence[tuple[str, str]],
    url_id: str,
) -> list[str]:
    """Return credential ids bound to a URL.

    Credentials with a matching base_url_id are owned by that URL. Otherwise the
    URL uses shared credentials (empty base_url_id).
    """
    owned = [
        credential_id
        for credential_id, bound_url_id in credentials
        if bound_url_id == url_id
    ]
    if owned:
        return list(dict.fromkeys(owned))
    return [
        credential_id for credential_id, bound_url_id in credentials if not bound_url_id
    ]
