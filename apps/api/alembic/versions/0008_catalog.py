"""catálogo de nombres de ligas, naciones y clubes

Revision ID: 0008
Revises: 0007
"""

import sqlalchemy as sa

from alembic import op

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "catalog",
        sa.Column("kind", sa.Text, primary_key=True),
        sa.Column("ea_id", sa.Integer, primary_key=True, autoincrement=False),
        sa.Column("name", sa.Text, nullable=False),
    )


def downgrade() -> None:
    op.drop_table("catalog")
