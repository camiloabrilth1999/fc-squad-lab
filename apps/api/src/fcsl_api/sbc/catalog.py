"""Catálogo de retos SBC.

La fuente principal son los DCP reales capturados de EA (`ea_capture.json`, vía el
adaptador `sbc/ea.py`, source="ea"). Si no hay captura, se cae al JSON semilla de
ejemplo (`seed_catalog.json`, source="seed") para que la app siga funcionando de
punta a punta.
"""

import json
from functools import lru_cache
from pathlib import Path

from . import ea
from .models import SbcChallenge, SbcChallengeSummary

SEED_PATH = Path(__file__).resolve().parent / "seed_catalog.json"


def _load_seed() -> tuple[SbcChallenge, ...]:
    if not SEED_PATH.exists():
        return ()
    raw = json.loads(SEED_PATH.read_text(encoding="utf-8"))
    return tuple(SbcChallenge.model_validate(c) for c in raw)


@lru_cache(maxsize=1)
def _load() -> tuple[SbcChallenge, ...]:
    real = ea.load()
    return tuple(real) if real else _load_seed()


def all_challenges() -> list[SbcChallenge]:
    return list(_load())


def summaries() -> list[SbcChallengeSummary]:
    return [SbcChallengeSummary.of(c) for c in _load()]


def get(challenge_id: str) -> SbcChallenge | None:
    return next((c for c in _load() if c.id == challenge_id), None)
