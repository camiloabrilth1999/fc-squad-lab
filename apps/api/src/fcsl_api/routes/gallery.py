"""Galería: sets, progreso del club y solución de coste mínimo por grado."""

from typing import Annotated

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select

from ..gallery.plan import build_options, plan
from ..gallery.service import (
    PoolCard,
    collected_ids,
    current_grade,
    load_pool,
    progress,
    solve_set,
)
from ..gallery.sets import GallerySet, get_set, load_sets
from ..models_db import Catalog
from .imports import DbSession

router = APIRouter(prefix="/gallery", tags=["gallery"])


class GradeOut(BaseModel):
    name: str
    threshold: int
    tokens: int


class SetOut(BaseModel):
    id: int
    name: str
    group: str
    group_name: str
    required: int
    tokens: int
    badge_type: str | None
    image_path: str | None = None
    grades: list[GradeOut]
    collected: int  # cartas del set que ya tienes coleccionadas
    points: int  # puntos de tus `required` mejores coleccionadas
    grade: str | None  # grado que ya alcanzas


class SetsOut(BaseModel):
    items: list[SetOut]


class CardOut(BaseModel):
    resource_id: int
    name: str | None
    rating: int | None
    positions: list[str]
    rarity_name: str | None
    image_path: str | None
    points: int
    exact: bool  # false: puntos estimados (rareza o media no observadas)
    price: int | None
    collected: bool


class SolutionOut(BaseModel):
    set_id: int
    name: str
    grade: str
    threshold: int
    required: int
    status: str  # optimal | feasible | reached | infeasible | unknown
    points: int
    cost: int
    tax: int
    coins_needed: int
    buys: int
    estimated: bool  # alguna carta usa puntos estimados
    cards: list[CardOut]


def _card_out(c: PoolCard) -> CardOut:
    return CardOut(**{k: getattr(c, k) for k in CardOut.model_fields})


def _badge_images(session: DbSession) -> dict[tuple[str, int], str | None]:
    return {
        (c.kind, c.ea_id): c.image_path
        for c in session.scalars(
            select(Catalog).where(
                Catalog.kind.in_(("club", "league")), Catalog.image_path.is_not(None)
            )
        )
    }


@router.get("", response_model=SetsOut)
def list_sets(session: DbSession, group: str | None = None, q: str | None = None) -> SetsOut:
    sets: list[GallerySet] = [
        s
        for s in load_sets()
        if (group is None or s.group == group) and (not q or q.lower() in s.name.lower())
    ]
    done = progress(session, sets)
    images = _badge_images(session)
    items = [
        SetOut(
            id=s.id,
            name=s.name,
            group=s.group,
            group_name=s.group_name,
            required=s.required,
            tokens=s.tokens,
            badge_type=s.badge_type,
            image_path=images.get((s.badge_type or "", s.badge_id)),  # type: ignore[arg-type]
            grades=[
                GradeOut(name=g.name, threshold=g.threshold, tokens=g.tokens) for g in s.grades
            ],
            collected=done[s.id][0],
            points=done[s.id][1],
            grade=current_grade(s, done[s.id][1]),
        )
        for s in sets
    ]
    return SetsOut(items=items)


@router.get("/{set_id}/solve", response_model=SolutionOut)
def solve(
    set_id: int,
    session: DbSession,
    grade: Annotated[str, Query(pattern="^[DCBAS]$")] = "S",
    complete: bool = True,
) -> SolutionOut:
    s = get_set(set_id)
    if s is None:
        raise HTTPException(404, "Set de Galería no encontrado")
    target = next((g for g in s.grades if g.name == grade), None)
    if target is None:
        raise HTTPException(404, f"El set no tiene grado {grade}")
    pool = load_pool(session, s, collected_ids(session))
    sel = solve_set(pool, s.required, target.threshold, complete=complete)
    return SolutionOut(
        set_id=s.id,
        name=s.name,
        grade=grade,
        threshold=target.threshold,
        required=s.required,
        status=sel.status,
        points=sel.points,
        cost=sel.cost,
        tax=sel.tax,
        coins_needed=sel.coins_needed,
        buys=sel.buys,
        estimated=any(not c.exact for c in sel.cards),
        cards=[_card_out(c) for c in sel.cards],
    )


class PlanItemOut(BaseModel):
    set_id: int
    name: str
    image_path: str | None = None
    from_grade: str | None
    grade: str
    tokens: int  # fichas nuevas de este set
    points: int
    cost: int
    tax: int
    buys: int
    coins_needed: int


class PlanOut(BaseModel):
    status: str  # optimal | feasible | infeasible | unknown
    tokens: int
    tax: int
    cost: int
    transfers: int
    coins_needed: int
    sets: int
    max_tokens: int  # fichas máximas con esos límites (o en total, sin objetivo)
    items: list[PlanItemOut]


@router.get("/plan", response_model=PlanOut)
def gallery_plan(
    session: DbSession,
    target_tokens: Annotated[int | None, Query(ge=1)] = None,
    max_tax: Annotated[int | None, Query(ge=0)] = None,
    max_transfers: Annotated[int | None, Query(ge=0)] = None,
    max_sets: Annotated[int | None, Query(ge=1)] = None,
    max_coins: Annotated[int | None, Query(ge=0)] = None,
    complete: bool = True,
) -> PlanOut:
    """Plan multi-set: con `target_tokens`, el de menor impuesto; sin él, el de más fichas."""
    res = plan(
        build_options(session, complete=complete),
        target_tokens=target_tokens,
        max_tax=max_tax,
        max_transfers=max_transfers,
        max_sets=max_sets,
        max_coins=max_coins,
    )
    images = _badge_images(session)
    return PlanOut(
        status=res.status,
        tokens=res.tokens,
        tax=res.tax,
        cost=res.cost,
        transfers=res.transfers,
        coins_needed=res.coins_needed,
        sets=len(res.items),
        max_tokens=res.max_tokens,
        items=[
            PlanItemOut(
                set_id=it.set.id,
                name=it.set.name,
                image_path=images.get((it.set.badge_type or "", it.set.badge_id)),  # type: ignore[arg-type]
                from_grade=it.from_grade,
                grade=it.option.grade,
                tokens=it.option.tokens,
                points=it.option.points,
                cost=it.option.cost,
                tax=it.option.tax,
                buys=it.option.buys,
                coins_needed=it.option.coins_needed,
            )
            for it in res.items
        ],
    )
