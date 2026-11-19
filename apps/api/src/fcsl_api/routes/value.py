"""Vistas de valor: chollos (meta alto para su precio) y fodder (lo más barato por rating)."""

from typing import Annotated

from fastapi import APIRouter, Query
from pydantic import BaseModel
from sqlalchemy import any_, func, literal, select

from ..models_db import Card, CardMeta, Price
from .imports import DbSession

router = APIRouter(prefix="/value", tags=["value"])

MARKET_SOURCE = "easysbc:market"
BARGAIN_MIN_RATING = 75  # población con la que se comparan precio y meta


class BargainRow(BaseModel):
    resource_id: int
    name: str | None
    rating: int | None
    positions: list[str]
    rarity_name: str | None
    role: str
    meta: float
    meta_source: str
    tier: str
    price: int
    score: float  # percentil de meta − percentil de precio, dentro del rol (−1..1)
    image_path: str | None = None


class BargainsPage(BaseModel):
    items: list[BargainRow]


class FodderCard(BaseModel):
    resource_id: int
    name: str | None
    positions: list[str]
    rarity_name: str | None
    price: int
    image_path: str | None = None


class FodderGroup(BaseModel):
    rating: int
    cheapest: int
    cards: list[FodderCard]


def _market_prices():
    return (
        select(Price.resource_id.label("rid"), Price.price.label("price"))
        .where(Price.platform == "PC", Price.source == MARKET_SOURCE, Price.price > 0)
        .subquery()
    )


@router.get("/bargains", response_model=BargainsPage)
def bargains(
    session: DbSession,
    role: str | None = None,
    position: str | None = None,
    min_rating: Annotated[int | None, Query(ge=40, le=99)] = None,
    max_price: Annotated[int | None, Query(ge=0)] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> BargainsPage:
    market = _market_prices()
    ranked = (
        select(
            Card.resource_id.label("rid"),
            func.percent_rank()
            .over(partition_by=CardMeta.role, order_by=CardMeta.meta)
            .label("meta_pct"),
            func.percent_rank()
            .over(partition_by=CardMeta.role, order_by=market.c.price)
            .label("price_pct"),
        )
        .join(CardMeta, CardMeta.resource_id == Card.resource_id)
        .join(market, market.c.rid == Card.resource_id)
        .where(Card.rating >= BARGAIN_MIN_RATING)
        .subquery()
    )
    score = (ranked.c.meta_pct - ranked.c.price_pct).label("score")
    stmt = (
        select(Card, CardMeta, market.c.price, score)
        .join(ranked, ranked.c.rid == Card.resource_id)
        .join(CardMeta, CardMeta.resource_id == Card.resource_id)
        .join(market, market.c.rid == Card.resource_id)
    )
    if role:
        stmt = stmt.where(CardMeta.role == role)
    if position:
        stmt = stmt.where(literal(position) == any_(Card.positions))
    if min_rating is not None:
        stmt = stmt.where(Card.rating >= min_rating)
    if max_price is not None:
        stmt = stmt.where(market.c.price <= max_price)
    rows = session.execute(stmt.order_by(score.desc(), Card.resource_id).limit(limit)).all()
    return BargainsPage(
        items=[
            BargainRow(
                resource_id=c.resource_id,
                name=c.name,
                rating=c.rating,
                positions=c.positions or [],
                rarity_name=c.rarity_name,
                role=m.role,
                meta=m.meta,
                meta_source=m.source,
                tier=m.tier,
                price=price,
                score=round(float(s), 3),
                image_path=c.image_path,
            )
            for c, m, price, s in rows
        ]
    )


@router.get("/fodder", response_model=list[FodderGroup])
def fodder(
    session: DbSession,
    min_rating: Annotated[int, Query(ge=40, le=99)] = 75,
    max_rating: Annotated[int, Query(ge=40, le=99)] = 92,
    per_rating: Annotated[int, Query(ge=1, le=20)] = 5,
) -> list[FodderGroup]:
    market = _market_prices()
    nth = (
        func.row_number()
        .over(partition_by=Card.rating, order_by=(market.c.price, Card.resource_id))
        .label("nth")
    )
    inner = (
        select(Card.resource_id.label("rid"), nth)
        .join(market, market.c.rid == Card.resource_id)
        .where(Card.rating >= min_rating, Card.rating <= max_rating)
        .subquery()
    )
    rows = session.execute(
        select(Card, market.c.price)
        .join(inner, inner.c.rid == Card.resource_id)
        .join(market, market.c.rid == Card.resource_id)
        .where(inner.c.nth <= per_rating)
        .order_by(Card.rating, market.c.price, Card.resource_id)
    ).all()
    groups: dict[int, list[FodderCard]] = {}
    for c, price in rows:
        groups.setdefault(c.rating or 0, []).append(
            FodderCard(
                resource_id=c.resource_id,
                name=c.name,
                positions=c.positions or [],
                rarity_name=c.rarity_name,
                price=price,
                image_path=c.image_path,
            )
        )
    return [
        FodderGroup(rating=r, cheapest=cards[0].price, cards=cards)
        for r, cards in sorted(groups.items())
    ]
