"""Meta rating de una carta de la BD: stats guardados + bonus del listado de FUT.GG."""

from dataclasses import dataclass
from typing import Any, Literal

from .attributes import ALL_STATS, PlayerAttributes
from .rating import meta_rating
from .roles import role_for

DEFAULT_HEIGHT = 182  # cm; si la carta no trae altura, no se hunde el meta


@dataclass(frozen=True)
class MetaValue:
    value: float | None  # None si no hay stats ni rating de respaldo
    role: str | None
    source: Literal["stats", "rating"]


def attributes_for(stats: dict[str, int], card: Any) -> PlayerAttributes:
    """Stats + AcceleRATE, PlayStyles(+), filigranas y pie malo de la carta."""
    return PlayerAttributes(
        **{k: v for k, v in stats.items() if k in ALL_STATS},
        accelerate=getattr(card, "accelerate_type", None),
        play_styles=list(getattr(card, "play_styles", None) or []),
        play_styles_plus=list(getattr(card, "play_styles_plus", None) or []),
        height=getattr(card, "height", None) or DEFAULT_HEIGHT,
        skill_moves=getattr(card, "skill_moves", None) or 0,
        weak_foot=getattr(card, "weak_foot", None) or 0,
    )


def compute_meta(
    stats: dict[str, int] | None,
    card: Any,
    *,
    role: str | None = None,
    fallback_rating: int | None = None,
) -> MetaValue:
    """Meta en el rol de la posición preferida de `card` (objeto con `positions`).

    Con `role` se calcula el meta en ese rol (p. ej. el del hueco donde jugaría).
    Sin stats (o un portero sin sus stats de portero) se usa el rating como respaldo
    con `source="rating"`.
    """
    positions = getattr(card, "positions", None) or []
    if not positions:
        return MetaValue(None, None, "rating")
    pos = positions[0]
    role = role or role_for(pos)  # por defecto, el rol de su posición preferida
    needs_gk = pos == "GK" or role == "goalkeeper"
    if not stats or (needs_gk and "gk_diving" not in stats):
        rating = fallback_rating if fallback_rating is not None else getattr(card, "rating", None)
        return MetaValue(float(rating) if rating is not None else None, role, "rating")
    return MetaValue(meta_rating(attributes_for(stats, card), role), role, "stats")
