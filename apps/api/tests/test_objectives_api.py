from collections.abc import Iterator
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from fcsl_api.main import app
from fcsl_api.models_db import Card
from fcsl_api.objectives.awards import describe_award
from fcsl_api.routes import imports

TOKEN = "secreto-de-prueba"
H = {"X-FCSL-Token": TOKEN}
NOW = int(datetime.now(UTC).timestamp())
FUTURE = NOW + 5 * 86400
PAST = NOW - 5 * 86400


@pytest.fixture
def client(clean_db: Session, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    monkeypatch.setenv("FCSL_IMPORT_TOKEN", TOKEN)

    def _session() -> Iterator[Session]:
        yield clean_db

    app.dependency_overrides[imports.get_db] = _session
    yield TestClient(app)
    app.dependency_overrides.clear()


def _award(kind: str, value: int, count: int = 1, item: dict | None = None) -> dict:
    return {"type": kind, "value": value, "count": count, "untradeable": False, "item": item}


def _task(
    tid: int, name: str, progress: int | None, target: int, state: str | None = None, awards=None
) -> dict:
    return {
        "id": tid,
        "name": name,
        "description": f"d {name}",
        "progress": progress,
        "target": target,
        "state": state,
        "awards": awards or [],
    }


def _group(
    gid: int,
    title: str,
    *,
    state: int = 1,
    end: int = FUTURE,
    tasks=None,
    awards=None,
    gtype: int = 6,
) -> dict:
    return {
        "id": gid,
        "type": gtype,
        "content_id": gid + 100,
        "title": title,
        "subtitle": f"sub {title}",
        "state": state,
        "repeatability": "NON_REPEATABLE",
        "times_completed": 1 if state == 4 else 0,
        "start_time": NOW - 86400,
        "end_time": end,
        "visibility_time": NOW - 86400,
        "priority": gid,
        "awards": awards or [],
        "objectives": tasks or [],
    }


def _body(*cats: tuple[int, str, list[dict]]) -> dict:
    return {
        "categories": [
            {"id": cid, "name": name, "type": 4, "priority": cid, "groups": groups}
            for cid, name, groups in cats
        ]
    }


@pytest.mark.db
def test_import_requires_token(client: TestClient) -> None:
    assert client.post("/import/objectives", json=_body((0, "A", []))).status_code == 401


@pytest.mark.db
def test_import_then_list_with_progress_and_awards(client: TestClient, clean_db: Session) -> None:
    clean_db.add(
        Card(resource_id=50574680, asset_id=1, name="Gran Delantero", rating=82, positions=["ST"])
    )
    clean_db.commit()
    group = _group(
        30,
        "Fútbol total",
        tasks=[
            _task(1, "Juega 3", 3, 3, "REDEEMED", [_award("pack", 1050)]),
            _task(2, "Marca 10", 4, 10, "IN_PROGRESS"),
            _task(3, "Gana 2", None, 2),
        ],
        awards=[
            _award("coin", 5000),
            _award("xp", 200),
            _award("item", 50574680, item={"resource_id": 50574680, "rating": 82}),
        ],
    )
    r = client.post("/import/objectives", json=_body((0, "Fundamentos", [group])), headers=H)
    assert r.status_code == 200 and r.json() == {"categories": 1, "groups": 1}
    g = client.get("/objectives").json()["items"][0]
    assert g["title"] == "Fútbol total" and g["category"] == "Fundamentos"
    assert g["status"] == "in_progress" and g["progress"] == {"done": 1, "total": 3}
    assert [a["label"] for a in g["awards"]] == ["5.000 monedas", "+200 XP", "Gran Delantero (82)"]
    assert g["objectives"][0]["awards"][0]["label"] == "Sobre #1050"
    assert g["objectives"][1]["progress"] == 4 and g["objectives"][1]["target"] == 10
    assert g["objectives"][2]["progress"] is None


@pytest.mark.db
def test_reimport_replaces_groups_of_the_category(client: TestClient) -> None:
    client.post(
        "/import/objectives",
        json=_body((0, "A", [_group(1, "Vieja"), _group(2, "Se queda")])),
        headers=H,
    )
    client.post("/import/objectives", json=_body((0, "A", [_group(2, "Se queda")])), headers=H)
    assert [g["title"] for g in client.get("/objectives").json()["items"]] == ["Se queda"]


@pytest.mark.db
def test_reimport_of_one_category_keeps_the_others(client: TestClient) -> None:
    client.post(
        "/import/objectives",
        json=_body((0, "A", [_group(1, "Uno")]), (1, "B", [_group(2, "Dos")])),
        headers=H,
    )
    client.post("/import/objectives", json=_body((0, "A", [_group(1, "Uno nuevo")])), headers=H)
    assert {g["title"] for g in client.get("/objectives").json()["items"]} == {"Uno nuevo", "Dos"}


@pytest.mark.db
def test_filters_status_category_search_and_expiry(client: TestClient) -> None:
    groups = [
        _group(1, "Semanal", state=1, tasks=[_task(1, "x", 1, 3, "IN_PROGRESS")]),
        _group(2, "Hecho", state=4, tasks=[_task(2, "y", 1, 1, "REDEEMED")]),
        _group(3, "Sin empezar", state=0),
        _group(4, "Caducado", state=1, end=PAST),
    ]
    client.post(
        "/import/objectives",
        json=_body((0, "A", groups), (1, "B", [_group(5, "Otra cat")])),
        headers=H,
    )

    def titles(**p) -> set[str]:
        return {g["title"] for g in client.get("/objectives", params=p).json()["items"]}

    assert titles() == {"Semanal", "Hecho", "Sin empezar", "Otra cat"}  # sin caducados
    assert titles(include_expired=True) >= {"Caducado"}
    assert titles(status="done") == {"Hecho"}
    assert titles(status="open") == {"Semanal", "Sin empezar", "Otra cat"}
    assert titles(category_id=1) == {"Otra cat"}
    assert titles(q="seman") == {"Semanal"}


@pytest.mark.db
def test_categories_endpoint_counts_groups_and_done(client: TestClient) -> None:
    client.post(
        "/import/objectives",
        json=_body((0, "A", [_group(1, "x", state=4), _group(2, "y", state=1)]), (1, "B", [])),
        headers=H,
    )
    cats = {c["name"]: c for c in client.get("/objectives/categories").json()}
    assert cats["A"]["groups"] == 2 and cats["A"]["done"] == 1
    assert cats["B"]["groups"] == 0


def test_describe_award_labels() -> None:
    assert describe_award(_award("coin", 5000), {})["label"] == "5.000 monedas"
    assert describe_award(_award("xp", 200), {})["label"] == "+200 XP"
    assert describe_award(_award("pack", 304, 2), {})["label"] == "2× Sobre #304"
    assert (
        describe_award(_award("item", 9, item={"resource_id": 9, "rating": 80}), {9: "Nombre"})[
            "label"
        ]
        == "Nombre (80)"
    )
    assert (
        describe_award(_award("item", 9, item={"resource_id": 9, "rating": 80}), {})["label"]
        == "Jugador #9 (80)"
    )
    assert describe_award(_award("event_token_1", 3), {})["label"] == "Ficha de evento ×3"
    assert describe_award(_award("raro", 1), {})["label"] == "raro ×1"
