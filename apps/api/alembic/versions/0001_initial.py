"""esquema inicial: cards, prices, club_items

Revision ID: 0001
Revises:
"""
import sqlalchemy as sa

from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "cards",
        sa.Column("resource_id", sa.Integer, primary_key=True, autoincrement=False),
        sa.Column("asset_id", sa.Integer, nullable=False),
        sa.Column("name", sa.Text),
        sa.Column("rating", sa.SmallInteger),
        sa.Column("positions", sa.ARRAY(sa.Text)),
        sa.Column("league_id", sa.Integer),
        sa.Column("nation_id", sa.Integer),
        sa.Column("club_id", sa.Integer),
        sa.Column("rare", sa.Boolean),
        sa.Column("rarity_tags", sa.ARRAY(sa.Text)),
        sa.Column("is_icon", sa.Boolean),
        sa.Column("is_hero", sa.Boolean),
        sa.Column("updated_at", sa.DateTime(timezone=True)),
    )
    op.create_index("ix_cards_asset_id", "cards", ["asset_id"])
    op.create_table(
        "prices",
        sa.Column("resource_id", sa.Integer, primary_key=True, autoincrement=False),
        sa.Column("platform", sa.Text, primary_key=True),
        sa.Column("price", sa.Integer),
        sa.Column("captured_at", sa.DateTime(timezone=True)),
        sa.Column("source", sa.Text),
    )
    op.create_table(
        "club_items",
        sa.Column("item_id", sa.BigInteger, primary_key=True, autoincrement=False),
        sa.Column("resource_id", sa.Integer),
        sa.Column("untradeable", sa.Boolean),
        sa.Column("location", sa.Text),
        sa.Column("duplicate", sa.Boolean),
        sa.Column("loan", sa.Boolean),
        sa.Column("last_sale_price", sa.Integer, nullable=True),
        sa.Column("imported_at", sa.DateTime(timezone=True)),
    )


def downgrade() -> None:
    op.drop_table("club_items")
    op.drop_table("prices")
    op.drop_index("ix_cards_asset_id", table_name="cards")
    op.drop_table("cards")
