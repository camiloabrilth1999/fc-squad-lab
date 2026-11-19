from datetime import datetime

from sqlalchemy import (
    ARRAY,
    JSON,
    BigInteger,
    Boolean,
    DateTime,
    Float,
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
    face_stats: Mapped[dict | None] = mapped_column(JSON)  # stats de la cara + fuerza (listado)
    image_path: Mapped[str | None] = mapped_column(Text)  # carta completa (CDN de FUT.GG)
    portrait_path: Mapped[str | None] = mapped_column(Text)  # retrato del jugador


class CardAttributes(Base):
    """Stats in-game detallados por carta (de la ficha de FUT.GG), para el meta rating."""

    __tablename__ = "card_attributes"

    resource_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False)
    stats: Mapped[dict] = mapped_column(JSON, nullable=False)  # nombre de stat -> valor
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Catalog(Base):
    """Nombres de ligas, naciones y clubes (del listado de FUT.GG), para filtros y vistas."""

    __tablename__ = "catalog"

    kind: Mapped[str] = mapped_column(Text, primary_key=True)  # league | nation | club
    ea_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    image_path: Mapped[str | None] = mapped_column(Text)  # escudo / bandera / liga (CDN de FUT.GG)


class EvolutionCategory(Base):
    """Categoría de Evoluciones (Evoluciones, Campus, Roles++…) según EA."""

    __tablename__ = "evolution_categories"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    slot_ids: Mapped[list[int]] = mapped_column(JSON, nullable=False, default=list)


class Evolution(Base):
    """Una evolución (slot de la Academia) tal como la vio la extensión, ya reducida."""

    __tablename__ = "evolutions"
    __table_args__ = (Index("ix_evolutions_category", "category_id"),)

    slot_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False)
    content_id: Mapped[int | None] = mapped_column(Integer)
    name: Mapped[str | None] = mapped_column(Text)
    description: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str | None] = mapped_column(Text)
    timed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    end_time: Mapped[int | None] = mapped_column(BigInteger)  # epoch en segundos; 0 = sin caducidad
    category_id: Mapped[int | None] = mapped_column(Integer)
    gk_only: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    outfield_only: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    multi_choice: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    reset_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_rewards: Mapped[int | None] = mapped_column(Integer)
    # currencies, top_rewards, requirements (filas crudas), levels y bonuses
    data: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ObjectiveCategory(Base):
    """Categoría de objetivos (Fundamentos, Hitos, De temporada…) según EA."""

    __tablename__ = "objective_categories"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    type: Mapped[int | None] = mapped_column(Integer)
    priority: Mapped[int | None] = mapped_column(Integer)


class ObjectiveGroup(Base):
    """Un grupo de objetivos con su progreso, tal como lo vio la extensión (ya reducido)."""

    __tablename__ = "objective_groups"
    __table_args__ = (Index("ix_objective_groups_category", "category_id"),)

    group_type: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False)
    group_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False)
    category_id: Mapped[int | None] = mapped_column(Integer)
    content_id: Mapped[int | None] = mapped_column(Integer)
    title: Mapped[str | None] = mapped_column(Text)
    subtitle: Mapped[str | None] = mapped_column(Text)
    state: Mapped[int | None] = mapped_column(Integer)  # 0 sin empezar, 1 en curso, 4 completado
    repeatability: Mapped[str | None] = mapped_column(Text)
    times_completed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    start_time: Mapped[int | None] = mapped_column(BigInteger)  # epoch en segundos
    end_time: Mapped[int | None] = mapped_column(BigInteger)
    visibility_time: Mapped[int | None] = mapped_column(BigInteger)
    priority: Mapped[int | None] = mapped_column(Integer)
    data: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)  # awards + objectives
    seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class CardMeta(Base):
    """Meta rating precalculado por carta (rol de su posición preferida), para la Players DB."""

    __tablename__ = "card_meta"
    __table_args__ = (Index("ix_card_meta_meta", "meta"),)

    resource_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False)
    role: Mapped[str] = mapped_column(Text, nullable=False)
    meta: Mapped[float] = mapped_column(Float, nullable=False)
    source: Mapped[str] = mapped_column(Text, nullable=False)  # stats | face
    tier: Mapped[str] = mapped_column(Text, nullable=False)  # S | A+ | A | B+ | B
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
    # cesión: MATCH_LOAN (loan_value = partidos que quedan) o USER_TIME_LIMIT_LOAN (epoch en que acaba)
    loan_type: Mapped[str | None] = mapped_column(Text)
    loan_value: Mapped[int | None] = mapped_column(BigInteger)
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
