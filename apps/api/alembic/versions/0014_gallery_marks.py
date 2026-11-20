"""marcas manuales de coleccionado de la Galería

Revision ID: 0014
Revises: 0013
"""

import sqlalchemy as sa

from alembic import op

revision = "0014"
down_revision = "0013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "gallery_marks",
        sa.Column("resource_id", sa.Integer(), primary_key=True, autoincrement=False),
        sa.Column("collected", sa.Boolean(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True)),
    )


def downgrade() -> None:
    op.drop_table("gallery_marks")
