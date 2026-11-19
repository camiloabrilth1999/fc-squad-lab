from collections.abc import Iterator
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from fcsl_api.main import app
from fcsl_api.models_db import Card, ClubItem
from fcsl_api.routes import imports
from fcsl_api.sbc.pool import club_cards

pytestmark = pytest.mark.db

TOKEN = "secreto-de-prueba"
H = {"X-FCSL-Token": TOKEN}
NOW = datetime.now(UTC)
FUTURE = int(NOW.timestamp()) + 86400 * 3
PAST = int(NOW.timestamp()) - 86400


@pytest.fixture
def client(clean_db: Session, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    monkeypatch.setenv("FCSL_IMPORT_TOKEN", TOKEN)

    def _session() -> Iterator[Session]:
        yield clean_db

    app.dependency_overrides[imports.get_db] = _session
    yield TestClient(app)
    app.dependency_overrides.clear()


def _item(item_id: int, resource_id: int, **extra) -> dict:
    return {
        "id": item_id,
        "resourceId": resource_id,
        "assetId": resource_id,
        "rating": 85,
        "itemType": "player",
        **extra,
    }


def _import(client: TestClient, *items: dict) -> None:
    r = client.post(
        "/import/club",
        json={"location": "club", "items": list(items), "duplicate_item_ids": []},
        headers=H,
    )
    assert r.status_code == 200


def test_import_detects_match_loans_and_time_limited_loans(
    client: TestClient, clean_db: Session
) -> None:
    _import(
        client,
        _item(1, 100),  # tuya
        _item(2, 101, loans=5, loansInfo={"loanType": "MATCH_LOAN", "loanValue": 5}),
        _item(
            3, 102, loansInfo={"loanType": "USER_TIME_LIMIT_LOAN", "loanValue": FUTURE}
        ),  # sin `loans`
    )
    rows = {i.item_id: i for i in clean_db.query(ClubItem)}
    assert [rows[k].loan for k in (1, 2, 3)] == [False, True, True]
    assert (rows[2].loan_type, rows[2].loan_value) == ("MATCH_LOAN", 5)
    assert (rows[3].loan_type, rows[3].loan_value) == ("USER_TIME_LIMIT_LOAN", FUTURE)
    assert rows[1].loan_type is None


def test_reimport_clears_a_loan_that_became_yours(client: TestClient, clean_db: Session) -> None:
    _import(client, _item(1, 100, loansInfo={"loanType": "MATCH_LOAN", "loanValue": 2}, loans=2))
    _import(client, _item(1, 100))  # ya lo compraste / lo fichaste
    row = clean_db.get(ClubItem, 1)
    assert row.loan is False and row.loan_type is None and row.loan_value is None


def _card(db: Session, rid: int, name: str) -> None:
    db.add(
        Card(
            resource_id=rid,
            asset_id=rid,
            name=name,
            rating=85,
            positions=["ST"],
            league_id=1,
            nation_id=1,
            club_id=1,
        )
    )


def _seed_club(db: Session) -> None:
    for rid, name in (
        (100, "Mia"),
        (101, "Cedido por partidos"),
        (102, "Cedido por tiempo"),
        (103, "Cedido caducado"),
    ):
        _card(db, rid, name)
    db.add(
        ClubItem(
            item_id=100, resource_id=100, location="club", loan=False, seen_at=NOW, imported_at=NOW
        )
    )
    db.add(
        ClubItem(
            item_id=101,
            resource_id=101,
            location="club",
            loan=True,
            loan_type="MATCH_LOAN",
            loan_value=5,
            seen_at=NOW,
            imported_at=NOW,
        )
    )
    db.add(
        ClubItem(
            item_id=102,
            resource_id=102,
            location="club",
            loan=True,
            loan_type="USER_TIME_LIMIT_LOAN",
            loan_value=FUTURE,
            seen_at=NOW,
            imported_at=NOW,
        )
    )
    db.add(
        ClubItem(
            item_id=103,
            resource_id=103,
            location="club",
            loan=True,
            loan_type="USER_TIME_LIMIT_LOAN",
            loan_value=PAST,
            seen_at=NOW,
            imported_at=NOW,
        )
    )
    db.commit()


def test_club_cards_excludes_loans_by_default(clean_db: Session) -> None:
    _seed_club(clean_db)
    assert {c.name for c in club_cards(clean_db, NOW)} == {"Mia"}


def test_club_cards_can_include_active_loans_but_never_expired_ones(clean_db: Session) -> None:
    _seed_club(clean_db)
    names = {c.name for c in club_cards(clean_db, NOW, include_loans=True)}
    assert names == {"Mia", "Cedido por partidos", "Cedido por tiempo"}  # la caducada nunca


def test_club_endpoint_labels_loans(client: TestClient, clean_db: Session) -> None:
    _seed_club(clean_db)
    by_name = {r["name"]: r for r in client.get("/club").json()["items"]}
    assert by_name["Mia"]["loan"] is False and by_name["Mia"]["loan_label"] is None
    assert by_name["Cedido por partidos"]["loan_label"] == "Cedido: 5 partidos"
    assert by_name["Cedido por tiempo"]["loan_label"].startswith("Temporal: hasta ")
    assert by_name["Cedido por partidos"]["value"] == 0  # no es tuyo: no suma valor


def test_club_summary_counts_loans_apart_and_hides_expired_ones(
    client: TestClient, clean_db: Session
) -> None:
    _seed_club(clean_db)
    body = client.get("/club").json()
    assert body["summary"]["loans"] == 2  # por partidos y por tiempo vigente
    assert "Cedido caducado" not in {r["name"] for r in body["items"]}  # EA ya la retiró


def test_squad_builder_ignores_loans_unless_asked(client: TestClient, clean_db: Session) -> None:
    # una carta propia por posición del 442 + un cedido muy superior de portero
    positions = ["GK", "LB", "CB", "CB", "RB", "LM", "CM", "CM", "RM", "ST", "ST"]
    for i, pos in enumerate(positions, start=1):
        clean_db.add(
            Card(
                resource_id=i,
                asset_id=i,
                name=f"J{i}",
                rating=70,
                positions=[pos],
                league_id=1,
                nation_id=1,
                club_id=1,
            )
        )
        clean_db.add(
            ClubItem(
                item_id=i, resource_id=i, location="club", loan=False, seen_at=NOW, imported_at=NOW
            )
        )
    clean_db.add(
        Card(
            resource_id=99,
            asset_id=99,
            name="Estrella cedida",
            rating=95,
            positions=["ST"],
            league_id=1,
            nation_id=1,
            club_id=1,
        )
    )
    clean_db.add(
        ClubItem(
            item_id=99,
            resource_id=99,
            location="club",
            loan=True,
            loan_type="MATCH_LOAN",
            loan_value=3,
            seen_at=NOW,
            imported_at=NOW,
        )
    )
    clean_db.commit()
    names = lambda body: {
        s["name"]
        for s in client.post("/squad/build", json={"formation": "442", **body}).json()["slots"]
    }
    assert "Estrella cedida" not in names({})
    with_loans = client.post(
        "/squad/build", json={"formation": "442", "include_loans": True}
    ).json()
    star = next(s for s in with_loans["slots"] if s["name"] == "Estrella cedida")
    assert star["loan"] is True
