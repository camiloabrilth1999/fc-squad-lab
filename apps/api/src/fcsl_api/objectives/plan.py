"""Plan de objetivos: cuántos partidos jugar y con qué plantilla para avanzar varios a la vez.

Cada objetivo pide algo (ganar, marcar, jugar…) en un modo y, a veces, con mínimos de jugadores de
una liga, nación o club. Los que comparten modo y cuyos mínimos caben en un mismo once se juegan
con una sola plantilla: los partidos de una sesión avanzan todos sus objetivos a la vez, así que la
sesión dura lo que pida su objetivo más largo en lugar de la suma.
"""

import math
import re
import unicodedata
from dataclasses import dataclass, field
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models_db import Catalog, ObjectiveGroup
from ..sbc.pool import club_cards
from ..squad.service import GroupMinReq, SquadBuildRequest, SquadBuildResponse, build_club_squad
from .parse import GroupMin, Task, parse_objective

WIN_RATE = 0.6  # partidos que ganas de cada 10
GOALS_PER_MATCH = 2.0
ASSISTS_PER_MATCH = 1.2

_ONLINE_MODES = {"squad_battles", "rivals", "champions", "live", "rush"}
_MODE_LABEL = {
    "any": "Cualquier modo",
    "online": "Squad Battles, Rivals, Champions o eventos en directo",
    "squad_battles": "Squad Battles",
    "rivals": "Rivals",
    "champions": "Champions",
    "draft": "Draft",
    "rush": "Rush",
    "coop": "Cooperativo",
    "live": "Eventos en directo",
}


def scope_label(scope: str) -> str:
    if scope.startswith("event:"):
        return scope[6:].strip().capitalize()
    return _MODE_LABEL.get(scope, scope)


def _norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9 ]", "", s).strip()


_LEAGUES = {
    "premier league": "premier league",
    "laliga": "laliga ea sports",
    "serie a": "serie a",
    "bundesliga": "bundesliga",
    "ligue 1": "ligue 1",
    "mls": "major league soccer",
    "liga f": "liga f",
    "nwsl": "nwsl",
}
_NATIONS = {
    "francia": "France", "belgica": "Belgium", "paises bajos": "Netherlands",
    "ee uu": "United States", "inglaterra": "England", "italia": "Italy", "alemania": "Germany",
    "espana": "Spain", "portugal": "Portugal", "brasil": "Brazil", "argentina": "Argentina",
    "croacia": "Croatia", "dinamarca": "Denmark", "suecia": "Sweden", "noruega": "Norway",
    "polonia": "Poland", "suiza": "Switzerland", "escocia": "Scotland", "gales": "Wales",
    "irlanda": "Republic of Ireland", "japon": "Japan", "corea del sur": "Korea Republic",
    "mexico": "Mexico", "canada": "Canada", "colombia": "Colombia", "uruguay": "Uruguay",
    "marruecos": "Morocco", "senegal": "Senegal", "nigeria": "Nigeria", "austria": "Austria",
    "turquia": "Türkiye", "grecia": "Greece", "serbia": "Serbia", "ucrania": "Ukraine",
}  # fmt: skip
_CLUBS = {"fc bayern de munich": "FC Bayern München", "bayern de munich": "FC Bayern München"}
_CLUB_IDS = {"psg": 73}  # Paris Saint-Germain


@dataclass(frozen=True)
class Resolved:
    kind: str
    id: int
    name: str
    k: int


