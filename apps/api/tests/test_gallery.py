from collections.abc import Iterator
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from fcsl_api.gallery.service import PoolCard, solve_set
from fcsl_api.gallery.sets import load_sets
from fcsl_api.main import app
from fcsl_api.models_db import Card, ClubItem, Price
from fcsl_api.routes import imports


def _c(rid: int, points: int, price: int | None, collected: bool = False) -> PoolCard:
    return PoolCard(
        resource_id=rid,
        name=f"C{rid}",
        rating=70,
        positions=["CM"],
        rarity_name="Rare",
        image_path=None,
        points=points,
        exact=True,
        price=price,
        collected=collected,
    )


def test_seeded_sets_cover_the_gallery() -> None:
    sets = load_sets()
    assert len(sets) == 198
    assert {s.group for s in sets} >= {"rarities", "leagues", "premier-league", "laliga"}
    lecce = next(s for s in sets if s.name == "Lecce")
    assert (lecce.badge_type, lecce.badge_id, lecce.required) == ("club", 347, 15)
    assert [g.name for g in lecce.grades] == ["D", "C", "B", "A", "S"]
    assert all(s.badge_type for s in sets)  # los sets sin badge tienen pool definido a mano


def test_solver_fills_every_slot_with_the_cheapest_cards_that_reach_the_grade() -> None:
    pool = [_c(1, 100, 1000), _c(2, 100, 200), _c(3, 50, 100), _c(4, 50, 100), _c(5, 10, 10)]
    sel = solve_set(pool, required=3, threshold=200)
    assert sel.status == "optimal"
    assert {c.resource_id for c in sel.cards} == {1, 2, 5} or sel.points >= 200
    assert len(sel.cards) == 3
    assert sel.points >= 200
    # 100 + 50 + 50 = 200 por 200 + 100 + 100 = 400 es más barato que usar la carta de 1000
    assert sel.cost == 400
    assert sel.tax == 20 and sel.coins_needed == 200 and sel.buys == 3


def test_solver_without_complete_may_use_fewer_cards() -> None:
    pool = [_c(1, 300, 900), _c(2, 20, 10), _c(3, 20, 10)]
    sel = solve_set(pool, required=3, threshold=300, complete=False)
    assert [c.resource_id for c in sel.cards] == [1]
    assert sel.cost == 900


def test_collected_cards_are_free_and_count() -> None:
    pool = [_c(1, 100, None, collected=True), _c(2, 100, 500), _c(3, 100, 300)]
    sel = solve_set(pool, required=2, threshold=200)
    assert {c.resource_id for c in sel.cards} == {1, 3}
    assert sel.cost == 300 and sel.buys == 1


def test_reached_when_the_collected_cards_already_make_the_grade() -> None:
    pool = [_c(1, 100, None, collected=True), _c(2, 100, None, collected=True)]
    sel = solve_set(pool, required=2, threshold=150)
    assert sel.status == "reached" and sel.cost == 0


def test_infeasible_when_not_enough_points_exist() -> None:
    sel = solve_set([_c(1, 10, 5), _c(2, 10, 5)], required=2, threshold=1000)
    assert sel.status == "infeasible"


def test_unpriced_cards_cannot_be_bought() -> None:
    sel = solve_set([_c(1, 100, None), _c(2, 100, 50)], required=1, threshold=100)
    assert [c.resource_id for c in sel.cards] == [2]


@pytest.fixture
def client(clean_db: Session) -> Iterator[TestClient]:
    def _session() -> Iterator[Session]:
        yield clean_db

    app.dependency_overrides[imports.get_db] = _session
    yield TestClient(app)
    app.dependency_overrides.clear()


def _card(rid: int, rating: int, club_id: int = 347) -> Card:
    return Card(
        resource_id=rid,
        asset_id=rid,
        name=f"Jugador {rid}",
        rating=rating,
        positions=["CM"],
        club_id=club_id,
        rare=False,
        rarity_ea_id=0,
        rarity_name="Common",
    )


