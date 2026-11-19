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


def _levels(count: int, cap: int) -> list[dict]:
    return [
        {"level": 0, "state": "NOT_STARTED", "objectives": [], "awards": []},
        {
            "level": 1,
            "state": "NOT_STARTED",
            "objectives": [],
            "awards": [
                {"stat": 21, "count": count, "max_value": cap},
                {"stat": 23, "count": count, "max_value": cap},
            ],
        },
    ]


@pytest.fixture
def client(clean_db: Session, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    from fcsl_api.meta import fitted

    monkeypatch.setenv("FCSL_IMPORT_TOKEN", TOKEN)
    # meta = media de aceleración y agilidad, para los dos roles que usamos
    fit = {
        r: {"intercept": 0.0, "coef": {"acceleration": 0.5, "agility": 0.5}}
        for r in ("playmaker", "winger")
    }
    monkeypatch.setattr(fitted, "load_fitted", lambda: fit)

    def _session() -> Iterator[Session]:
        yield clean_db

    app.dependency_overrides[imports.get_db] = _session
    yield TestClient(app)
    app.dependency_overrides.clear()


def _evo(
    client: TestClient, sid: int, name: str, positions: list[int], count: int, cap: int = 99
) -> dict:
    return {
        "id": sid,
        "name": name,
        "status": "NOT_STARTED",
        "category_id": 0,
        "requirements": _req(1, 47, 2, positions[0], *positions[1:]),
        "levels": _levels(count, cap),
        "currencies": [],
    }


def _import(client: TestClient, *slots: dict) -> None:
    client.post("/import/evolutions", json={"categories": [], "slots": list(slots)}, headers=H)


def _player(db: Session, rid: int, name: str, pos: str, accel: int, agil: int) -> None:
    db.add(
        Card(
            resource_id=rid, asset_id=rid, name=name, rating=70, positions=[pos],
            league_id=1, nation_id=1, club_id=1, face_stats={"pace": 70},
            play_styles=[], play_styles_plus=[], skill_moves=3, weak_foot=3,
        )
    )  # fmt: skip
    db.add(ClubItem(item_id=rid, resource_id=rid, location="club", seen_at=NOW, imported_at=NOW))
    db.add(CardAttributes(resource_id=rid, stats={"acceleration": accel, "agility": agil}))


def test_for_card_lists_the_evolutions_it_can_take_best_first(
    client: TestClient, clean_db: Session
) -> None:
    # CAM = 18. Dos evoluciones para mediapuntas con distinta mejora
    _import(
        client,
        _evo(client, 1, "Pequeña", [18], 5),
        _evo(client, 2, "Grande", [18], 15),
        _evo(client, 3, "De DC", [25], 20),
    )
    _player(clean_db, 10, "Mediapunta", "CAM", 60, 60)
    clean_db.commit()
    body = client.get("/evolutions/for-card/10").json()
    assert body["card"]["name"] == "Mediapunta"
    assert [e["evolution"]["name"] for e in body["items"]] == [
        "Grande",
        "Pequeña",
    ]  # la de DC no aplica
    top = body["items"][0]
    assert top["meta_before"] == 60.0 and top["meta_after"] == 75.0 and top["meta_gain"] == 15.0


def test_for_card_404(client: TestClient) -> None:
    assert client.get("/evolutions/for-card/999").status_code == 404


def test_plan_assigns_each_evolution_and_card_once_maximizing_gain(
    client: TestClient, clean_db: Session
) -> None:
    # Dos evoluciones de mediapunta; ambas quieren a la misma carta (la que más gana)
    _import(client, _evo(client, 1, "Grande", [18], 15), _evo(client, 2, "Pequeña", [18], 5))
    _player(clean_db, 10, "Candidata A", "CAM", 60, 60)  # +15 con Grande, +5 con Pequeña
    _player(clean_db, 11, "Candidata B", "CAM", 70, 70)  # +15 con Grande, +5 con Pequeña también
    clean_db.commit()
    plan = client.get("/evolutions/plan").json()
    assert plan["total_gain"] == 20.0  # 15 + 5: no se puede usar la misma carta dos veces
    assert {a["evolution"]["name"] for a in plan["assignments"]} == {"Grande", "Pequeña"}
    assert len({a["card"]["item_id"] for a in plan["assignments"]}) == 2


def test_plan_prefers_the_pairing_with_the_best_total(
    client: TestClient, clean_db: Session
) -> None:
    # Grande solo admite mediapuntas; Pequeña admite mediapuntas y delanteros.
    _import(client, _evo(client, 1, "Grande", [18], 15), _evo(client, 2, "Pequeña", [18, 25], 5))
    _player(clean_db, 10, "Mediapunta", "CAM", 60, 60)
    _player(clean_db, 11, "Delantero", "ST", 60, 60)  # solo puede ir a Pequeña
    clean_db.commit()
    plan = client.get("/evolutions/plan").json()
    by_evo = {a["evolution"]["name"]: a["card"]["name"] for a in plan["assignments"]}
    assert by_evo == {"Grande": "Mediapunta", "Pequeña": "Delantero"}  # óptimo: 15 + 5


def test_plan_min_after_filters_weak_results(client: TestClient, clean_db: Session) -> None:
    _import(client, _evo(client, 1, "Grande", [18], 15))
    _player(clean_db, 10, "Floja", "CAM", 40, 40)  # tras la evolución: 55
    _player(clean_db, 11, "Buena", "CAM", 70, 70)  # tras la evolución: 85
    clean_db.commit()
    plan = client.get("/evolutions/plan", params={"min_after": 80}).json()
    assert [a["card"]["name"] for a in plan["assignments"]] == ["Buena"]


def test_plan_ignores_unknown_and_expired(client: TestClient, clean_db: Session) -> None:
    past = int(datetime.now(UTC).timestamp()) - 86400
    expired = _evo(client, 1, "Caducada", [18], 15)
    expired["end_time"] = past
    expired["timed"] = True
    _import(client, expired)
    _player(clean_db, 10, "Mediapunta", "CAM", 60, 60)
    clean_db.commit()
    plan = client.get("/evolutions/plan").json()
    assert plan["assignments"] == [] and plan["total_gain"] == 0.0
