"""evoluciones (Academia de EA) importadas por la extensión

Revision ID: 0009
Revises: 0008
"""

import sqlalchemy as sa

from alembic import op

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "evolution_categories",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=False),
        sa.Column("name", sa.Text, nullable=False),
        sa.Column("slot_ids", sa.JSON, nullable=False),
    )
    op.create_table(
        "evolutions",
        sa.Column("slot_id", sa.Integer, primary_key=True, autoincrement=False),
        sa.Column("content_id", sa.Integer),
        sa.Column("name", sa.Text),
        sa.Column("description", sa.Text),
        sa.Column("status", sa.Text),
        sa.Column("timed", sa.Boolean, nullable=False),
        sa.Column("end_time", sa.BigInteger),
        sa.Column("category_id", sa.Integer),
        sa.Column("gk_only", sa.Boolean, nullable=False),
        sa.Column("outfield_only", sa.Boolean, nullable=False),
        sa.Column("multi_choice", sa.Boolean, nullable=False),
        sa.Column("reset_count", sa.Integer, nullable=False),
        sa.Column("total_rewards", sa.Integer),
        sa.Column("data", sa.JSON, nullable=False),
        sa.Column("seen_at", sa.DateTime(timezone=True)),
    )
    op.create_index("ix_evolutions_category", "evolutions", ["category_id"])


def downgrade() -> None:
    op.drop_index("ix_evolutions_category", table_name="evolutions")
    op.drop_table("evolutions")
    op.drop_table("evolution_categories")
