"""Collapse site protocol configs to one endpoint per URL.

Revision ID: a2c4e6f8b0d1
Revises: a1b9c3d5e7f0
Create Date: 2026-09-13
"""

from collections import defaultdict
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "a2c4e6f8b0d1"
down_revision: str | None = "a1b9c3d5e7f0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "sites",
        sa.Column("headers_json", sa.Text(), nullable=False, server_default="[]"),
    )
    op.add_column(
        "sites",
        sa.Column(
            "proxy_mode",
            sa.String(length=16),
            nullable=False,
            server_default="inherit",
        ),
    )
    op.add_column(
        "sites",
        sa.Column("channel_proxy", sa.Text(), nullable=False, server_default=""),
    )
    op.add_column(
        "sites",
        sa.Column("param_override", sa.Text(), nullable=False, server_default="[]"),
    )
    op.add_column(
        "site_credentials",
        sa.Column(
            "base_url_id", sa.String(length=80), nullable=False, server_default=""
        ),
    )

    conn = op.get_bind()
    configs = conn.execute(
        sa.text(
            "SELECT id, site_id, base_url_id, headers_json, proxy_mode, "
            "channel_proxy, param_override FROM site_protocol_configs "
            "ORDER BY site_id, id"
        )
    ).mappings()
    seen_sites: set[str] = set()
    configs_by_url: dict[str, list[str]] = defaultdict(list)
    config_site: dict[str, str] = {}
    for row in configs:
        config_id = str(row["id"])
        site_id = str(row["site_id"])
        url_id = str(row["base_url_id"])
        config_site[config_id] = site_id
        configs_by_url[url_id].append(config_id)
        if site_id in seen_sites:
            continue
        seen_sites.add(site_id)
        conn.execute(
            sa.text(
                "UPDATE sites SET headers_json = :headers_json, "
                "proxy_mode = :proxy_mode, channel_proxy = :channel_proxy, "
                "param_override = :param_override WHERE id = :id"
            ),
            {
                "headers_json": row["headers_json"] or "[]",
                "proxy_mode": row["proxy_mode"] or "inherit",
                "channel_proxy": row["channel_proxy"] or "",
                "param_override": row["param_override"] or "[]",
                "id": site_id,
            },
        )

    primary_url_by_site: dict[str, str] = {}
    for row in conn.execute(
        sa.text(
            "SELECT id, site_id FROM site_base_urls ORDER BY site_id, sort_order, id"
        )
    ).mappings():
        primary_url_by_site.setdefault(str(row["site_id"]), str(row["id"]))

    associations = conn.execute(
        sa.text(
            "SELECT protocol_config_id, credential_id "
            "FROM site_protocol_config_credentials"
        )
    ).mappings()
    creds_by_config: dict[str, set[str]] = defaultdict(set)
    for row in associations:
        creds_by_config[str(row["protocol_config_id"])].add(str(row["credential_id"]))

    for url_id, config_ids in configs_by_url.items():
        canonical = config_ids[0]
        extras = config_ids[1:]
        site_id = config_site[canonical]
        is_primary = primary_url_by_site.get(site_id) == url_id
        canonical_creds = set(creds_by_config[canonical])
        extra_only: set[str] = set()
        for extra_id in extras:
            extra_only |= creds_by_config[extra_id] - canonical_creds
            _remap_protocol_config(conn, extra_id, canonical)
            conn.execute(
                sa.text(
                    "DELETE FROM site_protocol_config_credentials "
                    "WHERE protocol_config_id = :old"
                ),
                {"old": extra_id},
            )
            conn.execute(
                sa.text("DELETE FROM site_protocol_configs WHERE id = :old"),
                {"old": extra_id},
            )
        if extra_only and not is_primary:
            for credential_id in extra_only:
                conn.execute(
                    sa.text(
                        "UPDATE site_credentials SET base_url_id = :url_id "
                        "WHERE id = :credential_id"
                    ),
                    {"url_id": url_id, "credential_id": credential_id},
                )

    op.drop_table("site_protocol_config_credentials")
    with op.batch_alter_table("site_base_urls") as batch:
        batch.drop_column("name")
        batch.drop_column("enabled")
        batch.drop_column("supported_protocols_json")
    with op.batch_alter_table("site_credentials") as batch:
        batch.drop_column("enabled")
    with op.batch_alter_table("site_protocol_configs") as batch:
        batch.drop_column("name")
        batch.drop_column("enabled")
        batch.drop_column("protocols_json")
        batch.drop_column("headers_json")
        batch.drop_column("proxy_mode")
        batch.drop_column("channel_proxy")
        batch.drop_column("param_override")
        batch.create_unique_constraint(
            "uq_site_protocol_configs_base_url_id", ["base_url_id"]
        )


