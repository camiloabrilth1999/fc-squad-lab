"""Valor en monedas de las recompensas de objetivos (estimación con el mercado).

- Monedas: su valor.
- Jugador: su precio de mercado (si la carta no tiene precio, el de una carta común de su media);
  las recompensas intransferibles valen una fracción (no se pueden vender, solo usar).
- Sobre: N cartas comunes de la media mínima del sobre (los nombres de EA dicen cuántas y qué
  mínimo: «Oro x3 81+»); los genéricos («grande», «jumbo») valen un número fijo de cartas de 75.
- XP, fichas de evento y accesos: no se valoran (0), pero se muestran.
"""

import re
import statistics
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models_db import Card, Catalog, Price
from ..prices import effective_prices
from .awards import describe_award

UNTRADEABLE_FACTOR = 0.5  # lo que vale un premio que no se puede vender
_GENERIC_PACKS = {"pequeño": 3, "pequeno": 3, "grande": 6, "gigante": 12, "jumbo": 12}
_METAL_RATING = {"oro": 75, "plata": 68, "bronce": 58}


@dataclass
class PriceBook:
    """Precios de referencia por media (cartas comunes) y por carta."""

    by_rating: dict[int, int] = field(default_factory=dict)
    by_card: dict[int, int] = field(default_factory=dict)
    pack_names: dict[int, str] = field(default_factory=dict)

    def at(self, rating: int) -> int:
        """Precio típico de una carta común de esa media (el más cercano disponible)."""
        if not self.by_rating:
            return 0
        if rating in self.by_rating:
            return self.by_rating[rating]
        nearest = min(self.by_rating, key=lambda r: abs(r - rating))
        return self.by_rating[nearest] if abs(nearest - rating) <= 2 else 0


def load_price_book(session: Session, resource_ids: set[int] | None = None) -> PriceBook:
    rows = session.execute(
        select(Card.rating, Price.price)
        .join(Price, Price.resource_id == Card.resource_id)
        .where(
            Price.platform == "PC",
            Price.source == "easysbc:market",
            Price.price > 0,
            Card.rarity_ea_id.in_((0, 1)),
            Card.rating.is_not(None),
        )
    ).all()
    prices: dict[int, list[int]] = {}
    for rating, price in rows:
        prices.setdefault(int(rating), []).append(int(price))
    by_rating = {r: round(statistics.median(p)) for r, p in prices.items() if len(p) >= 3}
    by_card = (
        {
            rid: p
            for rid, (p, _src) in effective_prices(session, resource_ids, datetime.now(UTC)).items()
        }
        if resource_ids
        else {}
    )
    names = {
        c.ea_id: c.name for c in session.scalars(select(Catalog).where(Catalog.kind == "pack"))
    }
    return PriceBook(by_rating=by_rating, by_card=by_card, pack_names=names)


def parse_pack(name: str) -> tuple[int, int] | None:
    """(nº de cartas, media mínima) de un sobre por su nombre, o None si no se entiende."""
    low = name.lower()
    m = re.search(r"\bx(\d+)\b(?:.*?(\d{2})\+)?", low)
    if m and m.group(2):
        return int(m.group(1)), int(m.group(2))
    m = re.search(r"(\d{2})\+", low)
    if m:
        return 1, int(m.group(1))
    m = re.search(r"(\d{2})-(\d{2})", low)  # «Oro 75-83»: usa el centro
    if m:
        return 1, (int(m.group(1)) + int(m.group(2))) // 2
    metal = next((rating for key, rating in _METAL_RATING.items() if key in low), None)
    if metal is None:
        m = re.search(r"\bx(\d+)\b", low)
        return (int(m.group(1)), 70) if m else None
    for word, count in _GENERIC_PACKS.items():
        if word in low:
            return count, metal
    return None


@dataclass(frozen=True)
class Valued:
    label: str
    value: int  # monedas estimadas
    valued: bool  # false: sin datos para valorarlo (0)


def award_value(award: Mapping[str, Any], book: PriceBook) -> Valued:
    desc = describe_award(dict(award), {}, book.pack_names)
    label = desc["label"]
    kind = str(award.get("type", ""))
    count = int(award.get("count") or 1)
    value = int(award.get("value") or 0)
    factor = UNTRADEABLE_FACTOR if award.get("untradeable") else 1.0
    if kind == "coin":
        return Valued(label, value * count, True)
    if kind == "item":
        item = award.get("item") or {}
        rid = int(item.get("resource_id", value))
        price = book.by_card.get(rid) or book.at(int(item.get("rating") or 0))
        return Valued(label, round(price * count * factor), price > 0)
    if kind == "pack":
        parsed = parse_pack(book.pack_names.get(value, ""))
        if parsed is None:
            return Valued(label, 0, False)
        n, rating = parsed
        price = book.at(rating)
        return Valued(label, round(price * n * count * factor), price > 0)
    return Valued(label, 0, True)  # XP, fichas de evento…: no se valoran


def allocate(sessions: list[list[tuple[int, int]]], budget: int) -> tuple[list[int], int]:
    """Reparte `budget` partidos entre sesiones para conseguir el mayor valor.

    Cada sesión es una lista de (partidos que hacen falta, valor) por objetivo: jugar M partidos
    completa los objetivos con `partidos ≤ M`. Devuelve (partidos a jugar por sesión, valor).
    """
    best: list[dict[int, tuple[int, list[int]]]] = [{0: (0, [])}]
    for tasks in sessions:
        steps = sorted({m for m, _ in tasks})
        options = [(0, 0)] + [(m, sum(v for mm, v in tasks if mm <= m)) for m in steps]
        nxt: dict[int, tuple[int, list[int]]] = {}
        for used, (val, plays) in best[-1].items():
            for m, v in options:
                total = used + m
                if total > budget:
                    continue
                cand = (val + v, [*plays, m])
                if total not in nxt or cand[0] > nxt[total][0]:
                    nxt[total] = cand
        best.append(nxt)
    value, plays = max(best[-1].values(), key=lambda x: x[0])
    return plays, value
