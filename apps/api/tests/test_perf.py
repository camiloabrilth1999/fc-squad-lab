"""Benchmark de rendimiento (lento): `uv run pytest -m slow -s tests/test_perf.py`."""

import time

import pytest

from fcsl_api.solver.cpsat import build_base_model, solve_model
from fcsl_api.solver.models import (
    Objective,
    Requirement,
    RequirementKind,
    ValuationSettings,
)
from fcsl_api.solver.pool import build_pool
from fcsl_api.solver.requirements import apply_requirement
from fcsl_api.solver.valuation import card_cost, objective_terms

from .synthetic import FORMATION_433, market_cards

SEEDS = range(10)
RAW_CARDS = 620  # ≈ 500 cartas tras la poda
TIME_LIMIT_S = 10.0
REQS = [
    Requirement(kind=RequirementKind.TEAM_RATING, op="min", value=84),
    Requirement(kind=RequirementKind.TEAM_CHEMISTRY, op="min", value=25),
    Requirement(kind=RequirementKind.LEAGUE_PLAYERS, op="min", value=3, ids=[1]),
]


def _run(seed: int) -> tuple[str, int, float]:
    cards = market_cards(RAW_CARDS, seed=seed)
    start = time.perf_counter()
    pool = build_pool(cards, "market", FORMATION_433, REQS, [], [])
    costs = [card_cost(c, ValuationSettings()) for c in pool]
    m = build_base_model(pool, FORMATION_433, costs)
    for req in REQS:
        apply_requirement(m, req)
    status, _, _ = solve_model(m, objective_terms(m, costs, Objective.CHEAPEST), TIME_LIMIT_S)
    return status, len(pool), time.perf_counter() - start


@pytest.mark.slow
def test_benchmark_rating_chemistry_league():
    results = []
    for seed in SEEDS:
        status, size, elapsed = _run(seed)
        results.append((seed, status, size, elapsed))
        print(f"seed={seed} pool={size} status={status} t={elapsed:.2f}s")
    optimal = sum(1 for _, status, _, elapsed in results if status == "optimal" and elapsed < 10)
    print(f"optimal < 10 s: {optimal}/{len(results)}")
    assert optimal >= 8
