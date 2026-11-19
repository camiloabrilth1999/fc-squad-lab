from collections.abc import Iterator
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from fcsl_api.evolutions.enums import stat_name
from fcsl_api.main import app
from fcsl_api.routes import imports

pytestmark = pytest.mark.db

TOKEN = "secreto-de-prueba"
H = {"X-FCSL-Token": TOKEN}


@pytest.fixture
def client(clean_db: Session, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    monkeypatch.setenv("FCSL_IMPORT_TOKEN", TOKEN)

    def _session() -> Iterator[Session]:
        yield clean_db

    app.dependency_overrides[imports.get_db] = _session
    yield TestClient(app)
    app.dependency_overrides.clear()


def _slot(
    sid: int, name: str, *, category: int = 0, end_time: int = 0, status: str = "NOT_STARTED"
) -> dict:
    return {
        "id": sid,
        "content_id": sid + 1000,
        "name": name,
        "description": f"Descripción de {name}",
        "status": status,
        "timed": end_time > 0,
        "end_time": end_time,
        "category_id": category,
        "gk_only": False,
        "outfield_only": True,
        "multi_choice": False,
        "reset_count": 0,
        "total_rewards": 18,
        "currencies": [{"currency": "COINS", "amount": 10000}],
        "top_rewards": [
            {"stat": 11, "count": 3, "max_value": 83},
            {"stat": 22, "count": 10, "max_value": 86},
        ],
        "requirements": [{"type": "PLAYER_ATTRIBUTE", "key": 1, "slot": 1, "value": 80}],
        "levels": [
            {"level": 0, "state": "NOT_STARTED", "objectives": [], "awards": []},
            {
                "level": 1,
                "state": "NOT_STARTED",
                "objectives": [{"id": 7, "name": "Juega 3 partidos", "description": "*"}],
                "awards": [{"stat": 22, "count": 10, "max_value": 86}],
            },
        ],
        "bonuses": {
            "1": [
                {"stat": 11, "total": 83, "initial": 80},
                {"stat": 22, "total": 86, "initial": None},
            ]
        },
    }


def _body(*slots: dict) -> dict:
    return {
        "categories": [
            {
                "id": 0,
                "name": "Evoluciones",
                "slot_ids": [s["id"] for s in slots if s["category_id"] == 0],
            },
            {
                "id": 30,
                "name": "Campus",
                "slot_ids": [s["id"] for s in slots if s["category_id"] == 30],
            },
        ],
        "slots": list(slots),
    }


def test_import_requires_token(client: TestClient) -> None:
    assert client.post("/import/evolutions", json=_body(_slot(1, "A"))).status_code == 401
    assert (
        client.post(
            "/import/evolutions", json=_body(_slot(1, "A")), headers={"X-FCSL-Token": "no"}
        ).status_code
        == 401
    )


def test_import_then_list_with_stat_names(client: TestClient) -> None:
    r = client.post("/import/evolutions", json=_body(_slot(1, "Bajo los focos")), headers=H)
    assert r.status_code == 200 and r.json() == {"slots": 1, "categories": 2}
    items = client.get("/evolutions").json()["items"]
    assert len(items) == 1
    e = items[0]
    assert e["id"] == 1 and e["name"] == "Bajo los focos" and e["category"] == "Evoluciones"
    assert e["cost"] == [{"currency": "COINS", "amount": 10000}]
    assert [r["name"] for r in e["top_rewards"]] == ["Valoración general", "Velocidad"]
    assert e["top_rewards"][0] == {
        "stat": 11,
        "name": "Valoración general",
        "count": 3,
        "max_value": 83,
    }
    assert e["levels"][1]["objectives"] == [
        {"id": 7, "name": "Juega 3 partidos", "description": "*"}
    ]
    assert e["upgrades"][0]["name"] == "Valoración general" and e["upgrades"][0]["total"] == 83


def test_reimport_updates_instead_of_duplicating(client: TestClient) -> None:
    client.post("/import/evolutions", json=_body(_slot(1, "Vieja")), headers=H)
    client.post("/import/evolutions", json=_body(_slot(1, "Nueva", status="STARTED")), headers=H)
    items = client.get("/evolutions").json()["items"]
    assert [(e["name"], e["status"]) for e in items] == [("Nueva", "STARTED")]


def test_partial_imports_keep_other_slots(client: TestClient) -> None:
    client.post("/import/evolutions", json=_body(_slot(1, "A", category=0)), headers=H)
    client.post("/import/evolutions", json=_body(_slot(2, "B", category=30)), headers=H)
    assert {e["name"] for e in client.get("/evolutions").json()["items"]} == {"A", "B"}


def test_filters_by_category_search_and_expiry(client: TestClient) -> None:
    future = int((datetime.now(UTC) + timedelta(days=3)).timestamp())
    past = int((datetime.now(UTC) - timedelta(days=3)).timestamp())
    client.post(
        "/import/evolutions",
        json=_body(
            _slot(1, "Bajo los focos", category=0, end_time=future),
            _slot(2, "Campus uno", category=30),
            _slot(3, "Ya caducada", category=0, end_time=past),
        ),
        headers=H,
    )

    def names(**p) -> set[str]:
        return {e["name"] for e in client.get("/evolutions", params=p).json()["items"]}

    assert names() == {"Bajo los focos", "Campus uno"}  # por defecto, sin las caducadas
    assert names(include_expired=True) == {"Bajo los focos", "Campus uno", "Ya caducada"}
    assert names(category_id=30) == {"Campus uno"}
    assert names(q="focos") == {"Bajo los focos"}
    timed = client.get("/evolutions", params={"q": "focos"}).json()["items"][0]
    assert timed["ends_at"] is not None and timed["timed"] is True


def test_categories_endpoint(client: TestClient) -> None:
    client.post(
        "/import/evolutions",
        json=_body(_slot(1, "A", category=0), _slot(2, "B", category=30)),
        headers=H,
    )
    cats = client.get("/evolutions/categories").json()
    assert {c["name"]: c["imported"] for c in cats} == {"Evoluciones": 1, "Campus": 1}


def test_stat_names_cover_known_ids_and_fallback() -> None:
    assert stat_name(11) == "Valoración general"
    assert stat_name(41) == "Pase corto"
    assert stat_name(301) == "Finesse Shot"
    assert stat_name(155).startswith("Rol")  # roles+/++
    assert stat_name(99999) == "Stat 99999"
