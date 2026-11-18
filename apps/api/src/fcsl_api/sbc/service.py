"""Resolver un SBC con los datos reales: carga tu club (y mercado) de la BD, llama al
solver y devuelve la plantilla con nombres, precios y el coste de lo que hay que comprar.
"""

from datetime import UTC, datetime

from sqlalchemy.orm import Session

from ..solver import service as solver_service
from ..solver.models import Card as SolverCard
from ..solver.models import Objective, RequirementKind, SolveRequest
from .models import SbcChallenge, SbcSolveResult, SquadSlot
from .pool import club_cards, market_cards

Pool = str  # "club" | "both" | "market"


def _max_rating_needed(challenge: SbcChallenge) -> int:
    """Rating máximo que puede exigir el reto, para acotar el pool de mercado."""
    ratings = [
        r.value
        for r in challenge.requirements
        if r.kind in (RequirementKind.TEAM_RATING, RequirementKind.PLAYER_RATING)
    ]
    # RATING_PLAYERS pide N jugadores con GRL ≥ min_rating: hay que traerlos.
    ratings += [
        r.min_rating
        for r in challenge.requirements
        if r.kind == RequirementKind.RATING_PLAYERS and r.min_rating is not None
    ]
    return max(ratings) if ratings else 99


def build_cards(
    challenge: SbcChallenge, session: Session, pool: Pool, now: datetime
) -> list[SolverCard]:
    cards: list[SolverCard] = []
    if pool in ("club", "both"):
        cards.extend(club_cards(session, now))
    if pool in ("market", "both"):
        cards.extend(market_cards(session, now, max_rating=_max_rating_needed(challenge)))
    return cards


def solve_challenge(
    challenge: SbcChallenge,
    session: Session,
    *,
    pool: Pool = "club",
    objective: Objective = Objective.CHEAPEST,
    time_limit_s: float = 10.0,
) -> SbcSolveResult:
    now = datetime.now(UTC)
    cards = build_cards(challenge, session, pool, now)
    result = SbcSolveResult(
        challenge_id=challenge.id,
        status="infeasible",
        pool=pool,
        objective=objective,
        formation=challenge.formation,
    )
    if not cards:
        result.message = "No hay cartas disponibles: importa tu club o sincroniza precios."
        return result

    req = SolveRequest(
        slots=challenge.slots(),
        requirements=challenge.requirements,
        cards=cards,
        pool=pool,  # type: ignore[arg-type]
        objective=objective,
        time_limit_s=time_limit_s,
    )
    solution = solver_service.solve(req)
    result.status = solution.status
    result.team_rating = solution.team_rating
    result.team_chemistry = solution.team_chemistry
    result.solve_time_s = solution.solve_time_s
    result.message = solution.message
    if not solution.assignments:
        return result

    index = {c.card_id: c for c in cards}
    squad: list[SquadSlot] = []
    spend = 0
    buys = 0
    for a in solution.assignments:
        c = index[a.card_id]
        if c.source == "market":
            buys += 1
            spend += c.price or 0
        squad.append(
            SquadSlot(
                slot_index=a.slot_index,
                position=a.position,
                card_id=c.card_id,
                resource_id=c.resource_id,
                name=c.name,
                rating=c.rating,
                positions=c.positions,
                source=c.source,
                untradeable=c.untradeable,
                price=c.price,
            )
        )
    squad.sort(key=lambda s: s.slot_index)
    result.squad = squad
    result.cost = spend
    result.buys = buys
    return result
