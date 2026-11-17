"""Catálogo de retos SBC.

Hoy se carga de un JSON semilla (retos de ejemplo, source="seed") para que la app
funcione de punta a punta. Cuando capturemos el detalle de los SBC de EA, el adaptador
(sbc/ea.py) producirá `SbcChallenge` con source="ea" y se mezclarán aquí.
"""

import json
from functools import lru_cache
from pathlib import Path

from .models import SbcChallenge, SbcChallengeSummary

CATALOG_PATH = Path(__file__).resolve().parent / "seed_catalog.json"


@lru_cache(maxsize=1)
def _load() -> tuple[SbcChallenge, ...]:
    if not CATALOG_PATH.exists():
        return ()
    raw = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    return tuple(SbcChallenge.model_validate(c) for c in raw)


def all_challenges() -> list[SbcChallenge]:
    return list(_load())


def summaries() -> list[SbcChallengeSummary]:
    return [SbcChallengeSummary.of(c) for c in _load()]


def get(challenge_id: str) -> SbcChallenge | None:
    return next((c for c in _load() if c.id == challenge_id), None)
