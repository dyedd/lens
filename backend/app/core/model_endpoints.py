from collections.abc import Sequence


def credential_ids_for_url(
    credentials: Sequence[tuple[str, list[str] | None]],
    url_id: str,
) -> list[str]:
    return [
        credential_id
        for credential_id, scope in credentials
        if scope is None or url_id in scope
    ]
