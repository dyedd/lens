from typing import Any, Literal


def parse_legacy_credential_scopes(
    payload: Any, *, reference_field: Literal["id", "ref"] = "id"
) -> Any:
    """在站点输入边界把旧共享规则转换为明确的地址范围。"""
    if not isinstance(payload, dict):
        return payload
    credentials = payload.get("credentials", [])
    addresses = payload.get("base_urls", [])
    if (
        not isinstance(credentials, list)
        or not credentials
        or not all(isinstance(item, dict) for item in credentials)
        or not isinstance(addresses, list)
        or not all(isinstance(item, dict) for item in addresses)
    ):
        return payload
    scope_field = f"base_url_{reference_field}s"
    legacy_field = f"base_url_{reference_field}"
    if any(scope_field in item for item in credentials):
        if any(scope_field not in item or legacy_field in item for item in credentials):
            raise ValueError(f"Use {scope_field} for every credential")
        return payload

    bindings: list[str] = []
    for credential in credentials:
        bound = credential.get(legacy_field, "")
        if not isinstance(bound, str):
            raise ValueError(f"{legacy_field} must be a string")
        bindings.append(bound.strip())
    owned = set(bindings) - {""}
    business_addresses = [
        item[reference_field]
        for item in addresses
        if item.get(reference_field) and item.get("kind") != "models"
    ]
    shared = [address for address in business_addresses if address not in owned]
    catalog = next(
        (
            item[reference_field]
            for item in addresses
            if item.get(reference_field) and item.get("kind") == "models"
        ),
        None,
    )
    converted: list[dict[str, Any]] = []
    for credential, bound in zip(credentials, bindings, strict=True):
        scope = [bound] if bound else list(shared)
        if catalog and any(address in business_addresses for address in scope):
            scope.append(catalog)
        converted.append(
            {
                **{
                    key: value
                    for key, value in credential.items()
                    if key != legacy_field
                },
                scope_field: list(dict.fromkeys(scope)),
            }
        )
    return {**payload, "credentials": converted}
