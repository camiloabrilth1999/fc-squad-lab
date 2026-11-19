from collections.abc import Iterator
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from fcsl_api.main import app
from fcsl_api.models_db import Card, CardAttributes, ClubItem
from fcsl_api.routes import imports

pytestmark = pytest.mark.db

NOW = datetime.now(UTC)


@pytest.fixture
def client(clean_db: Session) -> Iterator[TestClient]:
    def _session() -> Iterator[Session]:
        yield clean_db

    app.dependency_overrides[imports.get_db] = _session
    yield TestClient(app)
    app.dependency_overrides.clear()


POSITIONS_442 = ["GK", "LB", "CB", "CB", "RB", "LM", "CM", "CM", "RM", "ST", "ST"]


def _seed(db: Session, positions: list[str]) -> None:
    for i, pos in enumerate(positions, start=1):
        db.add(
            Card(
                resource_id=i,
                asset_id=i,
                name=f"J{i}",
                rating=80 + i,
                positions=[pos],
                league_id=1,
                nation_id=1,
                club_id=1,
            )
        )
        db.add(ClubItem(item_id=i, resource_id=i, location="club", seen_at=NOW, imported_at=NOW))
    db.add(CardAttributes(resource_id=11, stats={"finishing": 99, "acceleration": 90}))
    db.commit()


def test_build_full_xi_with_meta_and_chemistry(client: TestClient, clean_db: Session) -> None:
    _seed(clean_db, POSITIONS_442)
    body = client.post("/squad/build", json={"formation": "442"}).json()
    assert body["status"] in ("optimal", "feasible")
    assert len(body["slots"]) == 11
    assert body["team_chemistry"] == 33  # todos misma liga/nación/club, en posición
    by_pos = {s["resource_id"]: s for s in body["slots"]}
    assert by_pos[11]["meta_source"] == "stats" and by_pos[1]["meta_source"] == "rating"


def test_build_infeasible_when_a_position_is_missing(client: TestClient, clean_db: Session) -> None:
    _seed(clean_db, POSITIONS_442[:-2] + ["CM", "CM"])  # nadie juega de ST
    body = client.post("/squad/build", json={"formation": "442"}).json()
    assert body["status"] == "infeasible" and "ST" in body["message"]
    assert body["slots"] == []


def test_build_unknown_formation_falls_back_to_default(
    client: TestClient, clean_db: Session
) -> None:
    _seed(clean_db, POSITIONS_442)
    body = client.post("/squad/build", json={"formation": "zzz"}).json()
    assert body["formation"] == "442"


def _seed_market(db: Session, with_stats: bool = True) -> None:
    from fcsl_api.models_db import Price

    db.add(
        Card(
            resource_id=100,
            asset_id=100,
            name="Fichaje",
            rating=95,
            positions=["CB"],
            league_id=1,
            nation_id=1,
            club_id=1,
        )
    )
    db.add(Price(resource_id=100, platform="PC", source="easysbc:market", price=5000))
    if with_stats:
        db.add(
            CardAttributes(
                resource_id=100,
                stats={
                    n: 99
                    for n in (
                        "def_awareness",
                        "standing_tackle",
                        "interceptions",
                        "heading",
                        "strength",
                        "reactions",
                        "sprint_speed",
                        "acceleration",
                        "balance",
                        "aggression",
                        "sliding_tackle",
                        "jumping",
                    )
                },
            )
        )
    db.commit()


def test_market_card_is_bought_when_budget_allows(client: TestClient, clean_db: Session) -> None:
    _seed(clean_db, POSITIONS_442)
    _seed_market(clean_db)
    body = client.post(
        "/squad/build", json={"formation": "442", "pool": "both", "budget": 10000}
    ).json()
    bought = [s for s in body["slots"] if s["source"] == "market"]
    assert [s["name"] for s in bought] == ["Fichaje"] and bought[0]["price"] == 5000
    assert body["spent"] == 5000 and body["pending_stats"] == 0


def test_market_card_not_bought_when_over_budget(client: TestClient, clean_db: Session) -> None:
    _seed(clean_db, POSITIONS_442)
    _seed_market(clean_db)
    body = client.post(
        "/squad/build", json={"formation": "442", "pool": "both", "budget": 1000}
    ).json()
    assert body["spent"] == 0 and all(s["source"] == "club" for s in body["slots"])


def test_market_candidates_without_stats_are_reported_not_used(
    client: TestClient, clean_db: Session
) -> None:
    _seed(clean_db, POSITIONS_442)
    _seed_market(clean_db, with_stats=False)
    body = client.post(
        "/squad/build", json={"formation": "442", "pool": "both", "budget": 10000}
    ).json()
    assert body["pending_stats"] == 1 and body["spent"] == 0


def test_pool_both_requires_budget(client: TestClient) -> None:
    r = client.post("/squad/build", json={"formation": "442", "pool": "both"})
    assert r.status_code == 422
