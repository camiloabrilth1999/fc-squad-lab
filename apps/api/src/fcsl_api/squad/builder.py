"""Squad Builder: el mejor XI de un conjunto de cartas, maximizando meta rating + química.

Solo en posición (cada carta juega en una de sus posiciones, así la química cuenta).
El solver reutiliza el modelo base y la química de `fcsl_api.solver`.
"""

import time
from typing import Literal

from ortools.sat.python import cp_model
from pydantic import BaseModel, Field

from ..solver.chemistry import MAX_PLAYER_CHEM
from ..solver.cpsat import _assignments, _run_solver, add_chemistry, build_base_model
from ..solver.models import Assignment, Card, Position
from ..solver.rating import team_rating

META_SCALE = 10  # el meta (con 1 decimal) se escala a entero para CP-SAT
DEFAULT_CHEM_WEIGHT = 1.5  # puntos de meta que vale cada punto de química


class SquadResult(BaseModel):
    status: Literal["optimal", "feasible", "infeasible", "unknown"]
    assignments: list[Assignment] = Field(default_factory=list)
    total_meta: float = 0.0
    team_rating: int = 0
    team_chemistry: int = 0
    player_chemistry: dict[str, int] = Field(default_factory=dict)
    solve_time_s: float = 0.0
    message: str | None = None


def build_squad(
    cards: list[Card],
    meta: dict[str, float],
    slots: list[Position],
    *,
    chem_weight: float = DEFAULT_CHEM_WEIGHT,
    min_chemistry: int = 0,
    exclude_card_ids: list[str] | None = None,
    time_limit_s: float = 10.0,
) -> SquadResult:
    """Mejor asignación cartas→huecos. `meta` da el meta de cada carta (por `card_id`)."""
    excluded = set(exclude_card_ids or ())
    pool = [c for c in cards if c.card_id not in excluded]
    for s in set(slots):
        if not any(s in c.positions for c in pool):
            return SquadResult(status="infeasible", message=f"Ninguna carta juega de {s}")
    m = build_base_model(pool, slots, [0] * len(pool), in_position_only=True)
    chem = add_chemistry(m)
    team_chem = sum(chem.values())
    if min_chemistry:
        m.model.add(team_chem >= min_chemistry)

    weight = round(chem_weight * META_SCALE)
    meta_terms = [
        round(meta.get(card.card_id, 0.0) * META_SCALE) * m.used[c] for c, card in enumerate(pool)
    ]
    m.model.maximize(sum(meta_terms) + weight * team_chem)

    start = time.perf_counter()
    status, _obj, values = _run_solver(m.model, time_limit_s)
    elapsed = round(time.perf_counter() - start, 3)
    if values is None:
        name = "infeasible" if status == cp_model.INFEASIBLE else "unknown"
        return SquadResult(status=name)  # type: ignore[arg-type]
    assignments = _assignments(m, values)
    by_id = {c.card_id: c for c in pool}
    chosen = [by_id[a.card_id] for a in assignments]
    player_chem = {
        card.card_id: values[chem[c].index]
        for c, card in enumerate(pool)
        if values[m.used[c].index]
    }
    return SquadResult(
        status="optimal" if status == cp_model.OPTIMAL else "feasible",
        assignments=assignments,
        total_meta=round(sum(meta.get(c.card_id, 0.0) for c in chosen), 1),
        team_rating=team_rating([c.rating for c in chosen]),
        team_chemistry=sum(player_chem.values()),
        player_chemistry=player_chem,
        solve_time_s=elapsed,
    )


__all__ = ["MAX_PLAYER_CHEM", "SquadResult", "build_squad"]
