"""Meta rating precalculado de todas las cartas (`card_meta`), para la Players DB.

Por carta: el meta en el rol de su posición preferida, con stats detallados si los hay y, si
no, estimado con la cara. Se recalcula entero (`python -m fcsl_api.meta materialize`) tras
sincronizar cartas o stats. El tier sale del percentil dentro del rol, entre cartas 75+.
"""

from collections import defaultdict
from datetime import UTC, datetime

from sqlalchemy import delete, insert, select
from sqlalchemy.orm import Session

from ..models_db import Card, CardAttributes, CardMeta
from .compute import compute_meta
from .rating import tier_for

TIER_POPULATION_MIN_RATING = 75
BATCH = 2000


def materialize_meta(session: Session) -> int:
    """Recalcula `card_meta` para todas las cartas con datos; devuelve cuántas filas escribió."""
    stats = dict(session.execute(select(CardAttributes.resource_id, CardAttributes.stats)).all())
    rows: list[dict] = []
    population: dict[str, list[float]] = defaultdict(list)
    for card in session.scalars(select(Card)):
        if not card.positions:
            continue
        m = compute_meta(stats.get(card.resource_id), card)
        if m.source == "rating" or m.value is None or m.role is None:
            continue  # sin stats ni cara: no se inventa un meta
        rows.append(
            {
                "resource_id": card.resource_id,
                "role": m.role,
                "meta": round(m.value, 1),
                "source": m.source,
                "rating": card.rating or 0,
            }
        )
        if (card.rating or 0) >= TIER_POPULATION_MIN_RATING:
            population[m.role].append(m.value)
    now = datetime.now(UTC)
    values = [
        {
            "resource_id": r["resource_id"],
            "role": r["role"],
            "meta": r["meta"],
            "source": r["source"],
            "tier": tier_for(r["meta"], population[r["role"]]),
            "updated_at": now,
        }
        for r in rows
    ]
    session.execute(delete(CardMeta))
    for i in range(0, len(values), BATCH):
        session.execute(insert(CardMeta), values[i : i + BATCH])
    session.commit()
    return len(values)
