"""drop model group match regex

Revision ID: 4f6f1a2b7c0d
Revises: 30364ceff335
Create Date: 2026-04-04 23:35:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = '4f6f1a2b7c0d'
down_revision = '30364ceff335'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_column('model_groups', 'match_regex')


def downgrade() -> None:
    op.add_column('model_groups', sa.Column('match_regex', sa.Text(), nullable=False, server_default=''))
