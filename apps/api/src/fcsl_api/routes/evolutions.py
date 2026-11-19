"""Evoluciones: importación desde la extensión (solo lectura de EA) y consulta."""

from datetime import UTC, datetime
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func, or_, select
from sqlalchemy.dialects.postgresql import insert

from ..evolutions.enums import stat_name
from ..evolutions.requirements import decode, describe
from ..evolutions.service import ClubEvaluator, Match, active_evolutions, plan
from ..models_db import Catalog, Evolution, EvolutionCategory
from .imports import DbSession, require_token

import_router = APIRouter(prefix="/import", tags=["import"], dependencies=[Depends(require_token)])
router = APIRouter(prefix="/evolutions", tags=["evolutions"])


# ----------------------------- importación ----------------------------------------------
class CategoryIn(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: int
    name: str = ""
    slot_ids: list[int] = Field(default_factory=list)


class SlotIn(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: int
    content_id: int | None = None
    name: str | None = None
    description: str | None = None
    status: str | None = None
    timed: bool = False
    end_time: int | None = None
    category_id: int | None = None
    gk_only: bool = False
    outfield_only: bool = False
    multi_choice: bool = False
    reset_count: int = 0
    total_rewards: int | None = None
    currencies: list[Any] = Field(default_factory=list)
    top_rewards: list[dict[str, Any]] = Field(default_factory=list)
    requirements: list[dict[str, Any]] = Field(default_factory=list)
    levels: list[dict[str, Any]] = Field(default_factory=list)
    bonuses: dict[str, list[dict[str, Any]]] = Field(default_factory=dict)


class ImportEvolutionsBody(BaseModel):
    categories: list[CategoryIn] = Field(default_factory=list)
    slots: list[SlotIn]


@import_router.post("/evolutions")
def import_evolutions(body: ImportEvolutionsBody, session: DbSession) -> dict[str, int]:
    """Guarda lo visto (upsert por id). Cada lectura de EA es parcial: no se borra nada."""
    now = datetime.now(UTC)
    if body.categories:
        stmt = insert(EvolutionCategory).values(
            [{"id": c.id, "name": c.name, "slot_ids": c.slot_ids} for c in body.categories]
        )
        session.execute(
            stmt.on_conflict_do_update(
                index_elements=[EvolutionCategory.id],
                set_={"name": stmt.excluded.name, "slot_ids": stmt.excluded.slot_ids},
            )
        )
    if body.slots:
        rows = [
            {
                "slot_id": s.id,
                "content_id": s.content_id,
                "name": s.name,
                "description": s.description,
                "status": s.status,
                "timed": s.timed,
                "end_time": s.end_time,
                "category_id": s.category_id,
                "gk_only": s.gk_only,
                "outfield_only": s.outfield_only,
                "multi_choice": s.multi_choice,
                "reset_count": s.reset_count,
                "total_rewards": s.total_rewards,
                "data": {
                    "currencies": s.currencies,
                    "top_rewards": s.top_rewards,
                    "requirements": s.requirements,
                    "levels": s.levels,
                    "bonuses": s.bonuses,
                },
                "seen_at": now,
            }
            for s in {s.id: s for s in body.slots}.values()
        ]
        stmt = insert(Evolution).values(rows)
        session.execute(
            stmt.on_conflict_do_update(
                index_elements=[Evolution.slot_id],
                set_={c: stmt.excluded[c] for c in rows[0] if c != "slot_id"},
            )
        )
    session.commit()
    return {"slots": len(body.slots), "categories": len(body.categories)}


# ----------------------------- consulta -------------------------------------------------
class Reward(BaseModel):
    stat: int
    name: str
    count: int
    max_value: int | None = None


class Upgrade(BaseModel):
    stat: int
    name: str
    total: int
    initial: int | None = None


class LevelOut(BaseModel):
    level: int
    state: str | None
    objectives: list[dict[str, Any]]
    awards: list[Reward]


class EvolutionOut(BaseModel):
    id: int
    name: str | None
    description: str | None
    status: str | None
    category_id: int | None
    category: str | None
    timed: bool
    ends_at: datetime | None
    gk_only: bool
    outfield_only: bool
    multi_choice: bool
    total_rewards: int | None
    cost: list[Any]
    top_rewards: list[Reward]
    upgrades: list[Upgrade]  # mejora acumulada del último nivel sobre un jugador de ejemplo
    levels: list[LevelOut]
    requirements: list[str]  # texto como lo muestra el juego
    seen_at: datetime | None


class EvolutionsPage(BaseModel):
    items: list[EvolutionOut]
    total: int


class CategoryOut(BaseModel):
    id: int
    name: str
    total: int  # evoluciones de la categoría según EA
    imported: int  # las que ya hemos visto


def _reward(r: dict[str, Any]) -> Reward:
    return Reward(
        stat=r["stat"], name=stat_name(r["stat"]), count=r["count"], max_value=r.get("max_value")
    )


def _out(
    e: Evolution, categories: dict[int, str], names: dict[tuple[str, int], str] | None = None
) -> EvolutionOut:
    data = e.data or {}
    bonuses: dict[str, list[dict[str, Any]]] = data.get("bonuses") or {}
    last = bonuses[max(bonuses, key=int)] if bonuses else []
    return EvolutionOut(
        id=e.slot_id,
        name=e.name,
        description=e.description,
        status=e.status,
        category_id=e.category_id,
        category=categories.get(e.category_id) if e.category_id is not None else None,
        timed=e.timed,
        ends_at=datetime.fromtimestamp(e.end_time, UTC) if e.end_time else None,
        gk_only=e.gk_only,
        outfield_only=e.outfield_only,
        multi_choice=e.multi_choice,
        total_rewards=e.total_rewards,
        cost=data.get("currencies") or [],
        top_rewards=[_reward(r) for r in data.get("top_rewards") or []],
        upgrades=[
            Upgrade(
                stat=b["stat"],
                name=stat_name(b["stat"]),
                total=b["total"],
                initial=b.get("initial"),
            )
            for b in last
        ],
        levels=[
            LevelOut(
                level=lv["level"],
                state=lv.get("state"),
                objectives=lv.get("objectives") or [],
                awards=[_reward(a) for a in lv.get("awards") or []],
            )
            for lv in data.get("levels") or []
        ],
        requirements=[describe(r, names) for r in decode(data.get("requirements") or [])],
        seen_at=e.seen_at,
    )


@router.get("", response_model=EvolutionsPage)
def list_evolutions(
    session: DbSession,
    category_id: int | None = None,
    status: str | None = None,
    q: str | None = None,
    include_expired: bool = False,
    limit: Annotated[int, Query(ge=1, le=200)] = 100,
) -> EvolutionsPage:
    conds = []
    if category_id is not None:
        conds.append(Evolution.category_id == category_id)
    if status:
        conds.append(Evolution.status == status)
    if q:
        like = f"%{q.strip()}%"
        conds.append(or_(Evolution.name.ilike(like), Evolution.description.ilike(like)))
    if not include_expired:
        now = int(datetime.now(UTC).timestamp())
        conds.append(
            or_(Evolution.end_time.is_(None), Evolution.end_time == 0, Evolution.end_time > now)
        )
    total = session.scalar(select(func.count()).select_from(Evolution).where(*conds)) or 0
    rows = session.scalars(
        select(Evolution)
        .where(*conds)
        .order_by(Evolution.category_id, Evolution.end_time.nulls_last(), Evolution.slot_id)
        .limit(limit)
    ).all()
    cats = {c.id: c.name for c in session.scalars(select(EvolutionCategory))}
    names = _catalog_names(session)
    return EvolutionsPage(items=[_out(e, cats, names) for e in rows], total=total)


@router.get("/categories", response_model=list[CategoryOut])
def list_categories(session: DbSession) -> list[CategoryOut]:
    seen = dict(
        session.execute(
            select(Evolution.category_id, func.count()).group_by(Evolution.category_id)
        ).all()
    )
    cats = session.scalars(select(EvolutionCategory).order_by(EvolutionCategory.id)).all()
    return [
        CategoryOut(id=c.id, name=c.name, total=len(c.slot_ids or []), imported=seen.get(c.id, 0))
        for c in cats
    ]


def _catalog_names(session: DbSession) -> dict[tuple[str, int], str]:
    return {(c.kind, c.ea_id): c.name for c in session.scalars(select(Catalog))}


class Candidate(BaseModel):
    item_id: int
    resource_id: int
    name: str | None
    rating: int | None
    positions: list[str]
    eligible: bool | None  # True cumple; None = faltan datos para saberlo
    unknown: list[str] = Field(default_factory=list)  # requisitos que no se pudieron comprobar
    meta_before: float | None = None
    meta_after: float | None = None
    meta_gain: float | None = None
    image_path: str | None = None


class CandidatesOut(BaseModel):
    id: int
    name: str | None
    requirements: list[str]
    items: list[Candidate]
    eligible_count: int
    unknown_count: int
    total_checked: int


class CardRef(BaseModel):
    item_id: int
    resource_id: int
    name: str | None
    rating: int | None
    positions: list[str]
    image_path: str | None = None


class EvolutionRef(BaseModel):
    id: int
    name: str | None
    category: str | None = None


class ForCardItem(BaseModel):
    evolution: EvolutionRef
    eligible: bool | None
    unknown: list[str] = Field(default_factory=list)
    meta_before: float | None
    meta_after: float | None
    meta_gain: float | None


class ForCardOut(BaseModel):
    card: CardRef
    items: list[ForCardItem]


class PlanItem(BaseModel):
    evolution: EvolutionRef
    card: CardRef
    meta_before: float
    meta_after: float
    meta_gain: float


class PlanOut(BaseModel):
    assignments: list[PlanItem]
    total_gain: float
    evolutions_considered: int


def _card_ref(m: Match) -> CardRef:
    return CardRef(
        item_id=m.item_id,
        resource_id=m.resource_id,
        name=m.name,
        rating=m.rating,
        positions=m.positions,
        image_path=m.image_path,
    )


def _candidate(m: Match) -> Candidate:
    return Candidate(
        item_id=m.item_id,
        resource_id=m.resource_id,
        name=m.name,
        rating=m.rating,
        positions=m.positions,
        eligible=m.eligible,
        unknown=m.unknown,
        meta_before=m.meta_before,
        meta_after=m.meta_after,
        meta_gain=m.meta_gain,
        image_path=m.image_path,
    )


def _categories(session: DbSession) -> dict[int, str]:
    return {c.id: c.name for c in session.scalars(select(EvolutionCategory))}


@router.get("/plan", response_model=PlanOut)
def evolution_plan(
    session: DbSession,
    min_after: Annotated[float, Query(ge=0, le=100)] = 0.0,
) -> PlanOut:
    """Qué evolución dar a qué carta de tu club para subir más el meta en total.

    Cada evolución se usa una vez y cada carta una vez; solo cuentan las cartas que cumplen los
    requisitos y tienen stats detallados. `min_after` descarta resultados con meta final bajo.
    """
    evos = active_evolutions(session)
    ev = ClubEvaluator(session)
    cats = _categories(session)
    pairs = [(e, m) for e in evos for m in ev.matches(e)]
    chosen = plan(pairs, min_after=min_after)
    items = [
        PlanItem(
            evolution=EvolutionRef(id=e.slot_id, name=e.name, category=cats.get(e.category_id)),
            card=_card_ref(m),
            meta_before=m.meta_before or 0.0,
            meta_after=m.meta_after or 0.0,
            meta_gain=m.meta_gain or 0.0,
        )
        for e, m in chosen
    ]
    return PlanOut(
        assignments=items,
        total_gain=round(sum(i.meta_gain for i in items), 1),
        evolutions_considered=len(evos),
    )


@router.get("/for-card/{item_id}", response_model=ForCardOut)
def evolutions_for_card(item_id: int, session: DbSession) -> ForCardOut:
    """Las evoluciones activas que esta carta de tu club puede tomar, de mayor a menor meta final."""
    ev = ClubEvaluator(session)
    card, found = ev.for_card(item_id, active_evolutions(session))
    if card is None:
        raise HTTPException(status_code=404, detail="Carta no encontrada en tu club")
    cats = _categories(session)
    found.sort(
        key=lambda p: (
            p[1].eligible is not True,
            -(p[1].meta_after if p[1].meta_after is not None else -999.0),
        )
    )
    ref = CardRef(
        item_id=item_id,
        resource_id=card.resource_id,
        name=card.name,
        rating=card.rating,
        positions=card.positions or [],
        image_path=card.image_path,
    )
    return ForCardOut(
        card=ref,
        items=[
            ForCardItem(
                evolution=EvolutionRef(id=e.slot_id, name=e.name, category=cats.get(e.category_id)),
                eligible=m.eligible,
                unknown=m.unknown,
                meta_before=m.meta_before,
                meta_after=m.meta_after,
                meta_gain=m.meta_gain,
            )
            for e, m in found
        ],
    )


@router.get("/{slot_id}/candidates", response_model=CandidatesOut)
def candidates(
    slot_id: int,
    session: DbSession,
    include_unknown: bool = True,
    sort: Literal["after", "gain"] = "after",
    limit: Annotated[int, Query(ge=1, le=300)] = 100,
) -> CandidatesOut:
    """Cartas de tu club que cumplen los requisitos de la evolución y cuánto sube su meta.

    Orden: por defecto, mayor meta final (`after`); con `gain`, mayor mejora."""
    evo = session.get(Evolution, slot_id)
    if evo is None:
        raise HTTPException(status_code=404, detail="Evolución no encontrada")
    ev = ClubEvaluator(session)
    _, texts = ev.requirements(evo)
    found = ev.matches(evo)
    unknown_count = sum(1 for m in found if m.eligible is None)
    if not include_unknown:
        found = [m for m in found if m.eligible is not None]

    def _rank(m: Match) -> float:
        value = m.meta_after if sort == "after" else m.meta_gain
        return -(value if value is not None else -999.0)

    found.sort(key=lambda m: (m.eligible is not True, _rank(m), -(m.rating or 0)))
    return CandidatesOut(
        id=evo.slot_id,
        name=evo.name,
        requirements=texts,
        items=[_candidate(m) for m in found[:limit]],
        eligible_count=sum(1 for m in found if m.eligible),
        unknown_count=unknown_count,
        total_checked=len(ev.rows),
    )
