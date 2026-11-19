"""campos de bonus del meta por carta (AcceleRATE, PlayStyles, filigranas, pie malo)

Revision ID: 0004
Revises: 0003
"""

import sqlalchemy as sa

from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None

COLUMNS = [
    ("accelerate_type", sa.Text()),
    ("play_styles", sa.ARRAY(sa.Integer())),
    ("play_styles_plus", sa.ARRAY(sa.Integer())),
    ("skill_moves", sa.SmallInteger()),
    ("weak_foot", sa.SmallInteger()),
]


def upgrade() -> None:
    for name, type_ in COLUMNS:
        op.add_column("cards", sa.Column(name, type_))


def downgrade() -> None:
    for name, _ in reversed(COLUMNS):
        op.drop_column("cards", name)
