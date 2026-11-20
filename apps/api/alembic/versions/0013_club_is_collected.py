"""estado de coleccionado (Galería) de cada carta del club

Revision ID: 0013
Revises: 0012
"""

import sqlalchemy as sa

from alembic import op

revision = "0013"
down_revision = "0012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("club_items", sa.Column("is_collected", sa.Boolean()))


def downgrade() -> None:
    op.drop_column("club_items", "is_collected")
