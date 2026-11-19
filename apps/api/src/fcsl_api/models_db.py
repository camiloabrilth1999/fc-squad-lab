from datetime import datetime

from sqlalchemy import (
    ARRAY,
    JSON,
    BigInteger,
    Boolean,
    DateTime,
    Index,
    Integer,
    SmallInteger,
    Text,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Card(Base):
    __tablename__ = "cards"
    __table_args__ = (Index("ix_cards_asset_id", "asset_id"),)

    resource_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False)
    asset_id: Mapped[int] = mapped_column(Integer, nullable=False)
    name: Mapped[str | None] = mapped_column(Text)
    rating: Mapped[int | None] = mapped_column(SmallInteger)
    positions: Mapped[list[str] | None] = mapped_column(ARRAY(Text))
    league_id: Mapped[int | None] = mapped_column(Integer)
    nation_id: Mapped[int | None] = mapped_column(Integer)
    club_id: Mapped[int | None] = mapped_column(Integer)
    rare: Mapped[bool | None] = mapped_column(Boolean)
    rarity_tags: Mapped[list[str] | None] = mapped_column(ARRAY(Text))
    is_icon: Mapped[bool | None] = mapped_column(Boolean)
    is_hero: Mapped[bool | None] = mapped_column(Boolean)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    card_name: Mapped[str | None] = mapped_column(Text)
    rarity_ea_id: Mapped[int | None] = mapped_column(Integer)
    rarity_name: Mapped[str | None] = mapped_column(Text)
    source: Mapped[str | None] = mapped_column(Text)
    accelerate_type: Mapped[str | None] = mapped_column(Text)
    play_styles: Mapped[list[int] | None] = mapped_column(ARRAY(Integer))
    play_styles_plus: Mapped[list[int] | None] = mapped_column(ARRAY(Integer))
    skill_moves: Mapped[int | None] = mapped_column(SmallInteger)
    weak_foot: Mapped[int | None] = mapped_column(SmallInteger)
    height: Mapped[int | None] = mapped_column(SmallInteger)


class CardAttributes(Base):
    """Stats in-game detallados por carta (de la ficha de FUT.GG), para el meta rating."""

    __tablename__ = "card_attributes"

    resource_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False)
    stats: Mapped[dict] = mapped_column(JSON, nullable=False)  # nombre de stat -> valor
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Price(Base):
    __tablename__ = "prices"

    resource_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False)
    platform: Mapped[str] = mapped_column(Text, primary_key=True)
    source: Mapped[str] = mapped_column(Text, primary_key=True)
    price: Mapped[int | None] = mapped_column(Integer)
    captured_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ClubItem(Base):
    __tablename__ = "club_items"

    item_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False)
    resource_id: Mapped[int | None] = mapped_column(Integer)
    untradeable: Mapped[bool | None] = mapped_column(Boolean)
    location: Mapped[str | None] = mapped_column(Text)
    duplicate: Mapped[bool | None] = mapped_column(Boolean)
    loan: Mapped[bool | None] = mapped_column(Boolean)
    last_sale_price: Mapped[int | None] = mapped_column(Integer)
    imported_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    asset_id: Mapped[int | None] = mapped_column(Integer)
    rating: Mapped[int | None] = mapped_column(SmallInteger)
    market_min: Mapped[int | None] = mapped_column(Integer)
    market_max: Mapped[int | None] = mapped_column(Integer)
    first_owner: Mapped[bool | None] = mapped_column(Boolean)
    seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class SyncRun(Base):
    __tablename__ = "sync_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    kind: Mapped[str] = mapped_column(Text, nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(Text, nullable=False)  # ok | partial | failed
    items: Mapped[int | None] = mapped_column(Integer)
    error: Mapped[str | None] = mapped_column(Text)