class Resolver:
    """Traduce los nombres en español de EA a ids del catálogo."""

    def __init__(self, session: Session) -> None:
        self.by_kind: dict[str, dict[str, tuple[int, str]]] = {
            "league": {},
            "nation": {},
            "club": {},
        }
        for c in session.scalars(select(Catalog).where(Catalog.kind.in_(tuple(self.by_kind)))):
            self.by_kind[c.kind].setdefault(_norm(c.name), (c.ea_id, c.name))

    def resolve(self, g: GroupMin) -> Resolved | None:
        name = re.sub(r"\s*\(.*?\)\s*", "", g.name).strip()
        key = _norm(name)
        kind = g.kind
        if kind == "league":
            target = _LEAGUES.get(key, key)
            hits = [v for n, v in self.by_kind["league"].items() if n.startswith(target)]
            return Resolved("league", *min(hits), g.k) if hits else None
        if kind == "nation":
            en = _NATIONS.get(key)
            hit = self.by_kind["nation"].get(_norm(en)) if en else self.by_kind["nation"].get(key)
            if hit:
                return Resolved("nation", *hit, g.k)
            kind = "club"  # sin nación con ese nombre: probablemente un club sin paréntesis
        if key in _CLUB_IDS:
            return Resolved("club", _CLUB_IDS[key], name, g.k)
        target = _norm(_CLUBS.get(key, name))
        hit = self.by_kind["club"].get(target)
        return Resolved("club", *hit, g.k) if hit else None


def estimate_matches(task: Task, remaining: int, win_rate: float = WIN_RATE) -> int:
    """Partidos que hacen falta para completar lo que queda (estimación con medias)."""
    if remaining <= 0:
        return 0
    if task.kind == "win":
        return math.ceil(remaining / win_rate)
    if task.kind == "goals":
        return math.ceil(remaining / GOALS_PER_MATCH)
    if task.kind == "assists":
        return math.ceil(remaining / ASSISTS_PER_MATCH)
    if task.kind == "multi_goal":  # K goles en un mismo partido: cuesta más partidos cuanto mayor K
        return remaining * (1 + task.per_match)
    return remaining  # play / goal_matches


@dataclass
class OpenObjective:
    objective_id: int
    group_id: int
    group_title: str
    text: str
    progress: int
    target: int
    task: Task
    remaining: int
    matches: int
    groups: list[Resolved] = field(default_factory=list)
    unresolved: list[str] = field(default_factory=list)
    awards: list[dict] = field(default_factory=list)  # premios del objetivo (EA)
    group_awards: list[dict] = field(default_factory=list)  # premios por completar el grupo
    group_open: int = 1  # objetivos aún abiertos en su grupo


def open_objectives(
    session: Session, win_rate: float = WIN_RATE, now: datetime | None = None
) -> tuple[list[OpenObjective], list[OpenObjective]]:
    """(planificables, no planificables) entre los objetivos que aún se pueden hacer."""
    now = now or datetime.now(UTC)
    resolver = Resolver(session)
    ok: list[OpenObjective] = []
    skipped: list[OpenObjective] = []
    for g in session.scalars(select(ObjectiveGroup)):
        if g.state == 4:
            continue
        if g.end_time and g.end_time < now.timestamp():
            continue
        open_in_group = [o for o in g.data.get("objectives", []) if o.get("state") != "REDEEMED"]
        for o in open_in_group:
            task = parse_objective(o.get("description"))
            target, progress = int(o.get("target") or 0), int(o.get("progress") or 0)
            remaining = max(0, target - progress)
            if task.plannable and task.kind in (
                "goal_matches",
                "multi_goal",
                "play",
                "win",
                "goals",
                "assists",
            ):
                remaining = remaining or task.amount
            res, bad = [], []
            for gm in task.groups:
                r = resolver.resolve(gm)
                (res if r else bad).append(r or gm.name)
            item = OpenObjective(
                objective_id=int(o["id"]),
                group_id=g.group_id,
                group_title=g.title or "Objetivos",
                text=(o.get("description") or "").replace("\xa0", " "),
                progress=progress,
                target=target,
                task=task,
                remaining=remaining,
                matches=estimate_matches(task, remaining, win_rate) if task.plannable else 0,
                groups=res,  # type: ignore[arg-type]
                unresolved=bad,  # type: ignore[arg-type]
                awards=list(o.get("awards") or []),
                group_awards=list(g.data.get("awards") or []),
                group_open=len(open_in_group),
            )
            (ok if task.plannable and remaining > 0 else skipped).append(item)
    return ok, skipped


# --- sesiones -----------------------------------------------------------------------------------


@dataclass
class Session_:
    scope: str
    tasks: list[OpenObjective] = field(default_factory=list)
    constraints: dict[tuple[str, int], Resolved] = field(default_factory=dict)

    @property
    def matches(self) -> int:
        return max((t.matches for t in self.tasks), default=0)


