"""Catálogo de SBC y resolverlos con tu club."""

from typing import Annotated, Literal

from fastapi import APIRouter, HTTPException, Query

from ..sbc import catalog
from ..sbc.models import SbcChallenge, SbcChallengeSummary, SbcSolveResult
from ..sbc.service import solve_challenge
from ..solver.models import Objective
from .imports import DbSession

router = APIRouter(prefix="/sbc", tags=["sbc"])


@router.get("", response_model=list[SbcChallengeSummary])
def list_sbc() -> list[SbcChallengeSummary]:
    return catalog.summaries()


@router.get("/{challenge_id}", response_model=SbcChallenge)
def get_sbc(challenge_id: str) -> SbcChallenge:
    challenge = catalog.get(challenge_id)
    if challenge is None:
        raise HTTPException(status_code=404, detail="SBC no encontrado")
    return challenge


@router.post("/{challenge_id}/solve", response_model=SbcSolveResult)
def solve_sbc(
    challenge_id: str,
    session: DbSession,
    pool: Literal["club", "both", "market"] = "club",
    objective: Objective = Objective.CHEAPEST,
    time_limit_s: Annotated[float, Query(gt=0, le=60)] = 10.0,
) -> SbcSolveResult:
    challenge = catalog.get(challenge_id)
    if challenge is None:
        raise HTTPException(status_code=404, detail="SBC no encontrado")
    return solve_challenge(
        challenge, session, pool=pool, objective=objective, time_limit_s=time_limit_s
    )
