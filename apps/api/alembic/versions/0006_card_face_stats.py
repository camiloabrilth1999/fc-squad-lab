"""stats de la cara por carta (modelo de meta para cartas sin stats detallados)

Revision ID: 0006
Revises: 0005
"""

import sqlalchemy as sa

from alembic import op

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("cards", sa.Column("face_stats", sa.JSON()))


def downgrade() -> None:
    op.drop_column("cards", "face_stats")
