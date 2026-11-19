"""Objetivos de EA: importación desde la extensión (solo lectura) y consulta con progreso."""

from datetime import UTC, datetime
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import and_, delete, func, or_, select, tuple_
from sqlalchemy.dialects.postgresql import insert

from ..ingest.store import upsert_catalog
from ..models_db import Card, Catalog, ObjectiveCategory, ObjectiveGroup
from ..objectives.awards import describe_award
from .imports import DbSession, require_token

import_router = APIRouter(prefix="/import", tags=["import"], dependencies=[Depends(require_token)])
router = APIRouter(prefix="/objectives", tags=["objectives"])

DONE_STATE = 4  # groupState de EA: 0 sin empezar, 1 en curso, 4 completado


# ----------------------------- importación ----------------------------------------------
class GroupIn(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: int
    type: int = 0
    content_id: int | None = None
    title: str | None = None
    subtitle: str | None = None
    state: int | None = None
    repeatability: str | None = None
    times_completed: int = 0
    start_time: int | None = None
    end_time: int | None = None
    visibility_time: int | None = None
    priority: int | None = None
    awards: list[dict[str, Any]] = Field(default_factory=list)
    objectives: list[dict[str, Any]] = Field(default_factory=list)


class CategoryIn(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: int
    name: str = ""
    type: int | None = None
    priority: int | None = None
    groups: list[GroupIn] = Field(default_factory=list)


class ImportObjectivesBody(BaseModel):
    categories: list[CategoryIn]


@import_router.post("/objectives")
def import_objectives(body: ImportObjectivesBody, session: DbSession) -> dict[str, int]:
    """Instantánea por categoría: lo que EA ya no lista en una categoría se borra."""
    now = datetime.now(UTC)
    n_groups = 0
    for cat in body.categories:
        stmt = insert(ObjectiveCategory).values(
            id=cat.id, name=cat.name, type=cat.type, priority=cat.priority
        )
        session.execute(
            stmt.on_conflict_do_update(
                index_elements=[ObjectiveCategory.id],
                set_={
                    "name": stmt.excluded.name,
                    "type": stmt.excluded.type,
                    "priority": stmt.excluded.priority,
                },
            )
        )
        groups = {(g.type, g.id): g for g in cat.groups}
        if groups:
            rows = [
                {
                    "group_type": g.type,
                    "group_id": g.id,
                    "category_id": cat.id,
                    "content_id": g.content_id,
                    "title": g.title,
                    "subtitle": g.subtitle,
                    "state": g.state,
                    "repeatability": g.repeatability,
                    "times_completed": g.times_completed,
                    "start_time": g.start_time,
                    "end_time": g.end_time,
                    "visibility_time": g.visibility_time,
                    "priority": g.priority,
                    "data": {"awards": g.awards, "objectives": g.objectives},
                    "seen_at": now,
                }
                for g in groups.values()
            ]
            gstmt = insert(ObjectiveGroup).values(rows)
            session.execute(
                gstmt.on_conflict_do_update(
                    index_elements=[ObjectiveGroup.group_type, ObjectiveGroup.group_id],
                    set_={
                        c: gstmt.excluded[c] for c in rows[0] if c not in ("group_type", "group_id")
                    },
                )
            )
        keep = list(groups)
        stale = delete(ObjectiveGroup).where(ObjectiveGroup.category_id == cat.id)
        if keep:
            stale = stale.where(
                tuple_(ObjectiveGroup.group_type, ObjectiveGroup.group_id).not_in(keep)
            )
        session.execute(stale)
        n_groups += len(groups)
    session.commit()
    return {"categories": len(body.categories), "groups": n_groups}


class ImportPacksBody(BaseModel):
    names: dict[str, str]


@import_router.post("/packs")
def import_pack_names(body: ImportPacksBody, session: DbSession) -> dict[str, int]:
    """Nombres de sobres (id → nombre) leídos de la tabla de traducciones de la web app."""
    entries = [
        ("pack", int(pack_id), name.strip())
        for pack_id, name in body.names.items()
        if pack_id.isdigit() and name.strip()
    ]
    return {"packs": upsert_catalog(session, entries)}


# ----------------------------- consulta -------------------------------------------------
class AwardOut(BaseModel):
    type: str
    label: str
    count: int


class TaskOut(BaseModel):
    id: int
    name: str
    description: str | None
    progress: int | None
    target: int | None
    state: str | None
    awards: list[AwardOut]


class Progress(BaseModel):
    done: int
    total: int


class GroupOut(BaseModel):
    id: int
    type: int
    title: str | None
    subtitle: str | None
    category_id: int | None
    category: str | None
    status: Literal["not_started", "in_progress", "done"]
    repeatability: str | None
    times_completed: int
    starts_at: datetime | None
    ends_at: datetime | None
    progress: Progress
    awards: list[AwardOut]
    objectives: list[TaskOut]
    seen_at: datetime | None


class ObjectivesPage(BaseModel):
    items: list[GroupOut]
    total: int


class CategoryOut(BaseModel):
    id: int
    name: str
    groups: int
    done: int


def _ts(v: int | None) -> datetime | None:
    return datetime.fromtimestamp(v, UTC) if v else None


def _status(state: int | None) -> Literal["not_started", "in_progress", "done"]:
    if state == DONE_STATE:
        return "done"
    return "not_started" if not state else "in_progress"


def _item_ids(groups: list[ObjectiveGroup]) -> set[int]:
    ids: set[int] = set()
    for g in groups:
        data = g.data or {}
        awards = list(data.get("awards") or [])
        for t in data.get("objectives") or []:
            awards.extend(t.get("awards") or [])
        for a in awards:
            item = a.get("item") or {}
            if a.get("type") == "item" and item.get("resource_id") is not None:
                ids.add(int(item["resource_id"]))
    return ids


def _awards(
    raw: list[dict[str, Any]] | None, names: dict[int, str], packs: dict[int, str]
) -> list[AwardOut]:
    return [AwardOut(**describe_award(a, names, packs)) for a in raw or []]


def _out(
    g: ObjectiveGroup, cats: dict[int, str], names: dict[int, str], packs: dict[int, str]
) -> GroupOut:
    data = g.data or {}
    tasks = data.get("objectives") or []
    return GroupOut(
        id=g.group_id,
        type=g.group_type,
        title=g.title,
        subtitle=g.subtitle,
        category_id=g.category_id,
        category=cats.get(g.category_id) if g.category_id is not None else None,
        status=_status(g.state),
        repeatability=g.repeatability,
        times_completed=g.times_completed,
        starts_at=_ts(g.start_time),
        ends_at=_ts(g.end_time),
        progress=Progress(
            done=sum(1 for t in tasks if t.get("state") == "REDEEMED"), total=len(tasks)
        ),
        awards=_awards(data.get("awards"), names, packs),
        objectives=[
            TaskOut(
                id=t["id"],
                name=t.get("name") or "",
                description=t.get("description"),
                progress=t.get("progress"),
                target=t.get("target"),
                state=t.get("state"),
                awards=_awards(t.get("awards"), names, packs),
            )
            for t in tasks
        ],
        seen_at=g.seen_at,
    )


@router.get("", response_model=ObjectivesPage)
def list_objectives(
    session: DbSession,
    category_id: int | None = None,
    status: Literal["open", "done"] | None = None,
    q: str | None = None,
    include_expired: bool = False,
    limit: Annotated[int, Query(ge=1, le=300)] = 200,
) -> ObjectivesPage:
    conds = []
    if category_id is not None:
        conds.append(ObjectiveGroup.category_id == category_id)
    if status == "done":
        conds.append(ObjectiveGroup.state == DONE_STATE)
    elif status == "open":
        conds.append(or_(ObjectiveGroup.state.is_(None), ObjectiveGroup.state != DONE_STATE))
    if q:
        like = f"%{q.strip()}%"
        conds.append(or_(ObjectiveGroup.title.ilike(like), ObjectiveGroup.subtitle.ilike(like)))
    if not include_expired:
        now = int(datetime.now(UTC).timestamp())
        conds.append(
            or_(
                ObjectiveGroup.end_time.is_(None),
                and_(ObjectiveGroup.end_time == 0),
                ObjectiveGroup.end_time > now,
            )
        )
    total = session.scalar(select(func.count()).select_from(ObjectiveGroup).where(*conds)) or 0
    groups = session.scalars(
        select(ObjectiveGroup)
        .where(*conds)
        .order_by(ObjectiveGroup.category_id, ObjectiveGroup.priority, ObjectiveGroup.group_id)
        .limit(limit)
    ).all()
    ids = _item_ids(list(groups))
    names = (
        dict(
            session.execute(
                select(Card.resource_id, Card.name).where(Card.resource_id.in_(ids))
            ).all()
        )
        if ids
        else {}
    )
    cats = {c.id: c.name for c in session.scalars(select(ObjectiveCategory))}
    packs = {
        c.ea_id: c.name for c in session.scalars(select(Catalog).where(Catalog.kind == "pack"))
    }
    return ObjectivesPage(items=[_out(g, cats, names, packs) for g in groups], total=total)


@router.get("/categories", response_model=list[CategoryOut])
def list_categories(session: DbSession) -> list[CategoryOut]:
    counts = {
        cid: (n, done)
        for cid, n, done in session.execute(
            select(
                ObjectiveGroup.category_id,
                func.count(),
                func.count().filter(ObjectiveGroup.state == DONE_STATE),
            ).group_by(ObjectiveGroup.category_id)
        )
    }
    cats = session.scalars(
        select(ObjectiveCategory).order_by(ObjectiveCategory.priority, ObjectiveCategory.id)
    ).all()
    return [
        CategoryOut(
            id=c.id,
            name=c.name,
            groups=counts.get(c.id, (0, 0))[0],
            done=counts.get(c.id, (0, 0))[1],
        )
        for c in cats
    ]
