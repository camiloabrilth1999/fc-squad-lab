"""Orquesta el solver: pool -> elegibilidad -> modelo CP-SAT -> métricas.

Nunca lanza por resultados del solver: infeasible/unknown vuelven como `Solution`.
"""

import time

from .chemistry import player_chemistry, team_chemistry
from .cpsat import build_base_model, eligibility_problem, include_card, solve_model
from .models import Assignment, Objective, Solution, SolveRequest
from .pool import build_pool
from .rating import team_rating
from .requirements import apply_requirement
from .valuation import card_cost, objective_coefficient, objective_terms

_POOL_ORDER = ("club", "both", "market")
# Reserva de reloj para las métricas y la respuesta tras el solve.
SAFETY_S = 0.5
# Tiempo mínimo que recibe el solver aunque la poda haya agotado el presupuesto.
MIN_SOLVE_S = 0.05
# Tras resolver en posición, solo se intenta el modelo completo (fuera de posición)
# si queda al menos este reloj: en pools pequeños sobra tiempo y puede abaratar
# colocando fuera de posición; en pools grandes el intento en posición ya agotó el
# presupuesto y no merece la pena reempezar un modelo mucho mayor sin tiempo.
WARM_FULL_MIN_S = 1.0


def _infeasible(pool: str, message: str) -> Solution:
    return Solution(status="infeasible", pool=pool, message=message)


def _solve_once(
    cards: list,
    slots: list,
    costs: list[int],
    requirements: list,
    include_ids: list[str],
    index: dict[str, int],
    objective: Objective,
    time_limit_s: float,
    *,
    in_position_only: bool,
) -> tuple[str, list[Assignment], float]:
    m = build_base_model(cards, slots, costs, in_position_only=in_position_only)
    for requirement in requirements:
        apply_requirement(m, requirement)
    for card_id in include_ids:
        include_card(m, index[card_id])
    return solve_model(m, objective_terms(m, costs, objective), time_limit_s)


def _coefficients(cards: list, costs: list[int], objective: Objective) -> dict[str, int]:
    """Coeficiente del objetivo por card_id, para comparar dos soluciones."""
    return {c.card_id: objective_coefficient(c, costs[i], objective) for i, c in enumerate(cards)}


def _objective_value(assignments: list[Assignment], coef: dict[str, int]) -> int:
    return sum(coef[a.card_id] for a in assignments)


def solve(req: SolveRequest) -> Solution:
    """Resuelve un pool. `req.time_limit_s` es reloj total: incluye poda y modelo."""
    deadline = time.perf_counter() + req.time_limit_s
    cards = build_pool(
        req.cards,
        req.pool,
        req.slots,
        req.requirements,
        req.include_card_ids,
        req.exclude_card_ids,
    )
    in_pool = {c.card_id for c in cards}
    for card_id in req.include_card_ids:
        if card_id not in in_pool:
            return _infeasible(req.pool, f"Jugador incluido no disponible: {card_id}")

    problem = eligibility_problem(cards, req.slots)
    if problem:
        return _infeasible(req.pool, problem)

    costs = [card_cost(c, req.valuation) for c in cards]
    index = {c.card_id: i for i, c in enumerate(cards)}
    coef = _coefficients(cards, costs, req.objective)

    def remaining() -> float:
        return max(MIN_SOLVE_S, deadline - time.perf_counter() - SAFETY_S)

    def run(in_position_only: bool, budget: float) -> tuple[str, list[Assignment], float]:
        return _solve_once(
            cards,
            req.slots,
            costs,
            req.requirements,
            req.include_card_ids,
            index,
            req.objective,
            budget,
            in_position_only=in_position_only,
        )

    # Primero en posición: para pools grandes es el modelo que resuelve a tiempo y
    # suele ser casi óptimo; si algún hueco no tiene su posición (p. ej. ningún CF)
    # es infactible al instante y pasamos al modelo completo. Luego, si queda reloj
    # (pools pequeños), el modelo completo puede mejorar colocando fuera de posición.
    status, assignments, seconds = run(in_position_only=True, budget=remaining())
    if not assignments or remaining() > WARM_FULL_MIN_S:
        f_status, f_assignments, f_seconds = run(in_position_only=False, budget=remaining())
        better = f_assignments and (
            not assignments
            or _objective_value(f_assignments, coef) < _objective_value(assignments, coef)
        )
        if better:
            status, assignments, seconds = f_status, f_assignments, f_seconds
        elif not assignments:
            status, seconds = f_status, f_seconds  # ninguno halló: propaga el motivo

    if not assignments:
        if status == "infeasible":
            return Solution(
                status="infeasible",
                pool=req.pool,
                solve_time_s=seconds,
                message="No existe una plantilla que cumpla todos los requisitos con estas cartas",
            )
        return Solution(
            status="unknown",
            pool=req.pool,
            solve_time_s=seconds,
            message="No se encontró solución en el tiempo límite",
        )

    chosen = [cards[index[a.card_id]] for a in assignments]
    chosen_slots = [a.position for a in assignments]  # química: según el hueco real
    return Solution(
        status=status,
        pool=req.pool,
        assignments=assignments,
        cost=sum(card_cost(c, req.valuation) for c in chosen),
        team_rating=team_rating([c.rating for c in chosen]),
        team_chemistry=team_chemistry(chosen, chosen_slots),
        player_chemistry=player_chemistry(chosen, chosen_slots),
        solve_time_s=seconds,
    )


def solve_all_pools(req: SolveRequest) -> list[Solution]:
    """Resuelve club, ambos y mercado (solo mercado si no hay cartas del club).

    `req.time_limit_s` se aplica a cada pool por separado: el total puede llegar
    a 3 × `time_limit_s`.
    """
    has_club = any(c.source == "club" for c in req.cards)
    return [
        solve(req.model_copy(update={"pool": pool}))
        for pool in _POOL_ORDER
        if has_club or pool == "market"
    ]