@pytest.mark.db
def test_endpoints_list_sets_and_solve_with_the_club_progress(
    client: TestClient, clean_db: Session
) -> None:
    now = datetime.now(UTC)
    cards = [_card(1, 84), _card(2, 75), *[_card(10 + i, 70) for i in range(14)]]
    clean_db.add_all(cards)
    clean_db.flush()
    clean_db.add_all(
        Price(
            resource_id=c.resource_id,
            platform="PC",
            source="easysbc:market",
            price=700,
            captured_at=now,
        )
        for c in cards
    )
    clean_db.add(ClubItem(item_id=1, resource_id=1, location="club", is_collected=True))
    clean_db.commit()

    lecce = next(s for s in client.get("/gallery").json()["items"] if s["name"] == "Lecce")
    assert (lecce["collected"], lecce["points"], lecce["grade"]) == (1, 830, "B")  # umbral B: 800
    assert lecce["required"] == 15

    r = client.get(f"/gallery/{lecce['id']}/solve", params={"grade": "A"}).json()
    assert r["status"] in ("optimal", "feasible", "reached")
    assert r["points"] >= 1200 and len(r["cards"]) == 15
    assert any(c["collected"] and c["resource_id"] == 1 for c in r["cards"])
    assert r["coins_needed"] == 700 and r["buys"] == 14
    assert r["estimated"] is False


@pytest.mark.db
def test_import_stores_the_collected_flag(
    client: TestClient, clean_db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("FCSL_IMPORT_TOKEN", "t")
    items = [
        {
            "id": 1,
            "resourceId": 5,
            "assetId": 5,
            "rating": 80,
            "itemType": "player",
            "isCollected": True,
        },
        {
            "id": 2,
            "resourceId": 6,
            "assetId": 6,
            "rating": 80,
            "itemType": "player",
            "isCollected": False,
        },
        {"id": 3, "resourceId": 7, "assetId": 7, "rating": 80, "itemType": "player"},
    ]
    r = client.post(
        "/import/club",
        json={"location": "club", "items": items, "duplicate_item_ids": []},
        headers={"X-FCSL-Token": "t"},
    )
    assert r.status_code == 200
    got = {c.item_id: c.is_collected for c in clean_db.query(ClubItem)}
    assert got == {1: True, 2: False, 3: None}


@pytest.mark.db
def test_solve_404s(client: TestClient) -> None:
    assert client.get("/gallery/999999/solve").status_code == 404
    assert client.get("/gallery/124/solve", params={"grade": "Z"}).status_code == 422


@pytest.mark.db
def test_manual_marks_add_remove_and_reset_collected_cards(
    client: TestClient, clean_db: Session
) -> None:
    clean_db.add_all([_card(1, 84), _card(2, 75), _card(3, 70)])
    clean_db.add(ClubItem(item_id=1, resource_id=1, location="club", is_collected=True))
    clean_db.commit()

    def lecce() -> dict:
        return next(s for s in client.get("/gallery").json()["items"] if s["name"] == "Lecce")

    assert (lecce()["collected"], lecce()["points"]) == (1, 830)  # solo la del club
    r = client.post("/gallery/collected", json={"resource_ids": [2, 3], "collected": True})
    assert r.json() == {"updated": 2}
    assert (lecce()["collected"], lecce()["points"]) == (3, 830 + 90 + 35)
    # desmarcar a mano una que el club dice coleccionada
    client.post("/gallery/collected", json={"resource_ids": [1], "collected": False})
    assert (lecce()["collected"], lecce()["points"]) == (2, 90 + 35)
    # quitar la marca manual: vuelve a mandar el club
    client.post("/gallery/collected", json={"resource_ids": [1, 2, 3], "collected": None})
    assert (lecce()["collected"], lecce()["points"]) == (1, 830)


@pytest.mark.db
def test_marking_requires_at_least_one_card(client: TestClient) -> None:
    assert client.post("/gallery/collected", json={"resource_ids": []}).status_code == 422


@pytest.mark.db
def test_set_cards_lists_the_pool_with_search_and_collected_flag(
    client: TestClient, clean_db: Session
) -> None:
    clean_db.add_all([_card(1, 84), _card(2, 75), _card(3, 70), _card(4, 70, club_id=999)])
    clean_db.flush()
    clean_db.get(Card, 3).name = "Pierotti"
    clean_db.add(ClubItem(item_id=1, resource_id=2, location="club", is_collected=True))
    clean_db.commit()
    lecce_id = next(s for s in client.get("/gallery").json()["items"] if s["name"] == "Lecce")["id"]

    r = client.get(f"/gallery/{lecce_id}/cards").json()
    assert [c["resource_id"] for c in r["cards"]] == [1, 2, 3]  # por puntos; la 4 es de otro club
    assert {c["resource_id"]: c["collected"] for c in r["cards"]} == {1: False, 2: True, 3: False}
    found = client.get(f"/gallery/{lecce_id}/cards", params={"q": "pier"}).json()
    assert [c["resource_id"] for c in found["cards"]] == [3]
    assert client.get("/gallery/999999/cards").status_code == 404
