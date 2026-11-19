"""altura por carta (cm): influye en el meta (sobre todo en porteros)

Revision ID: 0005
Revises: 0004
"""

import sqlalchemy as sa

from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("cards", sa.Column("height", sa.SmallInteger()))


def downgrade() -> None:
    op.drop_column("cards", "height")
