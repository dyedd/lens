"""Restore site-level onboarding regex rules and drop sync targets.

Every saved site model is a sync target by definition, so the explicit
target table only duplicated the model rows. Sites get include and exclude
rule references back: a sync then materializes matching upstream models.
"""

import uuid
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "c3d5e7f9a1b2"
down_revision: str | None = "b2c4d6e8f0a1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_INSERT_TARGET = (
    "INSERT INTO site_protocol_config_sync_targets "
    "(id, protocol_config_id, credential_id, protocol, model_name) "
    "VALUES (:id, :pid, :cid, :protocol, :model_name)"
)


def upgrade() -> None:
    with op.batch_alter_table("sites") as batch:
        batch.add_column(
            sa.Column(
                "model_sync_include_rule_ids_json",
                sa.Text(),
                nullable=False,
                server_default="[]",
            )
        )
        batch.add_column(
            sa.Column(
                "model_sync_exclude_rule_ids_json",
                sa.Text(),
                nullable=False,
                server_default="[]",
            )
        )

    conn = op.get_bind()
    # Targets saved after the last sync have no model row yet; keep them.
    missing_rows = (
        conn.execute(
            sa.text(
                "SELECT t.protocol_config_id, t.credential_id, t.protocol, "
                "t.model_name FROM site_protocol_config_sync_targets AS t "
                "WHERE NOT EXISTS ("
                "SELECT 1 FROM site_discovered_models AS m "
                "WHERE m.protocol_config_id = t.protocol_config_id "
                "AND m.credential_id = t.credential_id "
                "AND m.protocol = t.protocol AND m.model_name = t.model_name)"
            )
        )
        .mappings()
        .all()
    )
    next_sort_orders: dict[str, int] = {}
    for row in missing_rows:
        config_id = str(row["protocol_config_id"])
        if config_id not in next_sort_orders:
            current_max = conn.execute(
                sa.text(
                    "SELECT MAX(sort_order) FROM site_discovered_models "
                    "WHERE protocol_config_id = :pid"
                ),
                {"pid": config_id},
            ).scalar()
            next_sort_orders[config_id] = (
                current_max if current_max is not None else -1
            ) + 1
        conn.execute(
            sa.text(
                "INSERT INTO site_discovered_models "
                "(id, protocol_config_id, credential_id, model_name, enabled, "
                "sort_order, protocol, upstream_missing, upstream_missing_since, "
                "context_window, upstream_context_window) "
                "VALUES (:id, :pid, :cid, :model_name, 1, :sort_order, "
                ":protocol, 0, NULL, NULL, NULL)"
            ),
            {
                "id": str(uuid.uuid4()),
                "pid": config_id,
                "cid": row["credential_id"],
                "model_name": row["model_name"],
                "sort_order": next_sort_orders[config_id],
                "protocol": row["protocol"],
            },
        )
        next_sort_orders[config_id] += 1

    op.drop_table("site_protocol_config_sync_targets")


def downgrade() -> None:
    op.create_table(
        "site_protocol_config_sync_targets",
        sa.Column("id", sa.String(length=80), nullable=False),
        sa.Column("protocol_config_id", sa.String(length=80), nullable=False),
        sa.Column("credential_id", sa.String(length=80), nullable=False),
        sa.Column("protocol", sa.String(length=40), nullable=False),
        sa.Column("model_name", sa.String(length=200), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "protocol_config_id",
            "credential_id",
            "protocol",
            "model_name",
            name="uq_site_protocol_config_sync_targets_target",
        ),
    )
    op.create_index(
        "ix_site_protocol_config_sync_targets_protocol_config_id",
        "site_protocol_config_sync_targets",
        ["protocol_config_id"],
    )
    op.create_index(
        "ix_site_protocol_config_sync_targets_credential_id",
        "site_protocol_config_sync_targets",
        ["credential_id"],
    )
    conn = op.get_bind()
    rows = conn.execute(
        sa.text(
            "SELECT protocol_config_id, credential_id, protocol, model_name "
            "FROM site_discovered_models WHERE protocol IS NOT NULL"
        )
    ).mappings()
    for row in rows:
        conn.execute(
            sa.text(_INSERT_TARGET),
            {"id": str(uuid.uuid4()), **dict(row)},
        )
    with op.batch_alter_table("sites") as batch:
        batch.drop_column("model_sync_exclude_rule_ids_json")
        batch.drop_column("model_sync_include_rule_ids_json")