def _remap_protocol_config(conn, old_id: str, canonical_id: str) -> None:
    conn.execute(
        sa.text(
            "UPDATE site_discovered_models SET protocol_config_id = :canonical "
            "WHERE protocol_config_id = :old AND NOT EXISTS ("
            "SELECT 1 FROM site_discovered_models AS kept "
            "WHERE kept.protocol_config_id = :canonical "
            "AND kept.credential_id = site_discovered_models.credential_id "
            "AND kept.protocol = site_discovered_models.protocol "
            "AND kept.model_name = site_discovered_models.model_name)"
        ),
        {"canonical": canonical_id, "old": old_id},
    )
    conn.execute(
        sa.text("DELETE FROM site_discovered_models WHERE protocol_config_id = :old"),
        {"old": old_id},
    )
    conn.execute(
        sa.text(
            "UPDATE site_protocol_config_sync_targets SET protocol_config_id = :canonical "
            "WHERE protocol_config_id = :old AND NOT EXISTS ("
            "SELECT 1 FROM site_protocol_config_sync_targets AS kept "
            "WHERE kept.protocol_config_id = :canonical "
            "AND kept.credential_id = site_protocol_config_sync_targets.credential_id "
            "AND kept.protocol = site_protocol_config_sync_targets.protocol "
            "AND kept.model_name = site_protocol_config_sync_targets.model_name)"
        ),
        {"canonical": canonical_id, "old": old_id},
    )
    conn.execute(
        sa.text(
            "DELETE FROM site_protocol_config_sync_targets "
            "WHERE protocol_config_id = :old"
        ),
        {"old": old_id},
    )
    conn.execute(
        sa.text(
            "UPDATE site_credential_rates SET protocol_config_id = :canonical "
            "WHERE protocol_config_id = :old"
        ),
        {"canonical": canonical_id, "old": old_id},
    )
    conn.execute(
        sa.text(
            "UPDATE request_logs SET protocol_config_id = :canonical "
            "WHERE protocol_config_id = :old"
        ),
        {"canonical": canonical_id, "old": old_id},
    )
    old_len = len(old_id) + 1
    conn.execute(
        sa.text(
            "UPDATE model_group_items SET channel_id = :canonical || "
            "substr(channel_id, :old_len) WHERE channel_id LIKE :prefix"
        ),
        {
            "canonical": canonical_id,
            "old_len": old_len,
            "prefix": f"{old_id}_%",
        },
    )


def downgrade() -> None:
    with op.batch_alter_table("site_protocol_configs") as batch:
        batch.drop_constraint("uq_site_protocol_configs_base_url_id", type_="unique")
        batch.add_column(
            sa.Column("name", sa.String(length=120), nullable=False, server_default="")
        )
        batch.add_column(
            sa.Column("enabled", sa.Integer(), nullable=False, server_default="1")
        )
        batch.add_column(
            sa.Column("protocols_json", sa.Text(), nullable=False, server_default="[]")
        )
        batch.add_column(
            sa.Column("headers_json", sa.Text(), nullable=False, server_default="[]")
        )
        batch.add_column(
            sa.Column(
                "proxy_mode",
                sa.String(length=16),
                nullable=False,
                server_default="inherit",
            )
        )
        batch.add_column(
            sa.Column("channel_proxy", sa.Text(), nullable=False, server_default="")
        )
        batch.add_column(
            sa.Column("param_override", sa.Text(), nullable=False, server_default="[]")
        )
    with op.batch_alter_table("site_credentials") as batch:
        batch.add_column(
            sa.Column("enabled", sa.Integer(), nullable=False, server_default="1")
        )
    with op.batch_alter_table("site_base_urls") as batch:
        batch.add_column(
            sa.Column("name", sa.String(length=120), nullable=False, server_default="")
        )
        batch.add_column(
            sa.Column("enabled", sa.Integer(), nullable=False, server_default="1")
        )
        batch.add_column(
            sa.Column(
                "supported_protocols_json",
                sa.Text(),
                nullable=False,
                server_default="[]",
            )
        )
    op.create_table(
        "site_protocol_config_credentials",
        sa.Column("id", sa.String(length=80), nullable=False),
        sa.Column("protocol_config_id", sa.String(length=80), nullable=False),
        sa.Column("credential_id", sa.String(length=80), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "protocol_config_id",
            "credential_id",
            name="uq_site_protocol_config_credentials_target",
        ),
    )
    op.drop_column("site_credentials", "base_url_id")
    op.drop_column("sites", "param_override")
    op.drop_column("sites", "channel_proxy")
    op.drop_column("sites", "proxy_mode")
    op.drop_column("sites", "headers_json")
