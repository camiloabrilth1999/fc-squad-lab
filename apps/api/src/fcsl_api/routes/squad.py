"""Squad Builder: el mejor XI de tu club por meta rating + química."""

from fastapi import APIRouter

from ..squad.service import SquadBuildRequest, SquadBuildResponse, build_club_squad
from .imports import DbSession

router = APIRouter(prefix="/squad", tags=["squad"])


@router.post("/build", response_model=SquadBuildResponse)
def build(req: SquadBuildRequest, session: DbSession) -> SquadBuildResponse:
    return build_club_squad(session, req)
