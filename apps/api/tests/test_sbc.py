from collections.abc import Iterator
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from fcsl_api.main import app
from fcsl_api.models_db import Card, ClubItem
from fcsl_api.routes import imports
from fcsl_api.sbc import catalog, formations
from fcsl_api.sbc.models import SbcChallenge
from fcsl_api.sbc.service import solve_challenge

pytestmark = pytest.mark.db

NOW = datetime.now(UTC)
POS_442 = formations.slots_for("442")


@pytest.fixture
def session(clean_db: Session) -> Iterator[Session]:
    def _session() -> Iterator[Session]:
        yield clean_db

    app.dependency_overrides[imports.get_db] = _session
    yield clean_db
    app.dependency_overrides.clear()


@pytest.fixture
def client(session: Session) -> TestClient:
    return TestClient(app)


def _seed_club(session: Session, ratings: list[int] | None = None) -> None:
    ratings = ratings or [90, 88, 87, 87, 86, 85, 88, 86, 85, 90, 89]
    cards = []
    items = []
    for i, (pos, rt) in enumerate(zip(POS_442, ratings, strict=True), start=1):
        cards.append(
            Card(
                resource_id=i,
                asset_id=i,
                name=f"J{i}",
                rating=rt,
                positions=[pos],
                league_id=1,
                nation_id=10,
                club_id=100,
                rarity_name="Rare",
            )
        )
        items.append(
            ClubItem(
                item_id=100 + i,
                resource_id=i,
                rating=rt,
                untradeable=False,
                location="club",
                duplicate=False,
                loan=False,
                imported_at=NOW,
                seen_at=NOW,
                last_sale_price=500,
            )
        )
    session.add_all(cards)
    session.add_all(items)
    session.commit()


def _challenge(value: int) -> SbcChallenge:
    return SbcChallenge(
        id="t",
        set_id="s",
        set_name="S",
        name="N",
        formation="442",
        requirements=[{"kind": "TEAM_RATING", "op": "min", "value": value}],
    )


# ---- formaciones y catálogo (sin BD) ----


def test_formation_slots():
    assert len(formations.slots_for("442")) == 11
    assert formations.slots_for("f433") == formations.slots_for("433")
    assert formations.slots_for("desconocida") == formations.slots_for("442")


def test_catalog_loads_and_parses():
    sums = catalog.summaries()
    assert sums, "el catálogo no debe estar vacío"
    ids = {s.id for s in sums}
    assert "ea-18" in ids  # Mejora de Oro (capturado de EA)
    ch = catalog.get("ea-18")
    assert ch is not None and ch.source == "ea"
    assert ch.requirements[0].kind == "LEVEL_PLAYERS"
    assert catalog.get("no-existe") is None


# ---- resolver con el club (BD) ----


def test_solve_with_club_fills_squad(session: Session):
    _seed_club(session)
    res = solve_challenge(_challenge(81), session, pool="club")
    assert res.status in ("optimal", "feasible")
    assert len(res.squad) == 11
    assert res.buys == 0 and res.cost == 0
    assert all(s.source == "club" for s in res.squad)
    assert res.team_rating >= 81


def test_solve_infeasible_when_club_too_weak(session: Session):
    _seed_club(session)
    res = solve_challenge(_challenge(95), session, pool="club")
    assert res.status == "infeasible"
    assert res.squad == []


def test_solve_without_cards_explains(session: Session):
    res = solve_challenge(_challenge(81), session, pool="club")
    assert res.status == "infeasible"
    assert res.squad == []
    assert res.message and "club" in res.message.lower()


# ---- endpoints ----


def test_list_endpoint(client: TestClient):
    body = client.get("/sbc").json()
    assert any(c["id"] == "ea-18" for c in body)


def test_detail_endpoint(client: TestClient):
    assert client.get("/sbc/ea-18").status_code == 200
    assert client.get("/sbc/no-existe").status_code == 404


def test_solve_endpoint(client: TestClient, session: Session):
    _seed_club(session)
    # ea-217 "Simona Botero": 442 + calidad mín. Oro -> el club semilla (11 oros) lo cumple.
    r = client.post("/sbc/ea-217/solve", params={"pool": "club"})
    assert r.status_code == 200
    body = r.json()
    assert body["status"] in ("optimal", "feasible")
    assert len(body["squad"]) == 11
    assert client.post("/sbc/no-existe/solve").status_code == 404
