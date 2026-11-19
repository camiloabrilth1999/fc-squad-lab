from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from fcsl_api.main import app
from fcsl_api.models_db import Card, CardMeta, Price
from fcsl_api.routes import imports

pytestmark = pytest.mark.db


@pytest.fixture
def client(clean_db: Session) -> Iterator[TestClient]:
    def _session() -> Iterator[Session]:
        yield clean_db

    app.dependency_overrides[imports.get_db] = _session
    yield TestClient(app)
    app.dependency_overrides.clear()


def _seed(db: Session) -> None:
    cards = [
        (
            1,
            "Alfa Delantero",
            90,
            ["ST", "CF"],
            1,
            10,
            100,
            91.0,
            "adv_forward",
            "stats",
            "S",
            50000,
        ),
        (2, "Beta Extremo", 85, ["LW"], 2, 11, 101, 88.5, "winger", "face", "A+", 9000),
        (3, "Gamma Central", 82, ["CB"], 1, 10, 102, 80.2, "defender", "face", "A", None),
        (4, "Delta Portero", 80, ["GK"], 3, 12, 103, 79.0, "goalkeeper", "face", "B+", 1000),
    ]
    for rid, name, rating, pos, league, nation, club, meta, role, src, tier, price in cards:
        db.add(
            Card(
                resource_id=rid,
                asset_id=rid,
                name=name,
                rating=rating,
                positions=pos,
                league_id=league,
                nation_id=nation,
                club_id=club,
                rarity_name="Rare",
            )
        )
        db.add(CardMeta(resource_id=rid, role=role, meta=meta, source=src, tier=tier))
        if price:
            db.add(Price(resource_id=rid, platform="PC", source="easysbc:market", price=price))
    db.commit()


def _names(client: TestClient, **params) -> list[str]:
    return [r["name"] for r in client.get("/players", params=params).json()["items"]]


def test_default_sort_is_meta_desc(client: TestClient, clean_db: Session) -> None:
    _seed(clean_db)
    body = client.get("/players").json()
    assert [r["resource_id"] for r in body["items"]] == [1, 2, 3, 4]
    assert body["total"] == 4
    top = body["items"][0]
    assert top["meta"] == 91.0 and top["tier"] == "S" and top["price"] == 50000


def test_filters_one_by_one(client: TestClient, clean_db: Session) -> None:
    _seed(clean_db)
    assert _names(client, q="extremo") == ["Beta Extremo"]
    assert _names(client, position="CF") == ["Alfa Delantero"]
    assert _names(client, role="defender") == ["Gamma Central"]
    assert _names(client, league_id=1) == ["Alfa Delantero", "Gamma Central"]
    assert _names(client, nation_id=11) == ["Beta Extremo"]
    assert _names(client, club_id=103) == ["Delta Portero"]
    assert _names(client, min_rating=85) == ["Alfa Delantero", "Beta Extremo"]
    assert _names(client, max_rating=82) == ["Gamma Central", "Delta Portero"]
    assert _names(client, tier="A+") == ["Beta Extremo"]
    assert _names(client, source="stats") == ["Alfa Delantero"]
    assert _names(client, min_meta=88) == ["Alfa Delantero", "Beta Extremo"]
    assert _names(client, max_price=9000) == ["Beta Extremo", "Delta Portero"]
    assert _names(client, min_price=10000) == ["Alfa Delantero"]


def test_sort_by_price_puts_unpriced_last(client: TestClient, clean_db: Session) -> None:
    _seed(clean_db)
    assert _names(client, sort="price", order="asc") == [
        "Delta Portero",
        "Beta Extremo",
        "Alfa Delantero",
        "Gamma Central",  # sin precio: al final
    ]
    assert _names(client, sort="name", order="asc")[0] == "Alfa Delantero"


def test_pagination(client: TestClient, clean_db: Session) -> None:
    _seed(clean_db)
    body = client.get("/players", params={"page": 2, "page_size": 3}).json()
    assert body["total"] == 4 and [r["resource_id"] for r in body["items"]] == [4]


def test_bad_sort_and_role_are_422(client: TestClient) -> None:
    assert client.get("/players", params={"sort": "nope"}).status_code == 422
    assert client.get("/players", params={"role": "nope"}).status_code == 422


def test_player_detail_has_roles_and_404(client: TestClient, clean_db: Session) -> None:
    _seed(clean_db)
    d = client.get("/players/1").json()
    assert d["name"] == "Alfa Delantero" and d["price"] == 50000
    assert [r["role"] for r in d["roles"]] == ["adv_forward"]  # ST y CF comparten rol
    assert client.get("/players/999").status_code == 404


def test_player_detail_has_playstyle_names_and_catalog(
    client: TestClient, clean_db: Session
) -> None:
    from fcsl_api.ingest.store import upsert_catalog

    _seed(clean_db)
    upsert_catalog(
        clean_db, [("league", 1, "Liga X"), ("nation", 10, "País Y"), ("club", 100, "Club Z")]
    )
    card = clean_db.get(Card, 1)
    card.play_styles = [16]
    card.play_styles_plus = [22, 34]
    clean_db.commit()
    d = client.get("/players/1").json()
    assert d["play_style_names"] == ["Technical"]
    assert d["play_style_plus_names"] == ["Quick Step", "Low Driven Shot"]
    assert (d["league_name"], d["nation_name"], d["club_name"]) == ("Liga X", "País Y", "Club Z")
