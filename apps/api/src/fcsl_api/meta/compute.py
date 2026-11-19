"""Meta rating de una carta de la BD: stats guardados + bonus del listado de FUT.GG."""

from dataclasses import dataclass
from typing import Any, Literal

from .attributes import STATS, PlayerAttributes
from .rating import meta_rating
from .roles import role_for


@dataclass(frozen=True)
class MetaValue:
    value: float | None  # None si no hay stats ni rating de respaldo
    role: str | None
    source: Literal["stats", "rating"]


def attributes_for(stats: dict[str, int], card: Any) -> PlayerAttributes:
    """Stats + AcceleRATE, PlayStyles(+), filigranas y pie malo de la carta."""
    return PlayerAttributes(
        **{k: v for k, v in stats.items() if k in STATS},
        accelerate=getattr(card, "accelerate_type", None),
        play_styles=list(getattr(card, "play_styles", None) or []),
        play_styles_plus=list(getattr(card, "play_styles_plus", None) or []),
        skill_moves=getattr(card, "skill_moves", None) or 0,
        weak_foot=getattr(card, "weak_foot", None) or 0,
    )


def compute_meta(
    stats: dict[str, int] | None, card: Any, *, fallback_rating: int | None = None
) -> MetaValue:
    """Meta en el rol de la posición preferida de `card` (objeto con `positions`).

    Sin stats, o portero (el rol GK aún no tiene stats propios), se usa el rating
    como respaldo con `source="rating"`.
    """
    positions = getattr(card, "positions", None) or []
    if not positions:
        return MetaValue(None, None, "rating")
    pos = positions[0]
    if not stats or pos == "GK":
        rating = fallback_rating if fallback_rating is not None else getattr(card, "rating", None)
        return MetaValue(float(rating) if rating is not None else None, role_for(pos), "rating")
    role = role_for(pos)
    return MetaValue(meta_rating(attributes_for(stats, card), role), role, "stats")
