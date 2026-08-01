"""model sources and protocol credentials

Revision ID: a4c7e2f9b1d6
Revises: 9b3e1d7c5a20
Create Date: 2026-08-01 00:00:00.000000

"""

from __future__ import annotations

import uuid
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "a4c7e2f9b1d6"
down_revision: Union[str, Sequence[str], None] = "9b3e1d7c5a20"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
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
    op.create_index(
        "ix_site_protocol_config_credentials_protocol_config_id",
        "site_protocol_config_credentials",
        ["protocol_config_id"],
    )
    op.create_index(
        "ix_site_protocol_config_credentials_credential_id",
        "site_protocol_config_credentials",
        ["credential_id"],
    )

    connection = op.get_bind()
    protocol_configs = connection.execute(
        sa.text("SELECT id, credential_id FROM site_protocol_configs")
    ).mappings()
    for protocol_config in protocol_configs:
        credential_ids: list[str] = []
        primary_credential_id = str(protocol_config["credential_id"] or "").strip()
        if primary_credential_id:
            credential_ids.append(primary_credential_id)
        model_credentials = connection.execute(
            sa.text(
                "SELECT credential_id FROM site_discovered_models "
                "WHERE protocol_config_id = :protocol_config_id "
                "ORDER BY sort_order, id"
            ),
            {"protocol_config_id": protocol_config["id"]},
        ).scalars()
        for credential_id in model_credentials:
            normalized = str(credential_id or "").strip()
            if normalized and normalized not in credential_ids:
                credential_ids.append(normalized)
        for sort_order, credential_id in enumerate(credential_ids):
            connection.execute(
                sa.text(
                    "INSERT INTO site_protocol_config_credentials "
                    "(id, protocol_config_id, credential_id, sort_order) "
                    "VALUES (:id, :protocol_config_id, :credential_id, :sort_order)"
                ),
                {
                    "id": str(uuid.uuid4()),
                    "protocol_config_id": protocol_config["id"],
                    "credential_id": credential_id,
                    "sort_order": sort_order,
                },
            )

    with op.batch_alter_table("site_discovered_models") as batch_op:
        batch_op.add_column(
            sa.Column(
                "source",
                sa.String(length=16),
                nullable=False,
                server_default="manual",
            )
        )

    with op.batch_alter_table("site_discovered_models") as batch_op:
        batch_op.create_check_constraint(
            "ck_site_discovered_models_source",
            "source IN ('manual', 'synced')",
        )
        batch_op.create_unique_constraint(
            "uq_site_discovered_models_target",
            ["protocol_config_id", "credential_id", "protocol", "model_name"],
        )
        batch_op.alter_column("source", server_default=None)

    with op.batch_alter_table("site_protocol_configs") as batch_op:
        batch_op.drop_index("ix_site_protocol_configs_credential_id")
        batch_op.drop_column("credential_id")


def downgrade() -> None:
    with op.batch_alter_table("site_protocol_configs") as batch_op:
        batch_op.add_column(
            sa.Column(
                "credential_id", sa.String(length=80), nullable=False, server_default=""
            )
        )
        batch_op.create_index(
            "ix_site_protocol_configs_credential_id", ["credential_id"]
        )

    connection = op.get_bind()
    primary_credentials = connection.execute(
        sa.text(
            "SELECT protocol_config_id, credential_id "
            "FROM site_protocol_config_credentials WHERE sort_order = 0"
        )
    ).mappings()
    for row in primary_credentials:
        connection.execute(
            sa.text(
                "UPDATE site_protocol_configs SET credential_id = :credential_id "
                "WHERE id = :protocol_config_id"
            ),
            row,
        )

    with op.batch_alter_table("site_protocol_configs") as batch_op:
        batch_op.alter_column("credential_id", server_default=None)

    with op.batch_alter_table("site_discovered_models") as batch_op:
        batch_op.drop_constraint("uq_site_discovered_models_target", type_="unique")
        batch_op.drop_constraint("ck_site_discovered_models_source", type_="check")
        batch_op.drop_column("source")

    op.drop_index(
        "ix_site_protocol_config_credentials_credential_id",
        table_name="site_protocol_config_credentials",
    )
    op.drop_index(
        "ix_site_protocol_config_credentials_protocol_config_id",
        table_name="site_protocol_config_credentials",
    )
    op.drop_table("site_protocol_config_credentials")
