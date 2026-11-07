"""将密钥的地址绑定改为明确范围，保留原有可用出口。"""

import json
from collections import defaultdict

import sqlalchemy as sa
from alembic import op

revision = "e3a6c9f2b5d8"
down_revision = "d2f4a6b8c0e1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    connection = op.get_bind()
    addresses = _site_addresses(connection)
    credentials: dict[str, list[tuple[str, str]]] = defaultdict(list)
    credential_sites: dict[str, str] = {}
    for row in connection.execute(
        sa.text("SELECT id, site_id, base_url_id FROM site_credentials")
    ).mappings():
        credentials[row["site_id"]].append((row["id"], row["base_url_id"]))
        credential_sites[row["id"]] = row["site_id"]
    scopes: dict[str, list[str]] = {}
    for site_id, keys in credentials.items():
        scopes.update(_legacy_scopes(addresses.get(site_id, []), keys))

    for row in connection.execute(
        sa.text("SELECT id, site_id, base_url_id FROM site_protocol_configs")
    ).mappings():
        if row["base_url_id"] not in {
            address for address, _kind in addresses.get(row["site_id"], [])
        }:
            raise RuntimeError(
                f"Protocol config references a missing address: {row['id']}"
            )

    for row in connection.execute(
        sa.text(
            "SELECT m.id, m.credential_id, p.base_url_id, p.site_id "
            "FROM site_discovered_models m LEFT JOIN site_protocol_configs p "
            "ON p.id = m.protocol_config_id"
        )
    ).mappings():
        if (
            row["credential_id"] not in credential_sites
            or credential_sites[row["credential_id"]] != row["site_id"]
            or row["base_url_id"] not in scopes[row["credential_id"]]
        ):
            raise RuntimeError(f"Model has an invalid credential address: {row['id']}")

    op.add_column(
        "site_credentials", sa.Column("base_url_ids_json", sa.Text(), nullable=True)
    )
    if scopes:
        connection.execute(
            sa.text(
                "UPDATE site_credentials SET base_url_ids_json = :scope WHERE id = :id"
            ),
            [{"id": key, "scope": json.dumps(scope)} for key, scope in scopes.items()],
        )
    with op.batch_alter_table("site_credentials") as batch:
        batch.drop_column("base_url_id")


def downgrade() -> None:
    connection = op.get_bind()
    addresses = _site_addresses(connection)
    scopes_by_site: dict[str, dict[str, set[str]]] = defaultdict(dict)
    for row in connection.execute(
        sa.text("SELECT id, site_id, base_url_ids_json FROM site_credentials")
    ).mappings():
        scope = (
            json.loads(row["base_url_ids_json"])
            if row["base_url_ids_json"] is not None
            else [address for address, _kind in addresses.get(row["site_id"], [])]
        )
        if not isinstance(scope, list) or any(
            not isinstance(item, str) for item in scope
        ):
            raise RuntimeError(f"Invalid credential scope: {row['id']}")
        scopes_by_site[row["site_id"]][row["id"]] = set(scope)

    bindings: dict[str, str] = {}
    for site_id, scopes in scopes_by_site.items():
        urls = addresses.get(site_id, [])
        owned_scopes = {
            url_id: set(_legacy_scopes(urls, [("key", url_id)])["key"])
            for url_id, _kind in urls
        }
        for shared in [*scopes.values(), set()]:
            candidate: list[tuple[str, str]] = []
            for key, scope in scopes.items():
                if scope == shared:
                    candidate.append((key, ""))
                    continue
                owner = next(
                    (
                        url_id
                        for url_id, owned in owned_scopes.items()
                        if owned == scope
                    ),
                    None,
                )
                if owner is None:
                    break
                candidate.append((key, owner))
            else:
                restored = _legacy_scopes(urls, candidate)
                if all(set(restored[key]) == scope for key, scope in scopes.items()):
                    bindings.update(candidate)
                    break
        else:
            raise RuntimeError(
                f"Credential scopes cannot be represented by the old schema: {site_id}"
            )

    op.add_column(
        "site_credentials",
        sa.Column("base_url_id", sa.String(80), nullable=False, server_default=""),
    )
    if bindings:
        connection.execute(
            sa.text("UPDATE site_credentials SET base_url_id = :url WHERE id = :id"),
            [{"id": key, "url": url} for key, url in bindings.items()],
        )
    with op.batch_alter_table("site_credentials") as batch:
        batch.drop_column("base_url_ids_json")


def _site_addresses(connection: sa.Connection) -> dict[str, list[tuple[str, str]]]:
    addresses: dict[str, list[tuple[str, str]]] = defaultdict(list)
    for row in connection.execute(
        sa.text("SELECT id, site_id, kind FROM site_base_urls ORDER BY sort_order, id")
    ).mappings():
        addresses[row["site_id"]].append((row["id"], row["kind"]))
    return addresses


def _legacy_scopes(
    addresses: list[tuple[str, str]], credentials: list[tuple[str, str]]
) -> dict[str, list[str]]:
    # 迁移固定旧规则，不依赖会随业务版本变化的范围解析器。
    address_ids = {address for address, _kind in addresses}
    business = [address for address, kind in addresses if kind != "models"]
    catalog = next((address for address, kind in addresses if kind == "models"), None)
    owned = {bound for _key, bound in credentials if bound}
    shared = [address for address in business if address not in owned]
    scopes: dict[str, list[str]] = {}
    for key, bound in credentials:
        if bound and bound not in address_ids:
            raise RuntimeError(f"Credential references a missing address: {key}")
        scope = [bound] if bound else list(shared)
        if catalog and any(address in business for address in scope):
            scope.append(catalog)
        scopes[key] = list(dict.fromkeys(scope))
    return scopes
