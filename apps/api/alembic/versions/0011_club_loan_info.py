"""tipo y valor de las cesiones del club (por partidos o por tiempo)

Revision ID: 0011
Revises: 0010
"""

import sqlalchemy as sa

from alembic import op

revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("club_items", sa.Column("loan_type", sa.Text()))
    op.add_column("club_items", sa.Column("loan_value", sa.BigInteger()))


def downgrade() -> None:
    op.drop_column("club_items", "loan_value")
    op.drop_column("club_items", "loan_type")
