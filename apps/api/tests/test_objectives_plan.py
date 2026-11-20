from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from fcsl_api.main import app
from fcsl_api.models_db import Catalog, ObjectiveGroup
from fcsl_api.objectives.parse import GroupMin, Task
from fcsl_api.objectives.plan import (
    OpenObjective,
    Resolved,
    Resolver,
    estimate_matches,
    group_into_sessions,
)
from fcsl_api.routes import imports


def test_estimate_matches_by_kind() -> None:
    assert estimate_matches(Task("play", 5), 5) == 5
    assert estimate_matches(Task("win", 6), 6, win_rate=0.6) == 10  # 6 victorias / 0,6
    assert estimate_matches(Task("goals", 10), 10) == 5  # 2 goles por partido
    assert estimate_matches(Task("assists", 6), 6) == 5  # 1,2 asistencias por partido
    assert estimate_matches(Task("goal_matches", 7), 7) == 7
    assert estimate_matches(Task("multi_goal", 1, per_match=2), 1) == 3
    assert estimate_matches(Task("win", 6), 0) == 0


def _obj(oid: int, scope: str, matches: int, *groups: Resolved) -> OpenObjective:
    return OpenObjective(
        objective_id=oid,
        group_id=1,
        group_title="G",
        text=f"obj {oid}",
        progress=0,
        target=1,
        task=Task("play", matches, scope=scope),
        remaining=matches,
        matches=matches,
        groups=list(groups),
    )


class _Feas:
    """Un once cabe si no pide más de 2 jugadores en total (stub del solver)."""

    def ok(self, constraints: dict[tuple[str, int], Resolved]) -> bool:
        return sum(r.k for r in constraints.values()) <= 2


FR = Resolved("nation", 18, "France", 1)
IT = Resolved("nation", 27, "Italy", 1)
PL = Resolved("league", 13, "Premier League", 2)


def test_objectives_of_the_same_mode_share_one_session_that_lasts_the_longest() -> None:
    sessions, dropped = group_into_sessions(
        [_obj(1, "rivals", 10), _obj(2, "rivals", 4), _obj(3, "rivals", 7, FR)], _Feas()
    )
    assert dropped == []
    assert len(sessions) == 1
    assert sessions[0].matches == 10  # no 21: los partidos avanzan todos a la vez
    assert sessions[0].constraints == {("nation", 18): FR}


def test_incompatible_squad_minimums_split_the_session() -> None:
    sessions, _ = group_into_sessions(
        [_obj(1, "rivals", 10, FR), _obj(2, "rivals", 6, PL)], _Feas()
    )  # 1 + 2 jugadores = 3 > 2: no caben en el mismo once
    assert len(sessions) == 2
    assert sorted(s.matches for s in sessions) == [6, 10]


def test_any_mode_objectives_piggyback_on_a_specific_mode_session() -> None:
    sessions, _ = group_into_sessions(
        [_obj(1, "champions", 8), _obj(2, "any", 5), _obj(3, "online", 6)], _Feas()
    )
    assert len(sessions) == 1 and sessions[0].scope == "champions"
    assert {t.objective_id for t in sessions[0].tasks} == {1, 2, 3}


def test_online_objectives_do_not_join_an_unrelated_mode_or_event() -> None:
    sessions, _ = group_into_sessions(
        [_obj(1, "draft", 3), _obj(2, "event:torneo x", 4), _obj(3, "online", 6)], _Feas()
    )
    # el «online» no puede jugarse en Draft ni en un torneo concreto: sesión propia
    scopes = sorted(s.scope for s in sessions)
    assert scopes == ["draft", "event:torneo x", "online"]


def test_tasks_whose_minimums_never_fit_are_dropped() -> None:
    big = Resolved("league", 13, "Premier League", 5)
    sessions, dropped = group_into_sessions([_obj(1, "rivals", 3, big)], _Feas())
    assert sessions == [] and [d.objective_id for d in dropped] == [1]


@pytest.fixture
def client(clean_db: Session) -> Iterator[TestClient]:
    def _session() -> Iterator[Session]:
        yield clean_db

    app.dependency_overrides[imports.get_db] = _session
    yield TestClient(app)
    app.dependency_overrides.clear()


def _group(gid: int, title: str, objectives: list[dict], **extra) -> ObjectiveGroup:
    return ObjectiveGroup(
        group_type=1,
        group_id=gid,
        title=title,
        state=1,
        data={"awards": [], "objectives": objectives},
        **extra,
    )


