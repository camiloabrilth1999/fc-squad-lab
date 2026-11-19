"""Club importado (unido a datos de cartas y precios PC) y estado de los datos."""

from datetime import UTC, datetime, timedelta
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field, ValidationError
from sqlalchemy import any_, delete, func, literal, or_, select
from sqlalchemy.orm import Session

from ..meta.attributes import STATS, PlayerAttributes
from ..meta.rating import meta_rating
from ..meta.roles import role_for
from ..models_db import Card, CardAttributes, ClubItem, Price, SyncRun
from ..prices import effective_prices
from ..solver import models as solver_models
from ..solver.valuation import card_cost
from .imports import (  # noqa: F401  (get_db se reexporta para los overrides)
    DbSession,
    get_db,
    require_token,
)

router = APIRouter(tags=["club"])

TRADEABLE_FACTOR = solver_models.ValuationSettings().tradeable_factor


class ClubRow(BaseModel):
    item_id: int
    resource_id: int | None
    name: str | None
    rating: int | None
    positions: list[str]
    league_id: int | None
    nation_id: int | None
    club_id: int | None
    rarity_name: str | None
    untradeable: bool
    location: str | None
    duplicate: bool
    loan: bool
    price: int | None
    price_source: str | None
    value: int
    seen_at: datetime | None
    meta: float | None = None
    meta_role: str | None = None


class ClubSummary(BaseModel):
    count: int
    value: int
    untradeable: int
    unknown_cards: int


class ClubPage(BaseModel):
    items: list[ClubRow]
    total: int
    summary: ClubSummary


class ForgetBody(BaseModel):
    older_than_days: int = Field(ge=1)


def _price_used(item: ClubItem, effective: tuple[int, str] | None) -> tuple[int | None, str | None]:
    if effective is not None:
        return effective
    if item.last_sale_price:
        return item.last_sale_price, "last-sale"
    if item.market_min:
        return item.market_min, "ea-min"
    return None, None


def _value(item: ClubItem, card: Card | None, price: int | None) -> int:
    """Valor de una carta propia, como la valora el solver.

    Precio usado: el efectivo; si no hay, `last_sale_price`, luego `market_min`, luego 0.
    Con datos de carta completos y válidos (rating 40..99, posiciones no vacías) se construye un
    `solver.models.Card(source="club")` (`in_sbc_storage` = ubicación "storage") y el valor es
    `card_cost(card, ValuationSettings())`. Si la carta es desconocida o sus datos no sirven al
    solver: 0 si es intransferible, si no precio × factor (0.95) redondeado.
    """
    used = price or 0
    rating = card.rating if card is not None and card.rating is not None else item.rating
    if (
        card is not None
        and rating is not None
        and card.positions
        and card.league_id is not None
        and card.nation_id is not None
        and card.club_id is not None
    ):
        try:
            solver_card = solver_models.Card(
                card_id=f"club:{item.item_id}",
                resource_id=card.resource_id,
                asset_id=card.asset_id,
                name=card.name or "",
                rating=rating,
                positions=card.positions,
                league_id=card.league_id,
                nation_id=card.nation_id,
                club_id=card.club_id,
                source="club",
                untradeable=bool(item.untradeable),
                duplicate=bool(item.duplicate),
                in_sbc_storage=item.location == "storage",
                price=used,
            )
        except ValidationError:
            pass
        else:
            return card_cost(solver_card, solver_models.ValuationSettings())
    if item.untradeable:
        return 0
    return round(used * TRADEABLE_FACTOR)


def _meta(stats: dict | None, card: Card | None) -> tuple[float | None, str | None]:
    """Meta rating de la carta en el rol de su primera posición (None sin stats)."""
    if not stats or card is None or not card.positions:
        return None, None
    role = role_for(card.positions[0])
    attrs = PlayerAttributes(**{k: v for k, v in stats.items() if k in STATS})
    return round(meta_rating(attrs, role), 1), role


