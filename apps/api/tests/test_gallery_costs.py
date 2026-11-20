from collections.abc import Iterator
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from fcsl_api.gallery.plan import _cache
from fcsl_api.main import app
from fcsl_api.models_db import Card, ClubItem, Price
from fcsl_api.routes import imports


@pytest.fixture
def client(clean_db: Session) -> Iterator[TestClient]:
    def _session() -> Iterator[Session]:
        yield clean_db

    _cache.clear()
    app.dependency_overrides[imports.get_db] = _session
    yield TestClient(app)
    app.dependency_overrides.clear()
    _cache.clear()


def _card(rid: int, rating: int, club_id: int = 347) -> Card:
    return Card(
        resource_id=rid,
        asset_id=rid,
        name=f"J{rid}",
        rating=rating,
        positions=["CM"],
        club_id=club_id,
        rare=False,
        rarity_ea_id=0,
        rarity_name="Common",
    )


def _seed(session: Session) -> None:
    now = datetime.now(UTC)
    cards = [_card(1, 84), _card(2, 75), *[_card(10 + i, 70) for i in range(14)]]
    session.add_all(cards)
    session.flush()
    session.add_all(
        Price(
            resource_id=c.resource_id,
            platform="PC",
            source="easysbc:market",
            price=700,
            captured_at=now,
        )
        for c in cards
    )
    session.commit()


@pytest.mark.db
def test_sets_without_costs_stay_fast_and_have_no_options(
    client: TestClient, clean_db: Session
) -> None:
    _seed(clean_db)
    lecce = next(s for s in client.get("/gallery").json()["items"] if s["name"] == "Lecce")
    assert lecce["options"] is None and lecce["verdict"] is None
    assert lecce["tokens_left"] == 28  # nada alcanzado: todas las fichas del set


@pytest.mark.db
def test_costs_list_the_options_per_grade_and_the_best_one(
    client: TestClient, clean_db: Session
) -> None:
    _seed(clean_db)
    items = client.get("/gallery", params={"costs": "true"}).json()["items"]
    lecce = next(s for s in items if s["name"] == "Lecce")
    grades = [o["grade"] for o in lecce["options"]]
    assert grades[0] == "B" and set(grades) <= {"B", "A", "S"}  # C y D no dan fichas nuevas
    b = lecce["options"][0]
    assert b["tokens"] == 5 and b["buys"] == 15 and b["coins_needed"] == 700
    assert b["tax"] == round(15 * 700 * 0.05)
    assert lecce["best_grade"] in grades
    # un set sin cartas en la base no tiene opciones
    empty = next(s for s in items if s["name"] == "Monaco" or s["name"] == "AS Monaco")
    assert empty["options"] == []


@pytest.mark.db
def test_tokens_left_drops_as_grades_are_reached(client: TestClient, clean_db: Session) -> None:
    _seed(clean_db)
    clean_db.add(ClubItem(item_id=1, resource_id=1, location="club", is_collected=True))  # 830 pts
    clean_db.commit()
    lecce = next(s for s in client.get("/gallery").json()["items"] if s["name"] == "Lecce")
    assert lecce["grade"] == "B"  # 830 ≥ 800
    assert lecce["tokens_left"] == 8 + 15  # A y S
