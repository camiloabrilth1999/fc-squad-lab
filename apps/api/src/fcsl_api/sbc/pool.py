"""Cartas del solver a partir de la BD: tu club (para resolver con lo que tienes) y
candidatos de mercado (para comprar lo que falte).

Solo entran cartas con datos completos y válidos para el solver (rating 40..99,
posiciones, liga/nación/club). El resto no puede colocarse en un hueco, así que se omite.
"""

from collections import defaultdict
from datetime import datetime

from pydantic import ValidationError
from sqlalchemy import and_, false, func, not_, or_, select
from sqlalchemy.orm import Session

from ..models_db import Card, ClubItem
from ..prices import effective_prices
from ..solver.models import Card as SolverCard

# Ubicaciones utilizables para un SBC: lo que posees y no está listado en el mercado.
USABLE_LOCATIONS = ("club", "storage")
# Candidatos de mercado por cada valor de rating (los más baratos), para acotar el pool.
MARKET_PER_RATING = 40


def _price_used(item: ClubItem, effective: tuple[int, str] | None) -> int | None:
    if effective is not None:
        return effective[0]
    if item.last_sale_price:
        return item.last_sale_price
    if item.market_min:
        return item.market_min
    return None


def _solver_card(
    card_id: str, card: Card, *, source: str, price: int | None, **extra: object
) -> SolverCard | None:
    rating = card.rating
    if (
        rating is None
        or not card.positions
        or card.league_id is None
        or card.nation_id is None
        or card.club_id is None
    ):
        return None
    try:
        return SolverCard(
            card_id=card_id,
            resource_id=card.resource_id,
            asset_id=card.asset_id,
            name=card.name or "",
            rating=rating,
            positions=card.positions,
            league_id=card.league_id,
            nation_id=card.nation_id,
            club_id=card.club_id,
            source=source,  # type: ignore[arg-type]
            price=price,
            **extra,  # type: ignore[arg-type]
        )
    except ValidationError:
        return None


def not_a_loan(now: datetime, include_loans: bool = False):
    """Condición SQL: solo lo que es tuyo; con `include_loans`, también las cesiones aún vigentes
    (las de tiempo ya caducadas no cuentan nunca)."""
    expired = and_(
        ClubItem.loan_type == "USER_TIME_LIMIT_LOAN", ClubItem.loan_value < int(now.timestamp())
    )
    if include_loans:
        return not_(func.coalesce(expired, false()))  # NULL (carta propia) = no caducada
    return or_(ClubItem.loan.is_(None), ClubItem.loan.is_(False))


def club_cards(session: Session, now: datetime, *, include_loans: bool = False) -> list[SolverCard]:
    """Tu club como cartas del solver (ubicaciones club/almacén), con precio PC.

    Las cartas cedidas (por partidos o por tiempo) no son tuyas: se excluyen salvo `include_loans`.
    """
    stmt = (
        select(ClubItem, Card)
        .join(Card, Card.resource_id == ClubItem.resource_id)
        .where(ClubItem.location.in_(USABLE_LOCATIONS), not_a_loan(now, include_loans))
    )
    pairs = [(i, c) for i, c in session.execute(stmt)]
    resource_ids = {i.resource_id for i, _ in pairs if i.resource_id is not None}
    effective = effective_prices(session, resource_ids, now)
    out: list[SolverCard] = []
    seen: set[str] = set()
    for item, card in pairs:
        card_id = f"club:{item.item_id}"
        if card_id in seen:
            continue
        price = _price_used(item, effective.get(item.resource_id or -1))
        sc = _solver_card(
            card_id,
            card,
            source="club",
            price=price,
            untradeable=bool(item.untradeable),
            duplicate=bool(item.duplicate),
            in_sbc_storage=item.location == "storage",
        )
        if sc is not None:
            out.append(sc)
            seen.add(card_id)
    return out


def market_cards(
    session: Session, now: datetime, *, max_rating: int = 99, per_rating: int = MARKET_PER_RATING
) -> list[SolverCard]:
    """Candidatos de mercado: las cartas más baratas con precio por cada rating ≤ max_rating.

    Por rating en vez de "las más baratas en total" para no perder opciones de media alta
    (un SBC de rating de equipo las necesita).
    """
    cards = session.scalars(
        select(Card).where(Card.rating.is_not(None), Card.rating <= max_rating)
    ).all()
    resource_ids = [c.resource_id for c in cards]
    effective = effective_prices(session, resource_ids, now)
    by_rating: dict[int, list[tuple[int, Card]]] = defaultdict(list)
    for card in cards:
        eff = effective.get(card.resource_id)
        if eff is None:
            continue
        by_rating[card.rating].append((eff[0], card))
    out: list[SolverCard] = []
    for rows in by_rating.values():
        rows.sort(key=lambda r: r[0])
        for price, card in rows[:per_rating]:
            sc = _solver_card(f"market:{card.resource_id}", card, source="market", price=price)
            if sc is not None:
                out.append(sc)
    return out
