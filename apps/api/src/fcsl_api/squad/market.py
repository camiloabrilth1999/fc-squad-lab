"""Candidatos de mercado para el Squad Builder.

Mirar las ~20.000 cartas con stats detallados no es viable (1 ficha por segundo), así
que se acota: por cada posición de la formación, las cartas que no están dominadas en
(rating, precio) dentro del presupuesto —ninguna otra de esa posición vale más y cuesta
menos—, en varias capas. Solo a esas se les piden los stats detallados.
"""

from collections.abc import Iterable
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models_db import Card
from ..prices import effective_prices
from ..sbc.pool import _solver_card
from ..solver.models import Card as SolverCard

MIN_RATING = 70
PER_POSITION = 40


def pareto_layers(items: list[tuple[int, int, int]], want: int) -> list[int]:
    """Ids de las capas de Pareto de (id, rating, precio): más rating y menos precio.

    Capa 1 = ninguna otra carta tiene ≥ rating y ≤ precio (con alguna estricta); se retiran
    y se repite hasta juntar `want` ids o agotar las cartas.
    """
    remaining = sorted(items, key=lambda t: (-t[1], t[2], t[0]))
    chosen: list[int] = []
    while remaining and len(chosen) < want:
        frontier: list[tuple[int, int, int]] = []
        rest: list[tuple[int, int, int]] = []
        best_price: int | None = None
        for item in remaining:  # por rating desc: entra si baja el mejor precio visto
            if best_price is None or item[2] < best_price:
                frontier.append(item)
                best_price = item[2]
            else:
                rest.append(item)
        chosen.extend(i[0] for i in frontier)
        remaining = rest
    return chosen[:want]


def market_candidates(
    session: Session,
    slot_positions: Iterable[str],
    budget: int,
    now: datetime,
    *,
    per_position: int = PER_POSITION,
    min_rating: int = MIN_RATING,
) -> list[SolverCard]:
    """Cartas del mercado (con precio ≤ presupuesto) candidatas para las posiciones dadas."""
    positions = set(slot_positions)
    cards = session.scalars(
        select(Card).where(
            Card.rating >= min_rating,
            Card.league_id.is_not(None),
            Card.nation_id.is_not(None),
            Card.club_id.is_not(None),
        )
    ).all()
    prices = effective_prices(session, [c.resource_id for c in cards], now)
    by_pos: dict[str, list[tuple[int, int, int]]] = {p: [] for p in positions}
    by_id = {c.resource_id: c for c in cards}
    for c in cards:
        price = prices.get(c.resource_id)
        if price is None or price[0] > budget or not c.positions:
            continue
        pos = c.positions[0]  # la posición preferida decide dónde compite
        if pos in by_pos:
            by_pos[pos].append((c.resource_id, c.rating, price[0]))
    picked: set[int] = set()
    for items in by_pos.values():
        picked.update(pareto_layers(items, per_position))
    out: list[SolverCard] = []
    for rid in sorted(picked):
        card = by_id[rid]
        sc = _solver_card(
            f"market:{rid}", card, source="market", price=prices[rid][0], untradeable=False
        )
        if sc is not None:
            out.append(sc)
    return out
