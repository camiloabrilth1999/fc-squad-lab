"""Meta rating por (carta, rol): 0–99.9.

base = media ponderada de los atributos clave del rol (normalizada por la suma de
pesos, así que los pesos no tienen que sumar 1) → 0–99.
+ bonus por cada PlayStyle+ del rol que tenga la carta
+ bonus si el AcceleRATE coincide con el preferido del rol (nunca penaliza)
+ aporte menor por filigranas/pie malo por encima de 3 estrellas
recortado a [0, 99.9]. Los pesos y bonus son nuestros y se afinan por calibración.
"""

from collections.abc import Sequence

from .attributes import PlayerAttributes
from .roles import get_role

MAX_META = 99.9
PLAYSTYLE_PLUS_BONUS = 1.5  # por cada PlayStyle+ relevante al rol
ACCELERATE_BONUS = 1.0  # si el AcceleRATE es el preferido del rol
STAR_STEP = 0.3  # por estrella de SM/WF por encima de 3


def meta_rating(attrs: PlayerAttributes, role: str) -> float:
    rw = get_role(role)
    total_w = sum(rw.key_stats.values())
    base = (
        sum(w * attrs.get(stat) for stat, w in rw.key_stats.items()) / total_w
        if total_w
        else 0.0
    )
    bonus = PLAYSTYLE_PLUS_BONUS * sum(1 for p in attrs.play_styles_plus if p in rw.playstyles_plus)
    if rw.best_accelerate is not None and attrs.accelerate == rw.best_accelerate:
        bonus += ACCELERATE_BONUS
    bonus += STAR_STEP * (max(0, attrs.skill_moves - 3) + max(0, attrs.weak_foot - 3))
    return round(min(MAX_META, max(0.0, base + bonus)), 1)


TIERS = ("S", "A+", "A", "B+", "B")
# Corte por percentil (fracción de la población ≤ score) para cada tier; ajustable.
_TIER_CUTS = (("S", 0.95), ("A+", 0.85), ("A", 0.65), ("B+", 0.40), ("B", 0.0))


def tier_for(score: float, population: Sequence[float]) -> str:
    """Tier del score según su percentil en `population` (uno de `TIERS`)."""
    if not population:
        return "B"
    rank = sum(1 for v in population if v <= score) / len(population)
    for tier, cut in _TIER_CUTS:
        if rank >= cut:
            return tier
    return "B"
