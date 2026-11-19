"""Calibración del meta rating (herramienta de desarrollo, no del producto).

La referencia es el `metaRating` que EasySBC devuelve por jugador, ya descargado en la
caché de precios. Solo se usa para **ajustar nuestros pesos**: el producto calcula el meta
con stats de FUT.GG y pesos propios y no consulta EasySBC en ejecución.
"""

import glob
import json
import random
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models_db import Card, CardAttributes
from .compute import attributes_for
from .fitted import FEATURE_NAMES, feature_vector

# Familia de posición → posiciones; una familia comparte pesos (rol de `meta.roles`).
FAMILIES: dict[str, tuple[str, ...]] = {
    "adv_forward": ("ST", "CF"),
    "winger": ("LW", "RW", "LM", "RM"),
    "playmaker": ("CAM",),
    "central_mid": ("CM",),
    "box_crasher": ("CDM",),
    "falseback": ("LB", "RB", "LWB", "RWB"),
    "defender": ("CB",),
}


def load_reference(cache_dir: Path | str) -> dict[int, dict]:
    """resource_id → fila de EasySBC (con `metaRatingZeroChem`)."""
    ref: dict[int, dict] = {}
    for fl in glob.glob(str(Path(cache_dir) / "*.json")):
        with open(fl, encoding="utf-8") as f:
            data = json.load(f).get("data")
        if isinstance(data, dict):
            for p in data.get("players") or []:
                ref[p["resourceId"]] = p
    return ref


def family_of(position: str) -> str | None:
    for fam, positions in FAMILIES.items():
        if position in positions:
            return fam
    return None


def sample_resource_ids(
    session: Session,
    ref: dict[int, dict],
    *,
    per_family: int = 70,
    min_rating: int = 78,
    seed: int = 0,
) -> list[int]:
    """Muestra estratificada por familia de cartas con referencia de EasySBC."""
    by_fam: dict[str, list[int]] = defaultdict(list)
    for rid, pos, rating in session.execute(
        select(Card.resource_id, Card.positions, Card.rating).where(Card.rating >= min_rating)
    ):
        fam = family_of(pos[0]) if pos else None
        if fam and rid in ref:
            by_fam[fam].append(rid)
    rng = random.Random(seed)
    chosen: list[int] = []
    for fam in FAMILIES:
        ids = sorted(by_fam[fam])
        rng.shuffle(ids)
        chosen.extend(ids[:per_family])
    return chosen


def features(stats: dict[str, int], card) -> list[float]:
    """Vector de características de una carta de la BD (ver `fitted.feature_vector`)."""
    from .roles import role_for

    return feature_vector(attributes_for(stats, card), role_for(card.positions[0]))


@dataclass
class Dataset:
    ids: list[int]
    X: np.ndarray
    y: np.ndarray


def build_dataset(session: Session, ref: dict[int, dict], family: str) -> Dataset:
    ids, rows, ys = [], [], []
    stmt = select(Card, CardAttributes.stats).join(
        CardAttributes, CardAttributes.resource_id == Card.resource_id
    )
    for card, stats in session.execute(stmt):
        if not card.positions or family_of(card.positions[0]) != family:
            continue
        r = ref.get(card.resource_id)
        if r is None:
            continue
        ids.append(card.resource_id)
        rows.append(features(stats, card))
        ys.append(float(r["metaRatingZeroChem"]))
    return Dataset(ids, np.array(rows).reshape(len(rows), -1), np.array(ys))


@dataclass
class FitResult:
    intercept: float
    coef: dict[str, float]  # nombre de característica → coeficiente (≥ 0)
    r2: float
    cv_corr: float
    n: int


def _fit_nnls(X: np.ndarray, y: np.ndarray, ridge: float) -> tuple[float, np.ndarray]:
    """Mínimos cuadrados con coeficientes ≥ 0, intercepto libre y ridge pequeño."""
    mu, ym = X.mean(axis=0), y.mean()
    Xc, yc = X - mu, y - ym
    active = list(range(X.shape[1]))
    beta = np.zeros(X.shape[1])
    while active:
        A = Xc[:, active]
        sol = np.linalg.solve(A.T @ A + ridge * np.eye(len(active)), A.T @ yc)
        if (sol >= 0).all():
            beta[active] = sol
            break
        active.pop(int(np.argmin(sol)))  # quita el coeficiente más negativo y repite
    return float(ym - mu @ beta), beta


def _corr(a: np.ndarray, b: np.ndarray) -> float:
    if len(a) < 3 or a.std() == 0 or b.std() == 0:
        return 0.0
    return float(np.corrcoef(a, b)[0, 1])


def fit_family(ds: Dataset, *, ridge: float = 50.0, folds: int = 5, seed: int = 0) -> FitResult:
    names = FEATURE_NAMES
    keep = [j for j in range(ds.X.shape[1]) if ds.X[:, j].std() > 0]
    X, y = ds.X[:, keep], ds.y
    intercept, beta = _fit_nnls(X, y, ridge)
    pred = intercept + X @ beta
    ss_res, ss_tot = float(((y - pred) ** 2).sum()), float(((y - y.mean()) ** 2).sum())
    # validación cruzada: correlación de las predicciones fuera de muestra
    idx = np.arange(len(y))
    np.random.default_rng(seed).shuffle(idx)
    oof = np.zeros(len(y))
    for f in range(folds):
        test = idx[f::folds]
        train = np.setdiff1d(idx, test)
        b0, b = _fit_nnls(X[train], y[train], ridge)
        oof[test] = b0 + X[test] @ b
    coef = {names[keep[k]]: float(beta[k]) for k in range(len(keep)) if beta[k] > 1e-9}
    return FitResult(intercept, coef, 1 - ss_res / ss_tot if ss_tot else 0.0, _corr(oof, y), len(y))


def fit_all(session: Session, ref: dict[int, dict], min_cards: int = 40) -> dict[str, dict]:
    """Ajusta todos los roles con muestra suficiente; devuelve el contenido de `roles`."""
    out: dict[str, dict] = {}
    for fam in FAMILIES:
        ds = build_dataset(session, ref, fam)
        if len(ds.y) < min_cards:
            continue
        r = fit_family(ds)
        out[fam] = {
            "intercept": round(r.intercept, 4),
            "coef": {k: round(v, 4) for k, v in sorted(r.coef.items())},
            "n": r.n,
            "r2": round(r.r2, 3),
            "cv_corr": round(r.cv_corr, 3),
        }
    return out
