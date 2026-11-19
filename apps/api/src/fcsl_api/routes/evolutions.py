"""Evoluciones: importación desde la extensión (solo lectura de EA) y consulta."""

from datetime import UTC, datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func, or_, select
from sqlalchemy.dialects.postgresql import insert

from ..evolutions.enums import stat_name
from ..models_db import Evolution, EvolutionCategory
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
    requirements: list[dict[str, Any]]
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


def _out(e: Evolution, categories: dict[int, str]) -> EvolutionOut:
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
        requirements=data.get("requirements") or [],
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
    return EvolutionsPage(items=[_out(e, cats) for e in rows], total=total)


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
