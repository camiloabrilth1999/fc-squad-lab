"""Pesos ajustados por regresión (calibración) y su evaluación.

`fitted_weights.json` lo genera `python -m fcsl_api.meta fit`: por rol, un intercepto y un
coeficiente ≥ 0 por característica (29 stats + bonus). Es un artefacto **nuestro**: se ajustó
contra una referencia externa en desarrollo, pero el producto solo lee este archivo.
"""

import json
from functools import lru_cache
from pathlib import Path

from .attributes import STATS, PlayerAttributes
from .roles import ROLES

WEIGHTS_FILE = Path(__file__).with_name("fitted_weights.json")
STAT_NAMES = sorted(STATS)
EXTRA_NAMES = ["ps_plus", "ps", "explosive", "controlled", "skill_moves", "weak_foot"]
FEATURE_NAMES = STAT_NAMES + EXTRA_NAMES
MAX_META = 99.9


def feature_vector(attrs: PlayerAttributes, role: str) -> list[float]:
    """Características de una carta para un rol (mismo orden que FEATURE_NAMES)."""
    rw = ROLES[role]
    return [float(attrs.get(s)) for s in STAT_NAMES] + [
        float(sum(1 for p in attrs.play_styles_plus if p in rw.playstyles_plus)),
        float(sum(1 for p in attrs.play_styles if p in rw.playstyles_plus)),
        1.0 if attrs.accelerate == "EXPLOSIVE" else 0.0,
        1.0 if attrs.accelerate == "CONTROLLED" else 0.0,
        float(max(0, attrs.skill_moves - 3)),
        float(max(0, attrs.weak_foot - 3)),
    ]


@lru_cache(maxsize=1)
def load_fitted(path: Path = WEIGHTS_FILE) -> dict[str, dict]:
    """Pesos ajustados por rol; {} si el archivo no existe."""
    try:
        return json.loads(path.read_text(encoding="utf-8")).get("roles", {})
    except FileNotFoundError:
        return {}


def fitted_meta(attrs: PlayerAttributes, role: str) -> float | None:
    """Meta con los pesos ajustados del rol; None si el rol no tiene ajuste."""
    fit = load_fitted().get(role)
    if fit is None:
        return None
    coef = fit["coef"]
    value = fit["intercept"] + sum(
        coef.get(name, 0.0) * x for name, x in zip(FEATURE_NAMES, feature_vector(attrs, role))
    )
    return round(min(MAX_META, max(0.0, value)), 1)