def _merge(
    base: dict[tuple[str, int], Resolved], extra: list[Resolved]
) -> dict[tuple[str, int], Resolved]:
    out = dict(base)
    for r in extra:
        key = (r.kind, r.id)
        if key not in out or out[key].k < r.k:
            out[key] = r
    return out


def _compatible(task_scope: str, session_scope: str) -> bool:
    if task_scope == session_scope or task_scope == "any":
        return True
    return task_scope == "online" and session_scope in _ONLINE_MODES


class Feasibility:
    """¿Existe un once de tu club con esos mínimos? (con memoria)"""

    def __init__(self, session: Session) -> None:
        self.session = session
        self.memo: dict[frozenset[tuple[str, int, int]], bool] = {}
        self._counts: dict[tuple[str, int], int] | None = None

    def _club_counts(self) -> dict[tuple[str, int], int]:
        """Cartas de tu club por liga / nación / club (descarte rápido sin llamar al solver)."""
        if self._counts is None:
            counts: dict[tuple[str, int], int] = {}
            for c in club_cards(self.session, datetime.now(UTC)):
                for kind, gid in (
                    ("league", c.league_id),
                    ("nation", c.nation_id),
                    ("club", c.club_id),
                ):
                    counts[kind, gid] = counts.get((kind, gid), 0) + 1
            self._counts = counts
        return self._counts

    def ok(self, constraints: dict[tuple[str, int], Resolved]) -> bool:
        if not constraints:
            return True
        counts = self._club_counts()
        if any(counts.get((r.kind, r.id), 0) < r.k for r in constraints.values()):
            return False
        if sum(r.k for r in constraints.values()) <= 1:
            return True  # un solo jugador de un grupo del que ya tienes
        key = frozenset((r.kind, r.id, r.k) for r in constraints.values())
        if key not in self.memo:
            res = build_club_squad(
                self.session, _request(constraints, time_limit_s=3.0, feasibility_only=True)
            )
            self.memo[key] = res.status in ("optimal", "feasible")
        return self.memo[key]


def _request(
    constraints: dict[tuple[str, int], Resolved],
    time_limit_s: float,
    *,
    feasibility_only: bool = False,
) -> SquadBuildRequest:
    return SquadBuildRequest(
        formation="442",
        feasibility_only=feasibility_only,
        time_limit_s=time_limit_s,
        min_players=[GroupMinReq(kind=r.kind, id=r.id, k=r.k) for r in constraints.values()],  # type: ignore[arg-type]
    )


def group_into_sessions(
    tasks: list[OpenObjective], feas: Feasibility
) -> tuple[list[Session_], list[OpenObjective]]:
    """Reparte los objetivos en sesiones: mismo modo y mínimos que caben en un mismo once."""
    sessions: list[Session_] = []
    dropped: list[OpenObjective] = []
    # primero los de modo concreto (los más largos antes), luego los que valen en varios modos
    rank = {"any": 2, "online": 1}
    ordered = sorted(tasks, key=lambda t: (rank.get(t.task.scope, 0), -t.matches))
    for t in ordered:
        placed = False
        candidates = [s for s in sessions if _compatible(t.task.scope, s.scope)]
        candidates.sort(key=lambda s: -s.matches)  # el que ya dura más: no añade partidos
        for s in candidates:
            merged = _merge(s.constraints, t.groups)
            if merged == s.constraints or feas.ok(merged):
                s.tasks.append(t)
                s.constraints = merged
                placed = True
                break
        if not placed:
            s = Session_(scope=t.task.scope)
            s.tasks.append(t)
            s.constraints = _merge({}, t.groups)
            if feas.ok(s.constraints) or not s.constraints:
                sessions.append(s)
            else:  # ni sola cabe en tu club: queda fuera del plan
                dropped.append(t)
    return sessions, dropped


def squad_for(session: Session, constraints: dict[tuple[str, int], Resolved]) -> SquadBuildResponse:
    return build_club_squad(session, _request(constraints, time_limit_s=6.0))
