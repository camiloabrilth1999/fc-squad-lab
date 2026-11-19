"""imágenes de cartas, escudos, banderas y ligas (rutas del CDN de FUT.GG)

Revision ID: 0012
Revises: 0011
"""

import sqlalchemy as sa

from alembic import op

revision = "0012"
down_revision = "0011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("cards", sa.Column("image_path", sa.Text()))
    op.add_column("cards", sa.Column("portrait_path", sa.Text()))
    op.add_column("catalog", sa.Column("image_path", sa.Text()))


def downgrade() -> None:
    op.drop_column("catalog", "image_path")
    op.drop_column("cards", "portrait_path")
    op.drop_column("cards", "image_path")
