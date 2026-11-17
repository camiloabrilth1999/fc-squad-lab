"""Modelo CP-SAT base: huecos, elegibilidad por posición, jugador único y coste."""

from collections import defaultdict
from dataclasses import dataclass

from ortools.sat.python import cp_model

from .models import Assignment, Card, Position


@dataclass
class SbcModel:
    model: cp_model.CpModel
    cards: list[Card]
    slots: list[Position]
    x: dict[tuple[int, int], cp_model.IntVar]  # (carta, hueco) -> 0/1, solo si es elegible
    used: list[cp_model.IntVar]  # used[c] = Σ_s x[c, s]
    sum_rating: cp_model.IntVar  # Σ rating·used


def eligibility_problem(cards: list[Card], slots: list[Position]) -> str | None:
    """Mensaje si es imposible cubrir los huecos por posición; None si no hay problema."""
    eligible_assets: set[int] = set()
    for pos in slots:
        eligible = [c for c in cards if pos in c.positions]
        if not eligible:
            return f"Ningún jugador puede ocupar la posición {pos}"
        eligible_assets.update(c.asset_id for c in eligible)
    if len(eligible_assets) < len(slots):
        return f"No hay suficientes jugadores distintos para {len(slots)} huecos"
    return None


def build_base_model(cards: list[Card], slots: list[Position], costs: list[int]) -> SbcModel:
    # `costs` se acepta por contrato; el objetivo llega vía `objective_terms` en solve_model.
    if len(costs) != len(cards):
        raise ValueError("costs debe tener una entrada por carta")
    model = cp_model.CpModel()
    x: dict[tuple[int, int], cp_model.IntVar] = {}
    for c, card in enumerate(cards):
        for s, pos in enumerate(slots):
            if pos in card.positions:
                x[c, s] = model.NewBoolVar(f"x_{c}_{s}")

    for s in range(len(slots)):
        model.AddExactlyOne(x[c, s] for c in range(len(cards)) if (c, s) in x)

    used: list[cp_model.IntVar] = []
    for c in range(len(cards)):
        u = model.NewIntVar(0, 1, f"used_{c}")
        model.Add(u == sum(x[c, s] for s in range(len(slots)) if (c, s) in x))
        used.append(u)

    by_asset: dict[int, list[int]] = defaultdict(list)
    for c, card in enumerate(cards):
        by_asset[card.asset_id].append(c)
    for idxs in by_asset.values():
        if len(idxs) > 1:
            model.Add(sum(used[c] for c in idxs) <= 1)

    sum_rating = model.NewIntVar(0, 99 * len(slots), "sum_rating")
    model.Add(sum_rating == sum(card.rating * used[c] for c, card in enumerate(cards)))

    return SbcModel(model, cards, slots, x, used, sum_rating)


def solve_model(
    m: SbcModel,
    objective_terms: list[tuple[int, cp_model.IntVar]],
    time_limit_s: float,
) -> tuple[str, list[Assignment], float]:
    if objective_terms:
        m.model.Minimize(sum(coef * var for coef, var in objective_terms))
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = time_limit_s
    solver.parameters.num_workers = 8
    solver.parameters.random_seed = 0
    status = solver.Solve(m.model)
    elapsed = solver.WallTime()

    if status == cp_model.MODEL_INVALID:
        raise ValueError(f"Modelo CP-SAT inválido: {m.model.Validate()}")
    if status == cp_model.OPTIMAL:
        name = "optimal"
    elif status == cp_model.FEASIBLE:
        name = "feasible"
    elif status == cp_model.INFEASIBLE:
        return "infeasible", [], elapsed
    else:
        return "unknown", [], elapsed

    assignments = [
        Assignment(slot_index=s, position=m.slots[s], card_id=m.cards[c].card_id)
        for (c, s), var in m.x.items()
        if solver.Value(var)
    ]
    assignments.sort(key=lambda a: a.slot_index)
    return name, assignments, elapsed
