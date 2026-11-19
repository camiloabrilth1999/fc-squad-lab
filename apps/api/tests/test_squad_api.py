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
