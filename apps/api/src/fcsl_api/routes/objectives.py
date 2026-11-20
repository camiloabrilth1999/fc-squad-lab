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
from ..objectives.plan import (
    WIN_RATE,
    Feasibility,
    OpenObjective,
    group_into_sessions,
    open_objectives,
    scope_label,
    squad_for,
)
from ..objectives.value import PriceBook, allocate, award_value, load_price_book
from ..squad.service import SquadBuildResponse
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


# --- plan de objetivos ------------------------------------------------------------------------


class GroupMinOut(BaseModel):
    kind: str
    id: int
    name: str
    k: int


class PlanTaskOut(BaseModel):
    objective_id: int
    group: str
    text: str
    kind: str  # play | win | goals | assists | goal_matches | multi_goal
    scope: str
    scope_label: str
    progress: int
    target: int
    remaining: int
    matches: int  # partidos estimados para completarlo él solo
    constraints: list[GroupMinOut]
    notes: list[str]
    unresolved: list[str]  # mínimos que no se pudieron traducir a una liga, nación o club
    rewards: list[str] = []  # premios en texto
    value: int = 0  # monedas estimadas de sus premios (incluye su parte del premio del grupo)
    value_known: bool = True  # false: algún premio no se pudo valorar
    done: bool = True  # con el presupuesto de partidos, ¿se completa?


class SkippedOut(BaseModel):
    objective_id: int
    group: str
    text: str
    reason: str


class CandidatesOut(BaseModel):
    plannable: list[PlanTaskOut]
    skipped: list[SkippedOut]


class SessionOut(BaseModel):
    scope: str
    label: str
    matches: int
    constraints: list[GroupMinOut]
    tasks: list[PlanTaskOut]
    squad: SquadBuildResponse | None = None
    value: int = 0  # monedas estimadas si se completa toda la sesión
    value_per_match: int = 0
    play_matches: int = 0  # partidos a jugar (con presupuesto, puede ser menos que `matches`)
    play_value: int = 0


class PlanTotals(BaseModel):
    objectives: int
    matches: int  # partidos del plan (sesiones)
    matches_separate: int  # si se jugara cada objetivo por separado
    saved: int
    value: int = 0  # monedas estimadas de todo el plan
    play_matches: int = 0  # partidos a jugar según el presupuesto
    play_value: int = 0


class ObjectivesPlanOut(BaseModel):
    sessions: list[SessionOut]
    dropped: list[SkippedOut]  # planificables pero sin plantilla posible con tu club
    skipped: list[SkippedOut]
    totals: PlanTotals
    assumptions: dict[str, float]


def _value_tasks(
    ok: list[OpenObjective], book: PriceBook
) -> dict[int, tuple[list[str], int, bool]]:
    """{objetivo: (premios, monedas, valorado)}: premios propios + su parte del premio del grupo."""
    chosen_by_group: dict[int, list[OpenObjective]] = {}
    for o in ok:
        chosen_by_group.setdefault(o.group_id, []).append(o)
    out: dict[int, tuple[list[str], int, bool]] = {}
    for o in ok:
        vals = [award_value(a, book) for a in o.awards]
        total = sum(v.value for v in vals)
        known = all(v.valued for v in vals)
        mates = chosen_by_group[o.group_id]
        if o.group_awards and len(mates) >= o.group_open:  # el grupo entero está en el plan
            gv = [award_value(a, book) for a in o.group_awards]
            total += round(sum(v.value for v in gv) / o.group_open)
            known = known and all(v.valued for v in gv)
        out[o.objective_id] = ([v.label for v in vals], total, known)
    return out


def _task_out(
    o: OpenObjective,
    valued: dict[int, tuple[list[str], int, bool]] | None = None,
    done: bool = True,
) -> PlanTaskOut:
    rewards, value, known = (valued or {}).get(o.objective_id, ([], 0, True))
    return PlanTaskOut(
        rewards=rewards,
        value=value,
        value_known=known,
        done=done,
        objective_id=o.objective_id,
        group=o.group_title,
        text=o.text,
        kind=o.task.kind,
        scope=o.task.scope,
        scope_label=scope_label(o.task.scope),
        progress=o.progress,
        target=o.target,
        remaining=o.remaining,
        matches=o.matches,
        constraints=[GroupMinOut(kind=r.kind, id=r.id, name=r.name, k=r.k) for r in o.groups],
        notes=list(o.task.notes),
        unresolved=list(o.unresolved),
    )


def _skipped_out(o: OpenObjective, reason: str | None = None) -> SkippedOut:
    return SkippedOut(
        objective_id=o.objective_id,
        group=o.group_title,
        text=o.text,
        reason=reason or o.task.reason or "ya está completado",
    )


def _book(session: DbSession, ok: list[OpenObjective]) -> PriceBook:
    rids = {
        int((a.get("item") or {}).get("resource_id", a.get("value", 0)))
        for o in ok
        for a in [*o.awards, *o.group_awards]
        if a.get("type") == "item"
    }
    return load_price_book(session, rids)


