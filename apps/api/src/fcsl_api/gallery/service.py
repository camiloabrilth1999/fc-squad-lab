"""Progreso y solver de la Galería.

Coleccionar una carta = comprarla y venderla al instante al mismo precio: cuesta el 5 % de
impuesto y hace falta tener a mano el precio de la más cara (`coins_needed`). Un set suma los
puntos de sus `required` cartas de más puntos; el solver busca las cartas que faltan al menor
coste para llegar al umbral de un grado.
"""

from dataclasses import dataclass, field
from datetime import UTC, datetime

from ortools.sat.python import cp_model
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models_db import Card, ClubItem, GalleryMark
from ..prices import effective_prices
from .points import card_points
from .sets import GallerySet, in_pool, pool_condition

TAX = 0.05


@dataclass
class PoolCard:
    resource_id: int
    name: str | None
    rating: int | None
    positions: list[str]
    rarity_name: str | None
    image_path: str | None
    points: int
    exact: bool
    price: int | None
    collected: bool


@dataclass
class Selection:
    status: str  # optimal | feasible | infeasible | reached | unknown
    cards: list[PoolCard] = field(default_factory=list)
    points: int = 0
    cost: int = 0  # suma de precios de lo que hay que comprar
    tax: int = 0
    coins_needed: int = 0
    buys: int = 0


def collected_ids(session: Session) -> set[int]:
    """Coleccionadas: las del club que EA marca como tales, más/menos tus marcas manuales."""
    rows = session.scalars(
        select(ClubItem.resource_id).where(
            ClubItem.is_collected.is_(True), ClubItem.resource_id.is_not(None)
        )
    )
    ids = {r for r in rows if r is not None}
    for mark in session.scalars(select(GalleryMark)):
        if mark.collected:
            ids.add(mark.resource_id)
        else:
            ids.discard(mark.resource_id)
    return ids


def set_marks(session: Session, resource_ids: list[int], collected: bool | None) -> int:
    """Marca (True), desmarca (False) o quita la marca manual (None) de las cartas dadas."""
    ids = sorted(set(resource_ids))
    if collected is None:
        n = session.query(GalleryMark).filter(GalleryMark.resource_id.in_(ids)).delete()
    else:
        now = datetime.now(UTC)
        for rid in ids:
            session.merge(GalleryMark(resource_id=rid, collected=collected, updated_at=now))
        n = len(ids)
    session.commit()
    return n


def list_pool(
    session: Session, s: GallerySet, collected: set[int], q: str | None = None, limit: int = 60
) -> tuple[list[PoolCard], int]:
    """Cartas del set (las de más puntos primero), con filtro por nombre, para marcarlas."""
    stmt = select(Card).where(pool_condition(s))
    if q and q.strip():
        stmt = stmt.where(Card.name.ilike(f"%{q.strip()}%"))
    cards = list(
        session.scalars(stmt.order_by(Card.rating.desc().nulls_last(), Card.name).limit(limit))
    )
    prices = effective_prices(session, {c.resource_id for c in cards}, datetime.now(UTC))
    out = []
    for c in cards:
        pts, exact = _points_of(c)
        price = prices.get(c.resource_id)
        out.append(
            PoolCard(
                resource_id=c.resource_id,
                name=c.name,
                rating=c.rating,
                positions=c.positions or [],
                rarity_name=c.rarity_name,
                image_path=c.image_path,
                points=pts,
                exact=exact,
                price=price[0] if price else None,
                collected=c.resource_id in collected,
            )
        )
    out.sort(key=lambda c: (-c.points, c.name or ""))
    return out, len(cards)


def _points_of(card: Card) -> tuple[int, bool]:
    special = bool(card.rare) and card.rarity_ea_id not in (0, 1)
    p = card_points(card.rating, card.rarity_ea_id, special=special)
    return p.points, p.exact


