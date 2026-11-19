"""Proyección de una carta tras completar una evolución.

Las mejoras de EA llegan por nivel: cada una suma `count` a un stat con un tope `max_value`
(acumulativo). Aplicadas nivel a nivel a los stats detallados de la carta, el meta se vuelve
a calcular con el mismo modelo calibrado que el resto del producto.
"""

from dataclasses import dataclass, field
from typing import Any

from ..meta.attributes import ALL_STATS
from ..meta.compute import attributes_for
from ..meta.rating import meta_rating
from ..meta.roles import role_for

# AcademyStatEnum → nombre de nuestro stat detallado
_STAT_NAME: dict[int, str] = {
    21: "acceleration", 22: "sprint_speed", 23: "agility", 24: "balance", 25: "jumping",
    26: "stamina", 27: "strength", 28: "reactions", 29: "aggression", 30: "composure",
    31: "interceptions", 32: "positioning", 33: "vision", 34: "ball_control", 35: "crossing",
    36: "dribbling", 37: "finishing", 38: "fk_accuracy", 39: "heading", 40: "long_passing",
    41: "short_passing", 42: "def_awareness", 43: "shot_power", 44: "long_shots",
    45: "standing_tackle", 46: "sliding_tackle", 47: "volleys", 48: "curve", 49: "penalties",
    50: "gk_diving", 51: "gk_handling", 52: "gk_kicking", 53: "gk_reflexes", 54: "gk_positioning",
}  # fmt: skip
# PlayStyle de EA (301–336) → id de PlayStyle de FUT.GG (0–39) que usa nuestro modelo
_PLAYSTYLE: dict[int, int] = {
    301: 0, 302: 1, 303: 2, 304: 3, 305: 39, 306: 25, 307: 34, 308: 37, 309: 5, 310: 6,
    311: 7, 312: 8, 313: 9, 314: 38, 315: 10, 316: 11, 317: 12, 318: 13, 319: 14, 320: 35,
    321: 16, 322: 17, 323: 19, 324: 20, 325: 21, 326: 22, 327: 23, 328: 26, 329: 15, 330: 36,
    331: 28, 332: 29, 333: 30, 334: 31, 335: 32, 336: 33,
}  # fmt: skip
OVR, WEAK_FOOT, SKILL_MOVES = 11, 81, 82


@dataclass
class Projected:
    rating: int | None
    stats: dict[str, int]
    play_styles: list[int] = field(default_factory=list)
    skill_moves: int | None = None
    weak_foot: int | None = None


def _bump(current: int, count: int, cap: int | None) -> int:
    new = current + count
    return new if cap is None else max(current, min(new, cap))  # el tope nunca baja un stat


def apply_upgrades(
    levels: list[dict[str, Any]],
    card: Any,
    stats: dict[str, int] | None,
    *,
    up_to_level: int | None = None,
) -> Projected:
    """Aplica las mejoras de los niveles (hasta `up_to_level`) a los stats y rasgos de la carta."""
    out = Projected(
        rating=getattr(card, "rating", None),
        stats={k: v for k, v in (stats or {}).items() if k in ALL_STATS},
        play_styles=list(getattr(card, "play_styles", None) or []),
        skill_moves=getattr(card, "skill_moves", None),
        weak_foot=getattr(card, "weak_foot", None),
    )
    for level in sorted(levels, key=lambda lv: lv.get("level", 0)):
        if up_to_level is not None and level.get("level", 0) > up_to_level:
            break
        for a in level.get("awards") or []:
            sid, count, cap = a.get("stat"), a.get("count") or 0, a.get("max_value")
            if sid == OVR and out.rating is not None:
                out.rating = _bump(out.rating, count, cap)
            elif sid == SKILL_MOVES and out.skill_moves is not None:
                out.skill_moves = _bump(out.skill_moves, count, cap)
            elif sid == WEAK_FOOT and out.weak_foot is not None:
                out.weak_foot = _bump(out.weak_foot, count, cap)
            elif sid in _STAT_NAME and _STAT_NAME[sid] in out.stats:
                name = _STAT_NAME[sid]
                out.stats[name] = _bump(out.stats[name], count, cap)
            elif sid in _PLAYSTYLE and _PLAYSTYLE[sid] not in out.play_styles:
                out.play_styles.append(_PLAYSTYLE[sid])
    return out


def project_meta(
    card: Any,
    stats: dict[str, int] | None,
    levels: list[dict[str, Any]],
    *,
    up_to_level: int | None = None,
) -> tuple[float | None, float | None]:
    """(meta antes, meta después) en el rol de la posición preferida; (None, None) sin stats
    detallados, porque las mejoras se aplican sobre ellos."""
    positions = getattr(card, "positions", None) or []
    if not stats or not positions:
        return None, None
    role = role_for(positions[0])
    before = meta_rating(attributes_for(stats, card), role)
    after_state = apply_upgrades(levels, card, stats, up_to_level=up_to_level)
    proxy = _Proxy(card, after_state)
    after = meta_rating(attributes_for(after_state.stats, proxy), role)
    return before, after


class _Proxy:
    """La carta con sus rasgos ya evolucionados, para `attributes_for`."""

    def __init__(self, card: Any, state: Projected) -> None:
        self.accelerate_type = getattr(card, "accelerate_type", None)
        self.play_styles = state.play_styles
        self.play_styles_plus = list(getattr(card, "play_styles_plus", None) or [])
        self.skill_moves = state.skill_moves
        self.weak_foot = state.weak_foot
        self.height = getattr(card, "height", None)
