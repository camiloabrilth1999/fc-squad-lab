"""datos fase 1: columnas de cards/club_items, prices por fuente, sync_runs

Revision ID: 0002
Revises: 0001
"""

import sqlalchemy as sa

from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("cards", sa.Column("card_name", sa.Text))
    op.add_column("cards", sa.Column("rarity_ea_id", sa.Integer))
    op.add_column("cards", sa.Column("rarity_name", sa.Text))
    op.add_column("cards", sa.Column("source", sa.Text))

    op.execute("UPDATE prices SET source = 'unknown' WHERE source IS NULL")
    op.alter_column("prices", "source", existing_type=sa.Text, nullable=False)
    op.drop_constraint("prices_pkey", "prices", type_="primary")
    op.create_primary_key("prices_pkey", "prices", ["resource_id", "platform", "source"])

    op.add_column("club_items", sa.Column("asset_id", sa.Integer))
    op.add_column("club_items", sa.Column("rating", sa.SmallInteger))
    op.add_column("club_items", sa.Column("market_min", sa.Integer))
    op.add_column("club_items", sa.Column("market_max", sa.Integer))
    op.add_column("club_items", sa.Column("first_owner", sa.Boolean))
    op.add_column("club_items", sa.Column("seen_at", sa.DateTime(timezone=True)))

    op.create_table(
        "sync_runs",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("kind", sa.Text, nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
        sa.Column("status", sa.Text, nullable=False),
        sa.Column("items", sa.Integer),
        sa.Column("error", sa.Text, nullable=True),
    )


def downgrade() -> None:
    op.drop_table("sync_runs")
    for col in ("seen_at", "first_owner", "market_max", "market_min", "rating", "asset_id"):
        op.drop_column("club_items", col)
    op.drop_constraint("prices_pkey", "prices", type_="primary")
    # Varias fuentes por (resource_id, platform) no caben en la PK antigua: se conserva la más reciente.
    op.execute(
        "DELETE FROM prices a USING prices b WHERE a.resource_id = b.resource_id "
        "AND a.platform = b.platform AND "
        "(a.captured_at, a.source) < (b.captured_at, b.source)"
    )
    op.create_primary_key("prices_pkey", "prices", ["resource_id", "platform"])
    op.alter_column("prices", "source", existing_type=sa.Text, nullable=True)
    for col in ("source", "rarity_name", "rarity_ea_id", "card_name"):
        op.drop_column("cards", col)
