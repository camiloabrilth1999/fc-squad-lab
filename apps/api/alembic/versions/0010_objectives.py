"""objetivos de EA importados por la extensión

Revision ID: 0010
Revises: 0009
"""

import sqlalchemy as sa

from alembic import op

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "objective_categories",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=False),
        sa.Column("name", sa.Text, nullable=False),
        sa.Column("type", sa.Integer),
        sa.Column("priority", sa.Integer),
    )
    op.create_table(
        "objective_groups",
        sa.Column("group_type", sa.Integer, primary_key=True, autoincrement=False),
        sa.Column("group_id", sa.Integer, primary_key=True, autoincrement=False),
        sa.Column("category_id", sa.Integer),
        sa.Column("content_id", sa.Integer),
        sa.Column("title", sa.Text),
        sa.Column("subtitle", sa.Text),
        sa.Column("state", sa.Integer),
        sa.Column("repeatability", sa.Text),
        sa.Column("times_completed", sa.Integer, nullable=False),
        sa.Column("start_time", sa.BigInteger),
        sa.Column("end_time", sa.BigInteger),
        sa.Column("visibility_time", sa.BigInteger),
        sa.Column("priority", sa.Integer),
        sa.Column("data", sa.JSON, nullable=False),
        sa.Column("seen_at", sa.DateTime(timezone=True)),
    )
    op.create_index("ix_objective_groups_category", "objective_groups", ["category_id"])


def downgrade() -> None:
    op.drop_index("ix_objective_groups_category", table_name="objective_groups")
    op.drop_table("objective_groups")
    op.drop_table("objective_categories")
