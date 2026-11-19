"""meta rating precalculado por carta (Players DB)

Revision ID: 0007
Revises: 0006
"""

import sqlalchemy as sa

from alembic import op

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "card_meta",
        sa.Column("resource_id", sa.Integer, primary_key=True, autoincrement=False),
        sa.Column("role", sa.Text, nullable=False),
        sa.Column("meta", sa.Float, nullable=False),
        sa.Column("source", sa.Text, nullable=False),
        sa.Column("tier", sa.Text, nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True)),
    )
    op.create_index("ix_card_meta_meta", "card_meta", ["meta"])


def downgrade() -> None:
    op.drop_index("ix_card_meta_meta", table_name="card_meta")
    op.drop_table("card_meta")
