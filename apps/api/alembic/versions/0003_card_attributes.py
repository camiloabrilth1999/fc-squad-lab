"""atributos detallados por carta (meta rating)

Revision ID: 0003
Revises: 0002
"""

import sqlalchemy as sa

from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "card_attributes",
        sa.Column("resource_id", sa.Integer, primary_key=True, autoincrement=False),
        sa.Column("stats", sa.JSON, nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True)),
    )


def downgrade() -> None:
    op.drop_table("card_attributes")