def load_pool(session: Session, s: GallerySet, collected: set[int]) -> list[PoolCard]:
    cards = list(session.scalars(select(Card).where(pool_condition(s))))
    prices = effective_prices(session, {c.resource_id for c in cards}, datetime.now(UTC))
    out: list[PoolCard] = []
    for c in cards:
        pts, exact = _points_of(c)
        price = prices.get(c.resource_id)
        out.append(
            PoolCard(
                resource_id=c.resource_id,
                name=c.name,
                rating=c.rating,
                positions=c.positions or [],
                rarity_name=c.rarity_name,
                image_path=c.image_path,
                points=pts,
                exact=exact,
                price=price[0] if price else None,
                collected=c.resource_id in collected,
            )
        )
    return out


def progress(session: Session, sets: list[GallerySet]) -> dict[int, tuple[int, int]]:
    """{set_id: (cartas coleccionadas, puntos de las `required` mejores)} desde el club."""
    ids = collected_ids(session)
    cards = list(session.scalars(select(Card).where(Card.resource_id.in_(ids)))) if ids else []
    pts = {c.resource_id: _points_of(c)[0] for c in cards}
    out: dict[int, tuple[int, int]] = {}
    for s in sets:
        mine = sorted((pts[c.resource_id] for c in cards if in_pool(c, s)), reverse=True)
        out[s.id] = (len(mine), sum(mine[: s.required]))
    return out


def current_grade(s: GallerySet, points: int) -> str | None:
    reached = [g.name for g in s.grades if points >= g.threshold]
    return reached[-1] if reached else None


def solve_set(
    pool: list[PoolCard],
    required: int,
    threshold: int,
    *,
    complete: bool = True,
    time_limit_s: float = 5.0,
) -> Selection:
    """Elige las cartas que suman `threshold` puntos al menor coste.

    `complete=True` (como EasySBC) rellena los `required` huecos del set; con `False` se
    admiten menos cartas si bastan para el grado.
    """
    owned = sorted((c for c in pool if c.collected), key=lambda c: -c.points)[:required]
    owned_points = sum(c.points for c in owned)
    if owned_points >= threshold and (not complete or len(owned) >= required):
        return Selection(status="reached", cards=owned, points=owned_points)

    # Candidatas a comprar: para cada valor de puntos solo hacen falta las `required` más baratas.
    by_points: dict[int, list[PoolCard]] = {}
    for c in pool:
        if not c.collected and c.price is not None:
            by_points.setdefault(c.points, []).append(c)
    buyable = [
        c
        for group in by_points.values()
        for c in sorted(group, key=lambda c: c.price or 0)[:required]
    ]
    candidates = owned + buyable
    best = sum(sorted((c.points for c in candidates), reverse=True)[:required])
    if best < threshold:
        return Selection(status="infeasible")
    slots = min(required, len(candidates))

    model = cp_model.CpModel()
    x = [model.new_bool_var(f"x{i}") for i in range(len(candidates))]
    if complete:
        model.add(sum(x) == slots)
    else:
        model.add(sum(x) <= required)
    model.add(sum(c.points * v for c, v in zip(candidates, x, strict=True)) >= threshold)
    cost = [0 if c.collected else (c.price or 0) for c in candidates]
    # Primero el coste; a igualdad, menos compras.
    model.minimize(
        sum(1000 * k * v for k, v in zip(cost, x, strict=True))
        + sum(v for c, v in zip(candidates, x, strict=True) if not c.collected)
    )
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = time_limit_s
    solver.parameters.num_workers = 4
    status = solver.solve(model)
    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return Selection(status="unknown" if status == cp_model.UNKNOWN else "infeasible")

    chosen = [c for c, v in zip(candidates, x, strict=True) if solver.value(v)]
    buys = [c for c in chosen if not c.collected]
    spent = sum(c.price or 0 for c in buys)
    return Selection(
        status="optimal" if status == cp_model.OPTIMAL else "feasible",
        cards=sorted(chosen, key=lambda c: -c.points),
        points=sum(c.points for c in chosen),
        cost=spent,
        tax=round(spent * TAX),
        coins_needed=max((c.price or 0 for c in buys), default=0),
        buys=len(buys),
    )