@router.get("/plan/candidates", response_model=CandidatesOut)
def plan_candidates(
    session: DbSession,
    win_rate: Annotated[float, Query(gt=0.05, le=1)] = WIN_RATE,
) -> CandidatesOut:
    """Objetivos abiertos: los que se pueden planificar y los que no (con el motivo)."""
    ok, skipped = open_objectives(session, win_rate)
    valued = _value_tasks(ok, _book(session, ok))
    return CandidatesOut(
        plannable=[_task_out(o, valued) for o in ok],
        skipped=[_skipped_out(o) for o in skipped if not o.task.plannable],
    )


@router.get("/plan/squad", response_model=SquadBuildResponse)
def plan_squad(
    session: DbSession,
    mins: Annotated[str, Query(description="mínimos: tipo:id:k separados por comas")] = "",
) -> SquadBuildResponse:
    """Mejor once de tu club con esos mínimos de liga / nación / club (p. ej. league:13:3)."""
    from ..objectives.plan import Resolved

    constraints: dict[tuple[str, int], Resolved] = {}
    for part in filter(None, (p.strip() for p in mins.split(","))):
        kind, _, rest = part.partition(":")
        ident, _, k = rest.partition(":")
        if kind in ("league", "nation", "club") and ident.isdigit() and k.isdigit():
            constraints[kind, int(ident)] = Resolved(kind, int(ident), "", int(k))
    return squad_for(session, constraints)


@router.get("/plan", response_model=ObjectivesPlanOut)
def objectives_plan(
    session: DbSession,
    ids: Annotated[str | None, Query(description="ids de objetivo separados por comas")] = None,
    win_rate: Annotated[float, Query(gt=0.05, le=1)] = WIN_RATE,
    squads: bool = False,
    budget: Annotated[int | None, Query(ge=1, description="partidos que quieres jugar")] = None,
    sort: Annotated[str, Query(pattern="^(value|matches)$")] = "value",
) -> ObjectivesPlanOut:
    """Sesiones de juego que avanzan varios objetivos a la vez, con la plantilla de cada una."""
    ok, skipped = open_objectives(session, win_rate)
    if ids:
        wanted = {int(x) for x in ids.split(",") if x.strip().isdigit()}
        ok = [o for o in ok if o.objective_id in wanted]
    sessions, dropped = group_into_sessions(ok, Feasibility(session))
    valued = _value_tasks([t for sn in sessions for t in sn.tasks], _book(session, ok))

    def session_value(sn) -> int:
        return sum(valued[t.objective_id][1] for t in sn.tasks)

    if sort == "matches":
        sessions.sort(key=lambda s: -s.matches)
    else:  # más valor por partido primero
        sessions.sort(key=lambda s: -(session_value(s) / max(s.matches, 1)))
    if budget is None:
        plays = [sn.matches for sn in sessions]
    else:
        plays, _ = allocate(
            [[(t.matches, valued[t.objective_id][1]) for t in sn.tasks] for sn in sessions], budget
        )
    cache: dict[frozenset[tuple[str, int, int]], SquadBuildResponse] = {}
    out: list[SessionOut] = []
    for sn, play in zip(sessions, plays, strict=True):
        squad = None
        if squads:
            key = frozenset((r.kind, r.id, r.k) for r in sn.constraints.values())
            if key not in cache:
                cache[key] = squad_for(session, sn.constraints)
            squad = cache[key]
        out.append(
            SessionOut(
                scope=sn.scope,
                label=scope_label(sn.scope),
                matches=sn.matches,
                constraints=[
                    GroupMinOut(kind=r.kind, id=r.id, name=r.name, k=r.k)
                    for r in sn.constraints.values()
                ],
                tasks=[
                    _task_out(t, valued, done=t.matches <= play)
                    for t in sorted(sn.tasks, key=lambda t: -t.matches)
                ],
                squad=squad,
                value=session_value(sn),
                value_per_match=round(session_value(sn) / max(sn.matches, 1)),
                play_matches=play,
                play_value=sum(valued[t.objective_id][1] for t in sn.tasks if t.matches <= play),
            )
        )
    separate = sum(t.matches for sn in sessions for t in sn.tasks)
    total = sum(sn.matches for sn in sessions)
    return ObjectivesPlanOut(
        sessions=out,
        dropped=[_skipped_out(o, "tu club no tiene jugadores para esos mínimos") for o in dropped],
        skipped=[_skipped_out(o) for o in skipped if not o.task.plannable],
        totals=PlanTotals(
            objectives=sum(len(sn.tasks) for sn in sessions),
            matches=total,
            matches_separate=separate,
            saved=max(0, separate - total),
            value=sum(session_value(sn) for sn in sessions),
            play_matches=sum(plays),
            play_value=sum(o.play_value for o in out),
        ),
        assumptions={"win_rate": win_rate, "goals_per_match": 2.0, "assists_per_match": 1.2},
    )
