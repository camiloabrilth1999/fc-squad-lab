"""Players DB: explorar todas las cartas con meta rating, tier y precio."""

from datetime import UTC, datetime
from typing import Annotated, Literal

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import any_, func, literal, or_, select
from sqlalchemy.orm import aliased

from ..meta.compute import compute_meta
from ..meta.playstyles import playstyle_names
from ..meta.roles import ROLES, role_for
from ..models_db import Card, CardAttributes, CardMeta, Catalog, Price
from ..prices import effective_prices
from .imports import DbSession

router = APIRouter(prefix="/players", tags=["players"])

MARKET_SOURCE = "easysbc:market"
SORTS = {"meta", "rating", "price", "name"}


class PlayerRow(BaseModel):
    resource_id: int
    name: str | None
    rating: int | None
    positions: list[str]
    league_id: int | None
    nation_id: int | None
    club_id: int | None
    league_name: str | None = None
    nation_name: str | None = None
    club_name: str | None = None
    rarity_name: str | None
    meta: float
    role: str
    meta_source: str  # stats | face
    tier: str
    price: int | None
    price_source: str | None


class PlayersPage(BaseModel):
    items: list[PlayerRow]
    total: int
    page: int
    page_size: int


class RoleMeta(BaseModel):
    role: str
    position: str
    meta: float | None
    source: str


class PlayerDetail(BaseModel):
    resource_id: int
    asset_id: int
    name: str | None
    rating: int | None
    positions: list[str]
    league_id: int | None
    nation_id: int | None
    club_id: int | None
    rarity_name: str | None
    height: int | None
    accelerate_type: str | None
    skill_moves: int | None
    weak_foot: int | None
    play_styles: list[int] = Field(default_factory=list)
    play_styles_plus: list[int] = Field(default_factory=list)
    play_style_names: list[str] = Field(default_factory=list)
    play_style_plus_names: list[str] = Field(default_factory=list)
    league_name: str | None = None
    nation_name: str | None = None
    club_name: str | None = None
    face_stats: dict[str, int] = Field(default_factory=dict)
    stats: dict[str, int] = Field(default_factory=dict)  # detallados, si los tenemos
    roles: list[RoleMeta]
    price: int | None
    price_source: str | None