@router.get("/club", response_model=ClubPage)
def get_club(
    session: DbSession,
    min_rating: int | None = None,
    max_rating: int | None = None,
    league_id: int | None = None,
    position: str | None = None,
    untradeable: bool | None = None,
    location: str | None = None,
    max_age_days: Annotated[int | None, Query(ge=0)] = 30,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=500)] = 100,
) -> ClubPage:
    rating = func.coalesce(Card.rating, ClubItem.rating)
    stmt = (
        select(ClubItem, Card)
        .outerjoin(Card, Card.resource_id == ClubItem.resource_id)
        .order_by(rating.desc(), Card.name.asc().nulls_last(), ClubItem.item_id)
    )
    if location is None:
        stmt = stmt.where(ClubItem.location.is_distinct_from("watchlist"))
    else:
        stmt = stmt.where(ClubItem.location == location)
    # La importación es pasiva y no ve bajas: lo no visto en `max_age_days` se oculta (0/None = todo).
    now = datetime.now(UTC)
    if max_age_days:
        stmt = stmt.where(ClubItem.seen_at >= now - timedelta(days=max_age_days))
    if min_rating is not None:
        stmt = stmt.where(rating >= min_rating)
    if max_rating is not None:
        stmt = stmt.where(rating <= max_rating)
    if league_id is not None:
        stmt = stmt.where(Card.league_id == league_id)
    if position is not None:
        stmt = stmt.where(literal(position) == any_(Card.positions))
    if untradeable is not None:
        stmt = stmt.where(func.coalesce(ClubItem.untradeable, False) == untradeable)

    pairs = [(i, c) for i, c in session.execute(stmt)]
    resource_ids = {i.resource_id for i, _ in pairs if i.resource_id is not None}
    effective = effective_prices(session, resource_ids, now)
    stats_by_rid = {
        rid: stats
        for rid, stats in session.execute(
            select(CardAttributes.resource_id, CardAttributes.stats).where(
                CardAttributes.resource_id.in_(resource_ids)
            )
        )
    }

    rows: list[ClubRow] = []
    for item, card in pairs:
        meta, meta_role = _meta(stats_by_rid.get(item.resource_id or -1), card)
        price, source = _price_used(item, effective.get(item.resource_id or -1))
        rows.append(
            ClubRow(
                item_id=item.item_id,
                resource_id=item.resource_id,
                name=card.name if card else None,
                rating=card.rating if card and card.rating is not None else item.rating,
                positions=(card.positions or []) if card else [],
                league_id=card.league_id if card else None,
                nation_id=card.nation_id if card else None,
                club_id=card.club_id if card else None,
                rarity_name=card.rarity_name if card else None,
                untradeable=bool(item.untradeable),
                location=item.location,
                duplicate=bool(item.duplicate),
                loan=bool(item.loan),
                price=price,
                price_source=source,
                value=_value(item, card, price),
                seen_at=item.seen_at,
                meta=meta,
                meta_role=meta_role,
            )
        )
    summary = ClubSummary(
        count=len(rows),
        value=sum(r.value for r in rows),
        untradeable=sum(r.untradeable for r in rows),
        unknown_cards=sum(card is None for _, card in pairs),
    )
    start = (page - 1) * page_size
    return ClubPage(items=rows[start : start + page_size], total=len(rows), summary=summary)


@router.post("/club/forget", dependencies=[Depends(require_token)])
def forget_club(body: ForgetBody, session: DbSession) -> dict[str, int]:
    """Borra las cartas no vistas en `older_than_days` días (o nunca vistas)."""
    cutoff = datetime.now(UTC) - timedelta(days=body.older_than_days)
    result = session.execute(
        delete(ClubItem).where(or_(ClubItem.seen_at.is_(None), ClubItem.seen_at < cutoff))
    )
    session.commit()
    return {"deleted": result.rowcount or 0}


def _count(session: Session, column: Any) -> int:
    return session.scalar(select(func.count()).select_from(column)) or 0


@router.get("/data/status")
def data_status(session: DbSession) -> dict[str, Any]:
    prices = {
        source: n
        for source, n in session.execute(select(Price.source, func.count()).group_by(Price.source))
    }
    latest = (
        select(SyncRun.kind, func.max(SyncRun.id).label("id")).group_by(SyncRun.kind).subquery()
    )
    runs = session.scalars(select(SyncRun).join(latest, SyncRun.id == latest.c.id))
    return {
        "cards": _count(session, Card),
        "prices": prices,
        "club_items": _count(session, ClubItem),
        "last_sync": {
            r.kind: {
                "status": r.status,
                "finished_at": r.finished_at.isoformat() if r.finished_at else None,
                "items": r.items,
                "error": r.error,
            }
            for r in runs
        },
    }
