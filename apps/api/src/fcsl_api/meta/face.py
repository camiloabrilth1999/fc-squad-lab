"""Meta rating a partir de los stats de la cara (para cartas sin stats detallados).

El listado de FUT.GG trae para todas las cartas los 6 stats de la cara (PAC, SHO, PAS,
DRI, DEF, PHY), los de portero y la fuerza. Con ellos más los bonus (PlayStyles, AcceleRATE,
estrellas, altura) se ajusta un modelo por rol (`python -m fcsl_api.meta fit-face`). Es
menos preciso que el de stats detallados, pero cubre las ~20.500 cartas sin bajar fichas.
"""

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from .roles import ROLES

FACE_WEIGHTS_FILE = Path(__file__).with_name("fitted_face_weights.json")
GOALKEEPER = "goalkeeper"
MAX_META = 99.9
DEFAULT_HEIGHT = 182

FACE_OUTFIELD = ["pace", "shooting", "passing", "dribbling", "defending", "physicality", "strength"]
FACE_GK = ["gk_diving", "gk_handling", "gk_kicking", "gk_reflexes", "gk_speed", "gk_positioning"]
EXTRA = ["ps_plus", "ps", "explosive", "controlled", "skill_moves", "weak_foot", "height"]
GK_EXTRA = ["ps_plus", "ps", "height"]


def face_feature_names(role: str) -> list[str]:
    return FACE_GK + GK_EXTRA if role == GOALKEEPER else FACE_OUTFIELD + EXTRA


def face_feature_vector(card: Any, role: str) -> list[float]:
    """Características de una carta (objeto con `face_stats` y los campos de bonus)."""
    face = getattr(card, "face_stats", None) or {}
    rw = ROLES[role]
    plus = sum(
        1 for p in (getattr(card, "play_styles_plus", None) or []) if p in rw.playstyles_plus
    )
    plain = sum(1 for p in (getattr(card, "play_styles", None) or []) if p in rw.playstyles_plus)
    height = float(getattr(card, "height", None) or DEFAULT_HEIGHT)
    if role == GOALKEEPER:
        return [float(face.get(k, 0)) for k in FACE_GK] + [float(plus), float(plain), height]
    acc = getattr(card, "accelerate_type", None)
    return [float(face.get(k, 0)) for k in FACE_OUTFIELD] + [
        float(plus),
        float(plain),
        1.0 if acc == "EXPLOSIVE" else 0.0,
        1.0 if acc == "CONTROLLED" else 0.0,
        float(max(0, (getattr(card, "skill_moves", None) or 0) - 3)),
        float(max(0, (getattr(card, "weak_foot", None) or 0) - 3)),
        height,
    ]


@lru_cache(maxsize=1)
def load_face_fitted(path: Path = FACE_WEIGHTS_FILE) -> dict[str, dict]:
    try:
        return json.loads(path.read_text(encoding="utf-8")).get("roles", {})
    except FileNotFoundError:
        return {}


def face_meta(card: Any, role: str) -> float | None:
    """Meta de la carta en `role` con el modelo de la cara; None sin ajuste o sin stats."""
    fit = load_face_fitted().get(role)
    if fit is None or not (getattr(card, "face_stats", None)):
        return None
    coef = fit["coef"]
    names = face_feature_names(role)
    value = fit["intercept"] + sum(
        coef.get(n, 0.0) * x for n, x in zip(names, face_feature_vector(card, role), strict=True)
    )
    return round(min(MAX_META, max(0.0, value)), 1)
