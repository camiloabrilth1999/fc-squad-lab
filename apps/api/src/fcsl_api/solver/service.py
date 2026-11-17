"""Orquesta el solver: pool -> elegibilidad -> modelo CP-SAT -> métricas.

Nunca lanza por resultados del solver: infeasible/unknown vuelven como `Solution`.
"""

import time

from .chemistry import player_chemistry, team_chemistry
from .cpsat import build_base_model, eligibility_problem, include_card, solve_model
from .models import Solution, SolveRequest
from .pool import build_pool
from .rating import team_rating
from .requirements import apply_requirement
from .valuation import card_cost, objective_terms

_POOL_ORDER = ("club", "both", "market")
# Reserva de reloj para las métricas y la respuesta tras el solve.
SAFETY_S = 0.5
# Tiempo mínimo que recibe el solver aunque la poda haya agotado el presupuesto.
MIN_SOLVE_S = 0.05


def _infeasible(pool: str, message: str) -> Solution:
    return Solution(status="infeasible", pool=pool, message=message)


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
    m = build_base_model(cards, req.slots, costs)
    for requirement in req.requirements:
        apply_requirement(m, requirement)
    index = {c.card_id: i for i, c in enumerate(cards)}
    for card_id in req.include_card_ids:
        include_card(m, index[card_id])

    remaining = max(MIN_SOLVE_S, deadline - time.perf_counter() - SAFETY_S)
    status, assignments, seconds = solve_model(
        m, objective_terms(m, costs, req.objective), remaining
    )
    if status == "unknown":
        return Solution(
            status="unknown",
            pool=req.pool,
            solve_time_s=seconds,
            message="No se encontró solución en el tiempo límite",
        )
    if status == "infeasible":
        return Solution(
            status="infeasible",
            pool=req.pool,
            solve_time_s=seconds,
            message="No existe una plantilla que cumpla todos los requisitos con estas cartas",
        )

    chosen = [cards[index[a.card_id]] for a in assignments]
    return Solution(
        status=status,
        pool=req.pool,
        assignments=assignments,
        cost=sum(card_cost(c, req.valuation) for c in chosen),
        team_rating=team_rating([c.rating for c in chosen]),
        team_chemistry=team_chemistry(chosen),
        player_chemistry=player_chemistry(chosen),
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
