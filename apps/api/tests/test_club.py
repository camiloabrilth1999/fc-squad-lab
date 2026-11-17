from collections.abc import Iterator
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from fcsl_api.main import app
from fcsl_api.models_db import Card, ClubItem, Price, SyncRun
from fcsl_api.routes import club, imports

pytestmark = pytest.mark.db

NOW = datetime.now(UTC)


@pytest.fixture
def session(clean_db: Session) -> Iterator[Session]:
    def _session() -> Iterator[Session]:
        yield clean_db

    app.dependency_overrides[imports.get_db] = _session
    assert club.get_db is imports.get_db
    yield clean_db
    app.dependency_overrides.clear()


@pytest.fixture
def client(session: Session) -> TestClient:
    return TestClient(app)


def _card(rid: int, name: str, rating: int, positions: list[str], league: int = 1) -> Card:
    return Card(
        resource_id=rid,
        asset_id=rid,
        name=name,
        rating=rating,
        positions=positions,
        league_id=league,
        nation_id=10,
        club_id=100,
        rarity_name="Rare",
    )


def _item(item_id: int, rid: int, rating: int, **kw: object) -> ClubItem:
    base: dict = {
        "item_id": item_id,
        "resource_id": rid,
        "rating": rating,
        "untradeable": False,
        "location": "club",
        "duplicate": False,
        "loan": False,
        "imported_at": NOW,
        "seen_at": NOW,
    }
    base.update(kw)
    return ClubItem(**base)


def _seed(session: Session) -> None:
    session.add_all(
        [
            _card(1, "Alfa", 90, ["ST", "CF"], league=1),
            _card(2, "Beta", 85, ["CB"], league=2),
            _card(3, "Gamma", 85, ["CM"], league=1),
            _card(4, "Delta", 80, ["GK"], league=3),
        ]
    )
    session.add_all(
        [
            Price(resource_id=1, platform="PC", source="ea-session", price=10000, captured_at=NOW),
            Price(resource_id=2, platform="PC", source="easysbc:market", price=2000),
            Price(resource_id=3, platform="PC", source="easysbc:sbc", price=1000),
        ]
    )
    session.add_all(
        [
            _item(11, 1, 90),
            _item(12, 2, 85, duplicate=True),
            _item(13, 3, 85, untradeable=True, location="storage"),
            _item(14, 4, 80, last_sale_price=500, market_min=400),
            _item(15, 99, 70, market_min=300),  # carta desconocida
            _item(16, 1, 90, location="watchlist"),
        ]
    )
    session.commit()


def test_default_listing_excludes_watchlist_and_values(
    client: TestClient, session: Session
) -> None:
    _seed(session)
    body = client.get("/club").json()
    ids = [r["item_id"] for r in body["items"]]
    assert ids == [11, 12, 13, 14, 15]  # rating desc, luego nombre; desconocida al final
    by_id = {r["item_id"]: r for r in body["items"]}
    assert by_id[11]["value"] == round(10000 * 0.95)
    assert by_id[11]["price"] == 10000 and by_id[11]["price_source"] == "ea-session"
    assert by_id[12]["value"] == round(round(2000 * 0.95) * 0.9)  # duplicada
    assert by_id[12]["price_source"] == "easysbc:market"
    assert by_id[13]["value"] == 0 and by_id[13]["price"] == 1000
    assert by_id[14]["price"] == 500 and by_id[14]["price_source"] == "last-sale"
    assert by_id[14]["value"] == round(500 * 0.95)
    assert by_id[15]["name"] is None and by_id[15]["price_source"] == "ea-min"
    assert by_id[15]["value"] == round(300 * 0.95) and by_id[15]["rating"] == 70
    assert body["total"] == 5
    assert body["summary"] == {
        "count": 5,
        "value": 9500 + 1710 + 0 + 475 + 285,
        "untradeable": 1,
        "unknown_cards": 1,
    }


def test_watchlist_only_with_explicit_filter(client: TestClient, session: Session) -> None:
    _seed(session)
    body = client.get("/club", params={"location": "watchlist"}).json()
    assert [r["item_id"] for r in body["items"]] == [16]
    assert body["summary"]["count"] == 1


def test_filters_one_by_one(client: TestClient, session: Session) -> None:
    _seed(session)

    def ids(**params: object) -> list[int]:
        return [r["item_id"] for r in client.get("/club", params=params).json()["items"]]

    assert ids(min_rating=85) == [11, 12, 13]
    assert ids(max_rating=80) == [14, 15]
    assert ids(league_id=1) == [11, 13]
    assert ids(position="CF") == [11]
    assert ids(position="CB") == [12]
    assert ids(untradeable="true") == [13]
    assert ids(untradeable="false") == [11, 12, 14, 15]
    assert ids(location="storage") == [13]


def test_summary_covers_all_pages(client: TestClient, session: Session) -> None:
    _seed(session)
    body = client.get("/club", params={"page": 2, "page_size": 2}).json()
    assert [r["item_id"] for r in body["items"]] == [13, 14]
    assert body["total"] == 5 and body["summary"]["count"] == 5
    assert client.get("/club", params={"page_size": 501}).status_code == 422


def test_unknown_card_uses_item_rating_for_filters(client: TestClient, session: Session) -> None:
    _seed(session)
    ids = [r["item_id"] for r in client.get("/club", params={"max_rating": 70}).json()["items"]]
    assert ids == [15]


def test_out_of_range_rating_does_not_break(client: TestClient, session: Session) -> None:
    session.add(_card(7, "Bajo", 30, ["ST"]))
    session.add(_item(21, 7, 30, last_sale_price=200))
    session.commit()
    row = client.get("/club").json()["items"][0]
    assert row["value"] == 190


def test_data_status(client: TestClient, session: Session) -> None:
    _seed(session)
    fin = NOW - timedelta(hours=1)
    session.add_all(
        [
            SyncRun(kind="cards", started_at=fin, finished_at=fin, status="failed", error="x"),
            SyncRun(kind="cards", started_at=NOW, finished_at=NOW, status="ok", items=4),
            SyncRun(kind="prices", started_at=NOW, finished_at=NOW, status="partial", items=2),
        ]
    )
    session.commit()
    body = client.get("/data/status").json()
    assert body["cards"] == 4
    assert body["club_items"] == 6
    assert body["prices"] == {"ea-session": 1, "easysbc:market": 1, "easysbc:sbc": 1}
    assert body["last_sync"]["cards"]["status"] == "ok"
    assert body["last_sync"]["cards"]["items"] == 4
    assert body["last_sync"]["cards"]["error"] is None
    assert body["last_sync"]["prices"]["status"] == "partial"
    assert set(body["last_sync"]) == {"cards", "prices"}
