"""protocol base_url_id

Revision ID: 0003
Revises: 0002
Create Date: 2026-04-09
"""

from alembic import op
import sqlalchemy as sa

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("site_protocol_configs") as batch_op:
        batch_op.add_column(sa.Column("base_url_id", sa.String(80), nullable=False, server_default=""))


def downgrade() -> None:
    with op.batch_alter_table("site_protocol_configs") as batch_op:
        batch_op.drop_column("base_url_id")
