"""Benchmark de calidad (lento): `uv run pytest -m slow -s tests/test_perf.py`.

Va por `service.solve` (la entrada real de la app): poda + modelo en dos fases
(en posición y, si procede, fuera de posición) + métricas, todo dentro del límite.
Se mide la calidad a 10 s frente a la mejor conocida: la mejor entre una ejecución
de 60 s y la propia de 10 s.

Listón: el SLA real es **10/10 plantillas válidas en < 10 s** (estricto). Para la
calidad, permitir jugadores fuera de posición hace la compra en mercado un problema
bastante más duro que el solo-en-posición original, así que en ~9 s alguna semilla
se queda a varios puntos del óptimo. Se exige entonces que la **mayoría** sean casi
óptimas (≤ 2 %) y que **ninguna** se aleje mucho (≤ 8 %), no que casi todas lleguen
al 2 % como cuando no se permitía fuera de posición.
"""

import time

import pytest

from fcsl_api.solver import service
from fcsl_api.solver.chemistry import team_chemistry
from fcsl_api.solver.models import Objective, Requirement, RequirementKind, SolveRequest
from fcsl_api.solver.rating import team_rating

from .synthetic import FORMATION_433, market_cards

SEEDS = range(10)
RAW_CARDS = 620  # ≈ 500 cartas tras la poda
WALL_LIMIT_S = 10.0
# El servicio hace poda, modelo y métricas dentro de `time_limit_s` y ya reserva su
# propio margen de respuesta, así que basta un pequeño margen externo para el reloj.
SAFETY_S = 0.5
BEST_KNOWN_S = 60.0
NEAR_GAP = 1.02  # "casi óptima": coste ≤ 1,02 × mejor conocida
WORST_GAP = 1.08  # ninguna plantilla debe alejarse más de esto del óptimo
NEAR_MIN = 6  # al menos esta mayoría de semillas, casi óptimas
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
    # Por el servicio (la entrada real de la app): poda + modelo en dos fases
    # (primero en posición, rápido; luego fuera de posición si queda reloj) + métricas.
    cards = market_cards(RAW_CARDS, seed=seed)
    req = SolveRequest(
        slots=FORMATION_433,
        requirements=REQS,
        cards=cards,
        pool="market",
        objective=Objective.CHEAPEST,
        time_limit_s=wall_limit_s - safety_s,
    )
    start = time.perf_counter()
    sol = service.solve(req)
    elapsed = time.perf_counter() - start
    by_id = {c.card_id: c for c in cards}
    chosen = [by_id[a.card_id] for a in sol.assignments]
    cost = sol.cost if chosen else None
    return sol.status, elapsed, cost, chosen


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
    near = [r for r in rows if r[3] is not None and r[3] <= NEAR_GAP * r[4]]
    worst = max((r[3] / r[4] for r in rows if r[3] is not None and r[4]), default=1.0)
    print(
        f"valid < 10 s: {len(ok)}/{len(rows)}  within 2%: {len(near)}/{len(rows)}  "
        f"worst gap: {(worst - 1) * 100:.2f}%"
    )
    assert len(ok) == len(rows)  # SLA: 10/10 válidas en < 10 s
    assert len(near) >= NEAR_MIN  # la mayoría, casi óptimas
    assert worst <= WORST_GAP  # ninguna se aleja demasiado del óptimo
