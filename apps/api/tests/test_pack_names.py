from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from fcsl_api.main import app
from fcsl_api.models_db import Catalog
from fcsl_api.objectives.awards import describe_award
from fcsl_api.routes import imports

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


def _pack(value: int, count: int = 1) -> dict:
    return {"type": "pack", "value": value, "count": count, "untradeable": True, "item": None}


def test_describe_award_uses_the_pack_name_when_known() -> None:
    names = {304: "Sobre de oro raro"}
    assert describe_award(_pack(304), {}, names)["label"] == "Sobre de oro raro"
    assert describe_award(_pack(304, 2), {}, names)["label"] == "2× Sobre de oro raro"
    assert describe_award(_pack(999), {}, names)["label"] == "Sobre #999"  # desconocido: el id
    assert describe_award(_pack(304), {})["label"] == "Sobre #304"  # sin tabla de nombres


@pytest.mark.db
def test_import_packs_requires_token(client: TestClient) -> None:
    assert client.post("/import/packs", json={"names": {"304": "x"}}).status_code == 401


@pytest.mark.db
def test_import_packs_stores_and_updates_names(client: TestClient, clean_db: Session) -> None:
    r = client.post(
        "/import/packs",
        json={"names": {"304": "Sobre de oro raro", "1050": "Sobre 85+"}},
        headers=H,
    )
    assert r.status_code == 200 and r.json() == {"packs": 2}
    client.post("/import/packs", json={"names": {"304": "Sobre de oro raro mejorado"}}, headers=H)
    got = {c.ea_id: c.name for c in clean_db.scalars(select(Catalog).where(Catalog.kind == "pack"))}
    assert got == {304: "Sobre de oro raro mejorado", 1050: "Sobre 85+"}


@pytest.mark.db
def test_import_packs_ignores_non_numeric_ids_and_blank_names(
    client: TestClient, clean_db: Session
) -> None:
    r = client.post(
        "/import/packs", json={"names": {"abc": "x", "7": "  ", "8": "Válido"}}, headers=H
    )
    assert r.json() == {"packs": 1}
    assert [c.ea_id for c in clean_db.scalars(select(Catalog).where(Catalog.kind == "pack"))] == [8]


@pytest.mark.db
def test_objectives_show_pack_names_from_the_catalog(client: TestClient) -> None:
    group = {
        "id": 1,
        "type": 6,
        "title": "G",
        "state": 1,
        "end_time": 4102444800,
        "awards": [_pack(304)],
        "objectives": [
            {
                "id": 1,
                "name": "t",
                "progress": 1,
                "target": 1,
                "state": "REDEEMED",
                "awards": [_pack(1050, 2)],
            }
        ],
    }
    client.post(
        "/import/objectives",
        json={"categories": [{"id": 0, "name": "A", "groups": [group]}]},
        headers=H,
    )
    before = client.get("/objectives").json()["items"][0]
    assert before["awards"][0]["label"] == "Sobre #304"  # aún sin nombres
    client.post(
        "/import/packs",
        json={"names": {"304": "Sobre de oro raro", "1050": "Sobre 85+"}},
        headers=H,
    )
    after = client.get("/objectives").json()["items"][0]
    assert after["awards"][0]["label"] == "Sobre de oro raro"
    assert after["objectives"][0]["awards"][0]["label"] == "2× Sobre 85+"
