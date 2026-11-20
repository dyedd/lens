"""Store only concrete models selected for each credential."""

import sqlalchemy as sa
from alembic import op

revision = "a8e2c6f0b4d9"
down_revision = "fce6f7a8b9c0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("site_credentials") as batch:
        batch.drop_column("model_pattern")


def downgrade() -> None:
    with op.batch_alter_table("site_credentials") as batch:
        batch.add_column(
            sa.Column(
                "model_pattern", sa.Text(), nullable=False, server_default=sa.text("''")
            )
        )
