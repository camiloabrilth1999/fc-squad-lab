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


def _add(
    db: Session, rid: int, rating: int, role: str, meta: float, price: int | None, pos: str = "ST"
) -> None:
    db.add(
        Card(
            resource_id=rid,
            asset_id=rid,
            name=f"J{rid}",
            rating=rating,
            positions=[pos],
            league_id=1,
            nation_id=1,
            club_id=1,
        )
    )
    db.add(CardMeta(resource_id=rid, role=role, meta=meta, source="face", tier="A"))
    if price:
        db.add(Price(resource_id=rid, platform="PC", source="easysbc:market", price=price))


def _seed_bargains(db: Session) -> None:
    # mismo rol: a mayor meta, mayor precio, salvo el 3 (mucho meta, barato) y el 5 (poco meta, caro)
    _add(db, 1, 80, "adv_forward", 80.0, 1000)
    _add(db, 2, 82, "adv_forward", 82.0, 2000)
    _add(db, 3, 84, "adv_forward", 90.0, 1500)  # chollo
    _add(db, 4, 86, "adv_forward", 86.0, 4000)
    _add(db, 5, 83, "adv_forward", 78.0, 9000)  # caro para lo que da
    db.commit()


def test_bargains_rank_cheap_high_meta_first(client: TestClient, clean_db: Session) -> None:
    _seed_bargains(clean_db)
    items = client.get("/value/bargains").json()["items"]
    ids = [r["resource_id"] for r in items]
    assert ids[0] == 3 and ids[-1] == 5
    top = items[0]
    assert top["meta"] == 90.0 and top["price"] == 1500 and top["score"] > items[-1]["score"]


def test_bargains_filters_apply_after_ranking(client: TestClient, clean_db: Session) -> None:
    _seed_bargains(clean_db)
    _add(clean_db, 6, 90, "defender", 85.0, 500, pos="CB")
    clean_db.commit()
    by_role = client.get("/value/bargains", params={"role": "defender"}).json()["items"]
    assert [r["resource_id"] for r in by_role] == [6]
    capped = client.get("/value/bargains", params={"max_price": 2000}).json()["items"]
    assert {r["resource_id"] for r in capped} == {1, 2, 3, 6}
    limited = client.get("/value/bargains", params={"limit": 2}).json()["items"]
    assert len(limited) == 2


def test_bargains_ignore_cards_without_price_or_low_rating(
    client: TestClient, clean_db: Session
) -> None:
    _seed_bargains(clean_db)
    _add(clean_db, 7, 90, "adv_forward", 99.0, None)  # sin precio
    _add(clean_db, 8, 60, "adv_forward", 99.0, 100)  # bajo el rating mínimo
    clean_db.commit()
    ids = {r["resource_id"] for r in client.get("/value/bargains").json()["items"]}
    assert 7 not in ids and 8 not in ids


def test_fodder_lists_cheapest_cards_per_rating(client: TestClient, clean_db: Session) -> None:
    for rid, rating, price in [
        (1, 84, 900),
        (2, 84, 500),
        (3, 84, 700),
        (4, 84, 1200),
        (5, 85, 3000),
        (6, 85, 2500),
        (7, 83, None),
    ]:
        _add(clean_db, rid, rating, "adv_forward", 80.0, price)
    clean_db.commit()
    rows = client.get(
        "/value/fodder", params={"per_rating": 2, "min_rating": 84, "max_rating": 85}
    ).json()
    assert [g["rating"] for g in rows] == [84, 85]
    by = {g["rating"]: g for g in rows}
    assert [c["price"] for c in by[84]["cards"]] == [500, 700]  # las 2 más baratas
    assert [c["price"] for c in by[85]["cards"]] == [2500, 3000]
    assert by[84]["cheapest"] == 500
