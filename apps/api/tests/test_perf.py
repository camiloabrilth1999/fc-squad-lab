"""Benchmark de calidad (lento): `uv run pytest -m slow -s tests/test_perf.py`.

Criterio de la spec: solución válida en < 10 s, indicando si es óptima. Se mide
la calidad a 10 s frente a la mejor conocida con 30 s.
"""

import time

import pytest

from fcsl_api.solver.chemistry import team_chemistry
from fcsl_api.solver.cpsat import build_base_model, solve_model
from fcsl_api.solver.models import (
    Objective,
    Requirement,
    RequirementKind,
    ValuationSettings,
)
from fcsl_api.solver.pool import build_pool
from fcsl_api.solver.rating import team_rating
from fcsl_api.solver.requirements import apply_requirement
from fcsl_api.solver.valuation import card_cost, objective_terms

from .synthetic import FORMATION_433, market_cards

SEEDS = range(10)
RAW_CARDS = 620  # ≈ 500 cartas tras la poda
WALL_LIMIT_S = 10.0
SAFETY_S = 1.0  # margen de reloj para poda, modelo y respuesta
BEST_KNOWN_S = 30.0
MAX_GAP = 1.02
REQS = [
    Requirement(kind=RequirementKind.TEAM_RATING, op="min", value=84),
    Requirement(kind=RequirementKind.TEAM_CHEMISTRY, op="min", value=25),
    Requirement(kind=RequirementKind.LEAGUE_PLAYERS, op="min", value=3, ids=[1]),
]


def _valid(chosen) -> bool:
    return (
        len(chosen) == len(FORMATION_433)
        and team_rating([c.rating for c in chosen]) >= 84
        and team_chemistry(chosen) >= 25
        and sum(1 for c in chosen if c.league_id == 1) >= 3
    )


def _run(seed: int, wall_limit_s: float, safety_s: float):
    cards = market_cards(RAW_CARDS, seed=seed)
    start = time.perf_counter()
    pool = build_pool(cards, "market", FORMATION_433, REQS, [], [])
    costs = [card_cost(c, ValuationSettings()) for c in pool]
    m = build_base_model(pool, FORMATION_433, costs)
    for req in REQS:
        apply_requirement(m, req)
    remaining = max(0.0, wall_limit_s - (time.perf_counter() - start) - safety_s)
    status, assignments, _ = solve_model(
        m, objective_terms(m, costs, Objective.CHEAPEST), remaining
    )
    elapsed = time.perf_counter() - start
    index = {card.card_id: c for c, card in enumerate(pool)}
    chosen_idx = [index[a.card_id] for a in assignments]
    chosen = [pool[c] for c in chosen_idx]
    cost = sum(costs[c] for c in chosen_idx) if chosen else None
    return status, elapsed, cost, chosen


@pytest.mark.slow
def test_benchmark_quality_at_10s():
    rows = []
    for seed in SEEDS:
        _, _, best_cost, _ = _run(seed, BEST_KNOWN_S, 0.0)
        status, elapsed, cost, chosen = _run(seed, WALL_LIMIT_S, SAFETY_S)
        known = [c for c in (best_cost, cost) if c is not None]
        best = min(known) if known else None  # la de 10 s también cuenta si es mejor
        gap = (cost / best - 1) * 100 if cost is not None and best else float("nan")
        rows.append((seed, status, elapsed, cost, best, gap, _valid(chosen)))
        print(
            f"seed={seed} status={status} t={elapsed:.2f}s cost_10s={cost} "
            f"best_known={best} gap={gap:.2f}% valid={_valid(chosen)}"
        )
    ok = [r for r in rows if r[1] in ("optimal", "feasible") and r[2] < WALL_LIMIT_S and r[6]]
    close = [r for r in rows if r[3] is not None and r[3] <= MAX_GAP * r[4]]
    print(f"valid < 10 s: {len(ok)}/{len(rows)}  within 2%: {len(close)}/{len(rows)}")
    assert len(ok) == len(rows)
    assert len(close) >= 8
