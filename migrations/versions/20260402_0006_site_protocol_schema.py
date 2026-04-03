"""add site protocol credential model schema

Revision ID: 20260402_0006
Revises: 20260402_0005
Create Date: 2026-04-02 23:45:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260402_0006"
down_revision = "20260402_0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "sites",
        sa.Column("id", sa.String(length=80), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_sites_name"), "sites", ["name"], unique=True)

    op.create_table(
        "site_credentials",
        sa.Column("id", sa.String(length=80), nullable=False),
        sa.Column("site_id", sa.String(length=80), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("api_key", sa.Text(), nullable=False),
        sa.Column("enabled", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_site_credentials_site_id"), "site_credentials", ["site_id"], unique=False)

    op.create_table(
        "site_protocol_configs",
        sa.Column("id", sa.String(length=80), nullable=False),
        sa.Column("site_id", sa.String(length=80), nullable=False),
        sa.Column("label", sa.String(length=120), nullable=False),
        sa.Column("protocol", sa.String(length=40), nullable=False),
        sa.Column("enabled", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("base_url", sa.String(length=500), nullable=False),
        sa.Column("headers_json", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("base_urls_json", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("proxy", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("channel_proxy", sa.Text(), nullable=False, server_default=""),
        sa.Column("param_override", sa.Text(), nullable=False, server_default=""),
        sa.Column("match_regex", sa.Text(), nullable=False, server_default=""),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_site_protocol_configs_site_id"), "site_protocol_configs", ["site_id"], unique=False)
    op.create_index(op.f("ix_site_protocol_configs_protocol"), "site_protocol_configs", ["protocol"], unique=False)

    op.create_table(
        "site_protocol_credential_bindings",
        sa.Column("id", sa.String(length=80), nullable=False),
        sa.Column("protocol_config_id", sa.String(length=80), nullable=False),
        sa.Column("credential_id", sa.String(length=80), nullable=False),
        sa.Column("enabled", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_site_protocol_credential_bindings_protocol_config_id"), "site_protocol_credential_bindings", ["protocol_config_id"], unique=False)
    op.create_index(op.f("ix_site_protocol_credential_bindings_credential_id"), "site_protocol_credential_bindings", ["credential_id"], unique=False)

    op.create_table(
        "site_discovered_models",
        sa.Column("id", sa.String(length=80), nullable=False),
        sa.Column("protocol_config_id", sa.String(length=80), nullable=False),
        sa.Column("credential_id", sa.String(length=80), nullable=False),
        sa.Column("model_name", sa.String(length=200), nullable=False),
        sa.Column("enabled", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_site_discovered_models_protocol_config_id"), "site_discovered_models", ["protocol_config_id"], unique=False)
    op.create_index(op.f("ix_site_discovered_models_credential_id"), "site_discovered_models", ["credential_id"], unique=False)

    with op.batch_alter_table("model_group_items") as batch_op:
        batch_op.add_column(sa.Column("credential_id", sa.String(length=80), nullable=False, server_default=""))
        batch_op.add_column(sa.Column("credential_name_snapshot", sa.String(length=120), nullable=False, server_default=""))
        batch_op.create_index(op.f("ix_model_group_items_credential_id"), ["credential_id"], unique=False)


def downgrade() -> None:
    with op.batch_alter_table("model_group_items") as batch_op:
        batch_op.drop_index(op.f("ix_model_group_items_credential_id"))
        batch_op.drop_column("credential_name_snapshot")
        batch_op.drop_column("credential_id")

    op.drop_index(op.f("ix_site_discovered_models_credential_id"), table_name="site_discovered_models")
    op.drop_index(op.f("ix_site_discovered_models_protocol_config_id"), table_name="site_discovered_models")
    op.drop_table("site_discovered_models")

    op.drop_index(op.f("ix_site_protocol_credential_bindings_credential_id"), table_name="site_protocol_credential_bindings")
    op.drop_index(op.f("ix_site_protocol_credential_bindings_protocol_config_id"), table_name="site_protocol_credential_bindings")
    op.drop_table("site_protocol_credential_bindings")

    op.drop_index(op.f("ix_site_protocol_configs_protocol"), table_name="site_protocol_configs")
    op.drop_index(op.f("ix_site_protocol_configs_site_id"), table_name="site_protocol_configs")
    op.drop_table("site_protocol_configs")

    op.drop_index(op.f("ix_site_credentials_site_id"), table_name="site_credentials")
    op.drop_table("site_credentials")

    op.drop_index(op.f("ix_sites_name"), table_name="sites")
    op.drop_table("sites")
