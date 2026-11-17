from fastapi.testclient import TestClient

from fcsl_api.main import app

client = TestClient(app)


def _card(i, pos="CM", **kw):
    d = {
        "card_id": f"market:{i}",
        "resource_id": i,
        "asset_id": i,
        "name": f"J{i}",
        "rating": 80,
        "positions": [pos],
        "league_id": 1,
        "nation_id": 1,
        "club_id": 1,
        "source": "market",
        "price": 1000,
    }
    d.update(kw)
    return d


def _body(**kw):
    body = {"slots": ["CM", "ST"], "cards": [_card(1), _card(2, "ST")]}
    body.update(kw)
    return body


def test_api_solve_ok():
    r = client.post("/solve", json=_body())
    assert r.status_code == 200
    assert r.json()["status"] == "optimal"


def test_api_solve_pools():
    r = client.post("/solve/pools", json=_body())
    assert r.status_code == 200
    assert [s["pool"] for s in r.json()] == ["market"]


def test_api_invalid_body_422():
    assert client.post("/solve", json={"slots": []}).status_code == 422


def test_api_invalid_op_422():
    req = {"kind": "PLAYER_CHEMISTRY", "op": "max", "value": 2}
    r = client.post("/solve", json=_body(requirements=[req]))
    assert r.status_code == 422
    assert "PLAYER_CHEMISTRY" in r.text


def test_api_invalid_requirement_inputs_422():
    for req in (
        {"kind": "LEAGUE_PLAYERS", "value": 2},
        {"kind": "TAG_PLAYERS", "value": 1},
        {"kind": "LEVEL_PLAYERS", "value": 1, "tags": ["diamond"]},
    ):
        assert client.post("/solve", json=_body(requirements=[req])).status_code == 422
