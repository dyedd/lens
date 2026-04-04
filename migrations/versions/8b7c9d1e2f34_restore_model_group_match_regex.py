"""restore model group match regex

Revision ID: 8b7c9d1e2f34
Revises: 4f6f1a2b7c0d
Create Date: 2026-04-04 23:55:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = '8b7c9d1e2f34'
down_revision = '4f6f1a2b7c0d'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('model_groups', sa.Column('match_regex', sa.Text(), nullable=False, server_default=''))


def downgrade() -> None:
    op.drop_column('model_groups', 'match_regex')
