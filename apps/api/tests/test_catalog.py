from collections.abc import Iterator

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from fcsl_api.ingest.futgg import parse_futgg_player
from fcsl_api.ingest.store import upsert_catalog
from fcsl_api.ingest.sync import sync_cards
from fcsl_api.main import app
from fcsl_api.models_db import Card, CardMeta, Catalog
from fcsl_api.routes import imports
from tests.test_futgg import PAGE, player
from tests.test_sync import client_for


def test_parser_reads_league_nation_club_names():
    p = dict(PAGE["data"][0])
    p.update(
        league={"eaId": 53, "name": "LaLiga EA SPORTS"},
        nation={"eaId": 18, "name": "France"},
        club={"eaId": 243, "name": "Real Madrid"},
    )
    row = parse_futgg_player(p)
    assert (row.league_name, row.nation_name, row.club_name) == (
        "LaLiga EA SPORTS",
        "France",
        "Real Madrid",
    )


@pytest.mark.db
def test_sync_cards_fills_the_catalog(clean_db: Session) -> None:
    def handler(request):
        p = player(1)
        p.update(
            league={"eaId": 53, "name": "LaLiga EA SPORTS"},
            nation={"eaId": 18, "name": "France"},
            club={"eaId": 243, "name": "Real Madrid"},
        )
        return httpx.Response(200, json={"data": [p], "next": None, "currentPage": 1, "total": 1})

    run = sync_cards(clean_db, client_for(handler))
    assert run.status == "ok"
    got = {(c.kind, c.ea_id): c.name for c in clean_db.scalars(select(Catalog))}
    assert got == {
        ("league", 53): "LaLiga EA SPORTS",
        ("nation", 18): "France",
        ("club", 243): "Real Madrid",
    }
    assert clean_db.get(Card, 1) is not None  # y las cartas se guardan igual


@pytest.mark.db
def test_upsert_catalog_updates_names(clean_db: Session) -> None:
    upsert_catalog(clean_db, [("league", 1, "Vieja")])
    upsert_catalog(clean_db, [("league", 1, "Nueva"), ("nation", 2, "País")])
    names = {(c.kind, c.ea_id): c.name for c in clean_db.scalars(select(Catalog))}
    assert names == {("league", 1): "Nueva", ("nation", 2): "País"}


@pytest.fixture
def client(clean_db: Session) -> Iterator[TestClient]:
    def _session() -> Iterator[Session]:
        yield clean_db

    app.dependency_overrides[imports.get_db] = _session
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.mark.db
def test_catalog_endpoint_lists_and_searches(client: TestClient, clean_db: Session) -> None:
    upsert_catalog(
        clean_db,
        [
            ("league", 13, "Premier League"),
            ("league", 53, "LaLiga EA SPORTS"),
            ("nation", 18, "France"),
        ],
    )
    leagues = client.get("/catalog", params={"kind": "league"}).json()
    assert [x["name"] for x in leagues] == ["LaLiga EA SPORTS", "Premier League"]  # por nombre
    found = client.get("/catalog", params={"kind": "league", "q": "prem"}).json()
    assert found == [{"id": 13, "name": "Premier League", "image_path": None}]
    assert client.get("/catalog", params={"kind": "bad"}).status_code == 422


@pytest.mark.db
def test_players_rows_include_names(client: TestClient, clean_db: Session) -> None:
    upsert_catalog(
        clean_db, [("league", 1, "Liga X"), ("nation", 10, "País Y"), ("club", 100, "Club Z")]
    )
    clean_db.add(
        Card(
            resource_id=1,
            asset_id=1,
            name="Alfa",
            rating=90,
            positions=["ST"],
            league_id=1,
            nation_id=10,
            club_id=100,
        )
    )
    clean_db.add(CardMeta(resource_id=1, role="adv_forward", meta=90.0, source="face", tier="S"))
    clean_db.commit()
    row = client.get("/players").json()["items"][0]
    assert (row["league_name"], row["nation_name"], row["club_name"]) == (
        "Liga X",
        "País Y",
        "Club Z",
    )
