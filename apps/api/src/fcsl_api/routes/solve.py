from fastapi import APIRouter

from ..solver import service
from ..solver.models import Solution, SolveRequest

router = APIRouter(prefix="/solve", tags=["solve"])


@router.post("", response_model=Solution)
def solve(req: SolveRequest) -> Solution:
    return service.solve(req)


@router.post("/pools", response_model=list[Solution])
def solve_pools(req: SolveRequest) -> list[Solution]:
    return service.solve_all_pools(req)
