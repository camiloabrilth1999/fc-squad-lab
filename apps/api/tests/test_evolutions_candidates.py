from collections.abc import Iterator
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from fcsl_api.main import app
from fcsl_api.models_db import Card, CardAttributes, ClubItem
from fcsl_api.routes import imports

pytestmark = pytest.mark.db

TOKEN = "secreto-de-prueba"
H = {"X-FCSL-Token": TOKEN}
NOW = datetime.now(UTC)
ATTR, SCOPE, TARGET, EXTRA = (
    "PLAYER_ATTRIBUTE",
    "SCOPE",
    "ACADEMY_PLAYER_SLOTTING",
    "ADDITIONAL_TARGET_VALUE",
)


def _req(slot: int, attribute: int, scope: int, value: int, *extra: int) -> list[dict]:
    rows = [
        {"type": ATTR, "key": 41, "slot": slot, "value": attribute},
        {"type": SCOPE, "key": 13, "slot": slot, "value": scope},
        {"type": TARGET, "key": 40, "slot": slot, "value": value},
    ]
    return rows + [{"type": EXTRA, "key": 42, "slot": slot, "value": v} for v in extra]


FOCOS = (
    _req(1, 1, 1, 80) + _req(2, 47, 2, 18, 14) + _req(3, 2, 1, 86)
)  # GRL ≤ 80, MCO/MC, ritmo ≤ 86
LEVELS = [
    {"level": 0, "state": "NOT_STARTED", "objectives": [], "awards": []},
    {
        "level": 1,
        "state": "NOT_STARTED",
        "objectives": [{"id": 1, "name": "Juega", "description": "*"}],
        "awards": [
            {"stat": 23, "count": 18, "max_value": 85},
            {"stat": 21, "count": 6, "max_value": 80},
        ],
    },
]


@pytest.fixture
def client(clean_db: Session, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    monkeypatch.setenv("FCSL_IMPORT_TOKEN", TOKEN)

    def _session() -> Iterator[Session]:
        yield clean_db

    app.dependency_overrides[imports.get_db] = _session
    yield TestClient(app)
    app.dependency_overrides.clear()


def _evolution(client: TestClient) -> None:
    slot = {
        "id": 2850,
        "name": "Bajo los focos",
        "status": "NOT_STARTED",
        "category_id": 0,
        "requirements": FOCOS,
        "levels": LEVELS,
        "currencies": [],
    }
    client.post("/import/evolutions", json={"categories": [], "slots": [slot]}, headers=H)


def _player(
    db: Session, rid: int, name: str, rating: int, positions: list[str], pace: int, *, stats=True
) -> None:
    db.add(
        Card(
            resource_id=rid,
            asset_id=rid,
            name=name,
            rating=rating,
            positions=positions,
            league_id=1,
            nation_id=1,
            club_id=1,
            face_stats={"pace": pace, "strength": 70},
            play_styles=[],
            play_styles_plus=[],
            skill_moves=3,
            weak_foot=3,
        )
    )
    db.add(ClubItem(item_id=rid, resource_id=rid, location="club", seen_at=NOW, imported_at=NOW))
    if stats:
        db.add(
            CardAttributes(
                resource_id=rid, stats={"acceleration": 70, "agility": 60, "strength": 70}
            )
        )


def test_evolution_lists_readable_requirements(client: TestClient) -> None:
    _evolution(client)
    e = client.get("/evolutions").json()["items"][0]
    assert e["requirements"] == ["GRL máximo: 80", "Posición: MCO O MC", "Ritmo máximo: 86"]


def test_candidates_split_eligible_and_filter_the_rest(
    client: TestClient, clean_db: Session
) -> None:
    _evolution(client)
    _player(clean_db, 1, "Mediocentro apto", 76, ["CM"], 70)
    _player(clean_db, 2, "Muy bueno", 85, ["CAM"], 70)  # GRL 85 > 80: no cumple
    _player(clean_db, 3, "Delantero", 75, ["ST"], 70)  # posición no válida
    _player(clean_db, 4, "Rápido", 75, ["CAM"], 92)  # ritmo > 86
    clean_db.commit()
    body = client.get("/evolutions/2850/candidates").json()
    assert [i["name"] for i in body["items"]] == ["Mediocentro apto"]
    assert body["requirements"] == ["GRL máximo: 80", "Posición: MCO O MC", "Ritmo máximo: 86"]
    assert body["eligible_count"] == 1 and body["total_checked"] == 4


def test_candidates_include_meta_before_and_after(
    client: TestClient, clean_db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    from fcsl_api.meta import fitted

    fit = {"playmaker": {"intercept": 0.0, "coef": {"acceleration": 0.5, "agility": 0.5}}}
    monkeypatch.setattr(fitted, "load_fitted", lambda: fit)
    _evolution(client)
    _player(clean_db, 1, "Mediapunta", 76, ["CAM"], 70)  # aceleración 70, agilidad 60
    clean_db.commit()
    item = client.get("/evolutions/2850/candidates").json()["items"][0]
    assert item["eligible"] is True
    assert item["meta_before"] == 65.0  # 0.5*70 + 0.5*60
    assert item["meta_after"] == 77.0  # aceleración 76 (tope 80), agilidad 78 (tope 85)
    assert item["meta_gain"] == 12.0


def test_candidates_sorted_by_gain_and_unknown_when_data_missing(
    client: TestClient, clean_db: Session
) -> None:
    _evolution(client)
    _player(clean_db, 1, "Con stats", 76, ["CAM"], 70)
    _player(clean_db, 2, "Sin cara", 76, ["CAM"], 70, stats=False)
    card = clean_db.get(Card, 2)
    card.face_stats = {"strength": 70}  # sin ritmo: no se puede saber
    clean_db.commit()
    body = client.get("/evolutions/2850/candidates").json()
    by_name = {i["name"]: i for i in body["items"]}
    assert by_name["Con stats"]["eligible"] is True
    assert by_name["Sin cara"]["eligible"] is None and by_name["Sin cara"]["unknown"] == [
        "Ritmo máximo: 86"
    ]
    assert body["unknown_count"] == 1


def test_candidates_404_for_unknown_evolution(client: TestClient) -> None:
    assert client.get("/evolutions/99999/candidates").status_code == 404


def test_candidates_sort_by_final_meta_or_by_gain(
    client: TestClient, clean_db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    from fcsl_api.meta import fitted

    fit = {"playmaker": {"intercept": 0.0, "coef": {"acceleration": 0.5, "agility": 0.5}}}
    monkeypatch.setattr(fitted, "load_fitted", lambda: fit)
    _evolution(client)
    _player(clean_db, 1, "Flojo", 70, ["CAM"], 70)
    _player(clean_db, 2, "Bueno", 76, ["CAM"], 70)
    clean_db.get(CardAttributes, 1).stats = {
        "acceleration": 60,
        "agility": 40,
        "strength": 70,
    }  # mucho margen
    clean_db.get(CardAttributes, 2).stats = {
        "acceleration": 79,
        "agility": 80,
        "strength": 70,
    }  # poco margen
    clean_db.commit()

    def names(sort: str) -> list[str]:
        items = client.get("/evolutions/2850/candidates", params={"sort": sort}).json()["items"]
        return [i["name"] for i in items]

    assert names("after")[0] == "Bueno"  # mejor carta final
    assert names("gain")[0] == "Flojo"  # mayor mejora