def _o(oid: int, text: str, progress: int, target: int, state: str = "IN_PROGRESS") -> dict:
    return {
        "id": oid,
        "name": f"o{oid}",
        "description": text,
        "progress": progress,
        "target": target,
        "state": state,
        "awards": [],
    }


@pytest.mark.db
def test_resolver_translates_spanish_names_to_catalog_ids(clean_db: Session) -> None:
    clean_db.add_all(
        [
            Catalog(kind="nation", ea_id=18, name="France"),
            Catalog(kind="nation", ea_id=95, name="United States"),
            Catalog(kind="league", ea_id=13, name="Premier League"),
            Catalog(kind="league", ea_id=53, name="LALIGA EA SPORTS"),
            Catalog(kind="club", ea_id=243, name="Real Madrid"),
            Catalog(kind="club", ea_id=21, name="FC Bayern München"),
        ]
    )
    clean_db.commit()
    r = Resolver(clean_db)
    assert r.resolve(GroupMin("nation", "Francia", 1)) == Resolved("nation", 18, "France", 1)
    assert r.resolve(GroupMin("nation", "EE. UU.", 2)).id == 95
    assert r.resolve(GroupMin("league", "Premier League", 3)).id == 13
    assert r.resolve(GroupMin("league", "LALIGA", 1)).id == 53
    assert r.resolve(GroupMin("club", "Real Madrid (LALIGA)", 1)).id == 243
    assert r.resolve(GroupMin("club", "FC Bayern de Múnich (Bundesliga)", 1)).id == 21
    assert r.resolve(GroupMin("club", "PSG (Ligue 1)", 1)).id == 73
    assert r.resolve(GroupMin("nation", "Narnia", 1)) is None


@pytest.mark.db
def test_plan_endpoints_group_objectives_and_explain_the_skipped(
    client: TestClient, clean_db: Session
) -> None:
    clean_db.add(Catalog(kind="nation", ea_id=18, name="France"))
    clean_db.add_all(
        [
            _group(
                1,
                "Maestría en Rivals",
                [
                    _o(10, "Gana 12 partidos de Rivals.", 6, 12),
                    _o(11, "Juega 5 partidos de Rivals.", 0, 5),
                    _o(12, "Gana 3 partidos de Rivals.", 3, 3, "REDEEMED"),
                ],
            ),
            _group(
                2,
                "Mercado",
                [_o(20, "Pon a 500 futbolistas en el Mercado de transferibles.", 0, 500)],
            ),
            _group(
                3,
                "Narnia",
                [
                    _o(
                        30,
                        "Gana 2 partidos de Draft con mín. 1 futbolista de Narnia en tu once inicial.",
                        0,
                        2,
                    )
                ],
            ),
        ]
    )
    clean_db.commit()

    c = client.get("/objectives/plan/candidates").json()
    assert {p["objective_id"] for p in c["plannable"]} == {10, 11, 30}  # el 12 ya está reclamado
    assert [s["objective_id"] for s in c["skipped"]] == [20]
    assert "Mercado" in c["skipped"][0]["reason"]
    unresolved = next(p for p in c["plannable"] if p["objective_id"] == 30)
    assert unresolved["unresolved"] == ["Narnia"]

    plan = client.get("/objectives/plan").json()
    rivals = next(s for s in plan["sessions"] if s["scope"] == "rivals")
    # quedan 6 victorias (10 partidos al 60 %) y 5 partidos: una sola sesión de 10
    assert rivals["matches"] == 10 and len(rivals["tasks"]) == 2
    assert plan["totals"]["matches_separate"] > plan["totals"]["matches"] - 1
    assert plan["totals"]["saved"] == plan["totals"]["matches_separate"] - plan["totals"]["matches"]
    assert plan["assumptions"]["win_rate"] == 0.6

    only = client.get("/objectives/plan", params={"ids": "11"}).json()
    assert [t["objective_id"] for s in only["sessions"] for t in s["tasks"]] == [11]
    assert only["totals"]["matches"] == 5


@pytest.mark.db
def test_plan_squad_endpoint_accepts_group_minimums(client: TestClient) -> None:
    r = client.get("/objectives/plan/squad", params={"mins": "league:13:3,bad,nation:x:1"})
    assert r.status_code == 200
    assert r.json()["status"] in ("infeasible", "unknown", "optimal", "feasible")