@router.get("", response_model=PlayersPage)
def list_players(
    session: DbSession,
    q: str | None = None,
    position: str | None = None,
    role: Annotated[str | None, Query(description="rol del meta, p. ej. winger")] = None,
    min_rating: int | None = None,
    max_rating: int | None = None,
    min_meta: float | None = None,
    league_id: int | None = None,
    nation_id: int | None = None,
    club_id: int | None = None,
    tier: Literal["S", "A+", "A", "B+", "B"] | None = None,
    source: Literal["stats", "face"] | None = None,
    min_price: Annotated[int | None, Query(ge=0)] = None,
    max_price: Annotated[int | None, Query(ge=0)] = None,
    sort: str = "meta",
    order: Literal["asc", "desc"] = "desc",
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 50,
) -> PlayersPage:
    if sort not in SORTS:
        raise HTTPException(status_code=422, detail=f"sort debe ser uno de {sorted(SORTS)}")
    if role is not None and role not in ROLES:
        raise HTTPException(status_code=422, detail=f"rol desconocido: {role}")
    market = (
        select(Price.resource_id.label("rid"), Price.price.label("price"))
        .where(Price.platform == "PC", Price.source == MARKET_SOURCE, Price.price > 0)
        .subquery()
    )
    league_c, nation_c, club_c = (aliased(Catalog) for _ in range(3))
    base = (
        select(Card, CardMeta, market.c.price, league_c.name, nation_c.name, club_c.name)
        .join(CardMeta, CardMeta.resource_id == Card.resource_id)
        .outerjoin(market, market.c.rid == Card.resource_id)
        .outerjoin(league_c, (league_c.kind == "league") & (league_c.ea_id == Card.league_id))
        .outerjoin(nation_c, (nation_c.kind == "nation") & (nation_c.ea_id == Card.nation_id))
        .outerjoin(club_c, (club_c.kind == "club") & (club_c.ea_id == Card.club_id))
    )
    conds = []
    if q:
        like = f"%{q.strip()}%"
        conds.append(or_(Card.name.ilike(like), Card.card_name.ilike(like)))
    if position:
        conds.append(literal(position) == any_(Card.positions))
    if role:
        conds.append(CardMeta.role == role)
    if min_rating is not None:
        conds.append(Card.rating >= min_rating)
    if max_rating is not None:
        conds.append(Card.rating <= max_rating)
    if min_meta is not None:
        conds.append(CardMeta.meta >= min_meta)
    if league_id is not None:
        conds.append(Card.league_id == league_id)
    if nation_id is not None:
        conds.append(Card.nation_id == nation_id)
    if club_id is not None:
        conds.append(Card.club_id == club_id)
    if tier:
        conds.append(CardMeta.tier == tier)
    if source:
        conds.append(CardMeta.source == source)
    if min_price is not None:
        conds.append(market.c.price >= min_price)
    if max_price is not None:
        conds.append(market.c.price <= max_price)
    stmt = base.where(*conds)
    total = session.scalar(
        select(func.count())
        .select_from(Card)
        .join(CardMeta, CardMeta.resource_id == Card.resource_id)
        .outerjoin(market, market.c.rid == Card.resource_id)
        .where(*conds)
    )
    column = {
        "meta": CardMeta.meta,
        "rating": Card.rating,
        "price": market.c.price,
        "name": Card.name,
    }[sort]
    ordered = column.asc() if order == "asc" else column.desc()
    stmt = stmt.order_by(ordered.nulls_last(), Card.resource_id).limit(page_size)
    stmt = stmt.offset((page - 1) * page_size)
    found = session.execute(stmt).all()
    prices = effective_prices(session, [r[0].resource_id for r in found], datetime.now(UTC))
    items = [
        PlayerRow(
            resource_id=c.resource_id,
            name=c.name,
            rating=c.rating,
            positions=c.positions or [],
            league_id=c.league_id,
            nation_id=c.nation_id,
            club_id=c.club_id,
            league_name=league_name,
            nation_name=nation_name,
            club_name=club_name,
            rarity_name=c.rarity_name,
            meta=m.meta,
            role=m.role,
            meta_source=m.source,
            tier=m.tier,
            price=prices[c.resource_id][0] if c.resource_id in prices else None,
            price_source=prices[c.resource_id][1] if c.resource_id in prices else None,
        )
        for c, m, _, league_name, nation_name, club_name in found
    ]
    return PlayersPage(items=items, total=total or 0, page=page, page_size=page_size)


def _catalog_name(session: DbSession, kind: str, ea_id: int | None) -> str | None:
    row = session.get(Catalog, (kind, ea_id)) if ea_id is not None else None
    return row.name if row else None


@router.get("/{resource_id}", response_model=PlayerDetail)
def get_player(resource_id: int, session: DbSession) -> PlayerDetail:
    card = session.get(Card, resource_id)
    if card is None:
        raise HTTPException(status_code=404, detail="Carta no encontrada")
    attrs = session.get(CardAttributes, resource_id)
    stats = attrs.stats if attrs else None
    roles: list[RoleMeta] = []
    seen: set[str] = set()
    for pos in card.positions or []:
        r = role_for(pos)
        if r in seen:
            continue
        seen.add(r)
        m = compute_meta(stats, card, role=r)
        roles.append(
            RoleMeta(
                role=r,
                position=pos,
                meta=round(m.value, 1) if m.source != "rating" and m.value is not None else None,
                source=m.source,
            )
        )
    price = effective_prices(session, [resource_id], datetime.now(UTC)).get(resource_id)
    return PlayerDetail(
        resource_id=card.resource_id,
        asset_id=card.asset_id,
        name=card.name,
        rating=card.rating,
        positions=card.positions or [],
        league_id=card.league_id,
        nation_id=card.nation_id,
        club_id=card.club_id,
        rarity_name=card.rarity_name,
        height=card.height,
        accelerate_type=card.accelerate_type,
        skill_moves=card.skill_moves,
        weak_foot=card.weak_foot,
        play_styles=card.play_styles or [],
        play_styles_plus=card.play_styles_plus or [],
        play_style_names=playstyle_names(card.play_styles),
        play_style_plus_names=playstyle_names(card.play_styles_plus),
        league_name=_catalog_name(session, "league", card.league_id),
        nation_name=_catalog_name(session, "nation", card.nation_id),
        club_name=_catalog_name(session, "club", card.club_id),
        face_stats=card.face_stats or {},
        stats=stats or {},
        roles=roles,
        price=price[0] if price else None,
        price_source=price[1] if price else None,
    )
