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
    spent: int = 0  # coste de las cartas con precio usadas (las del mercado)
    out_of_position: list[str] = Field(default_factory=list)  # card_id jugando fuera de posición
    total_meta: float = 0.0
    team_rating: int = 0
    team_chemistry: int = 0
    player_chemistry: dict[str, int] = Field(default_factory=dict)
    solve_time_s: float = 0.0
    message: str | None = None


MetaValue = float | dict[str, float]  # un valor para toda posición, o uno por posición


def _meta_at(meta: dict[str, MetaValue], card_id: str, position: str) -> float:
    v = meta.get(card_id, 0.0)
    return v.get(position, 0.0) if isinstance(v, dict) else v


def build_squad(
    cards: list[Card],
    meta: dict[str, MetaValue],
    slots: list[Position],
    *,
    allowed: dict[str, set[str]] | None = None,
    max_out_of_position: int | None = None,
    prices: dict[str, int] | None = None,
    budget: int | None = None,
    chem_weight: float = DEFAULT_CHEM_WEIGHT,
    min_chemistry: int = 0,
    exclude_card_ids: list[str] | None = None,
    include_card_ids: list[str] | None = None,
    group_mins: list[tuple[str, int, int]] | None = None,
    time_limit_s: float = 10.0,
    feasibility_only: bool = False,
) -> SquadResult:
    """Mejor asignación cartas→huecos. `meta` da el meta de cada carta (por `card_id`),
    único o por posición. `allowed` (card_id → posiciones) abre el juego fuera de posición;
    sin él solo se juega en posición. `max_out_of_position` acota cuántos pueden ir fuera.
    `prices` (card_id → monedas; las cartas sin precio cuestan 0, p. ej. las del club) y
    `budget` limitan el gasto total en cartas a comprar. `include_card_ids` fija cartas en
    el once (infactible si no caben o no están en el pool). `group_mins` exige al menos
    K jugadores de una liga / nación / club: ("league" | "nation" | "club", id, K)."""
    excluded = set(exclude_card_ids or ())
    pool = [c for c in cards if c.card_id not in excluded]
    in_pool = {c.card_id for c in pool}
    missing = [i for i in (include_card_ids or []) if i not in in_pool]
    if missing:
        return SquadResult(
            status="infeasible", message=f"Carta fijada no disponible: {', '.join(missing)}"
        )

    def may_play(card: Card) -> set[str]:
        return allowed[card.card_id] if allowed is not None else set(card.positions)

    for s in set(slots):
        if not any(s in may_play(c) for c in pool):
            return SquadResult(status="infeasible", message=f"Ninguna carta juega de {s}")
    if allowed is None:
        m = build_base_model(pool, slots, [0] * len(pool), in_position_only=True)
    else:
        by_index = {c: may_play(card) for c, card in enumerate(pool)}
        m = build_base_model(pool, slots, [0] * len(pool), allowed=by_index)
    chem = add_chemistry(m)
    team_chem = sum(chem.values())
    for card_id in include_card_ids or []:  # cartas fijadas: siempre en el once
        m.model.add(m.used[next(c for c, x in enumerate(pool) if x.card_id == card_id)] == 1)
    if min_chemistry:
        m.model.add(team_chem >= min_chemistry)
    for kind, group_id, k in group_mins or []:
        members = [c for c, card in enumerate(pool) if getattr(card, f"{kind}_id") == group_id]
        m.model.add(sum(m.used[c] for c in members) >= k)
    price_of = [(prices or {}).get(card.card_id, 0) for card in pool]
    if budget is not None:  # tope al coste de lo que hay que comprar
        m.model.add(sum(p * m.used[c] for c, p in enumerate(price_of) if p) <= budget)
    if max_out_of_position is not None:
        m.model.add(sum(m.used[c] - m.inpos[c] for c in range(len(pool))) <= max_out_of_position)

    weight = round(chem_weight * META_SCALE)
    terms = []
    for (c, key), var in m.x.items():
        position = key if isinstance(key, str) else m.slots[key]
        terms.append(round(_meta_at(meta, pool[c].card_id, position) * META_SCALE) * var)
    m.model.maximize(sum(terms) + weight * team_chem)

    start = time.perf_counter()
    status, _obj, values = _run_solver(m.model, time_limit_s, first_solution=feasibility_only)
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
        out_of_position=[
            a.card_id for a in assignments if a.position not in by_id[a.card_id].positions
        ],
        spent=sum(price_of[pool.index(by_id[a.card_id])] for a in assignments),
        total_meta=round(sum(_meta_at(meta, a.card_id, a.position) for a in assignments), 1),
        team_rating=team_rating([c.rating for c in chosen]),
        team_chemistry=sum(player_chem.values()),
        player_chemistry=player_chem,
        solve_time_s=elapsed,
    )


__all__ = ["MAX_PLAYER_CHEM", "SquadResult", "build_squad"]
