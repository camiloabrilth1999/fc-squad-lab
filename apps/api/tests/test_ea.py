"""Tests del adaptador EA → dominio (sbc/ea.py). Sin BD: solo traducción."""

from fcsl_api.sbc import ea
from fcsl_api.solver.models import Requirement


def _req(scope: int, count: int, code: int, values: list[int], text: str) -> dict:
    return {"scope": scope, "count": count, "kv": {str(code): values}, "text": text}


def _challenge(reqs: list[dict], formation: str = "f442", cid: int = 1) -> dict:
    return {
        "setId": 9,
        "setName": "Set",
        "id": cid,
        "name": "Reto",
        "formation": formation,
        "repeatable": False,
        "requirements": reqs,
    }


def _one(raw_req: dict):
    (ch,) = ea.parse({"challenges": [_challenge([raw_req])]})
    assert len(ch.requirements) == 1
    return ch.requirements[0]


def test_team_rating_min_and_max():
    assert _one(_req(1, -1, 19, [81], "Valoración del equipo: Mín. 81")) == Requirement(
        kind="TEAM_RATING", op="min", value=81
    )
    r = _one(_req(1, -1, 19, [85], "Valoración del equipo: Máx. 85"))
    assert r.kind == "TEAM_RATING" and r.op == "max" and r.value == 85


def test_team_chemistry():
    r = _one(_req(0, -1, 35, [25], "Química total: Mín. 25"))
    assert r.kind == "TEAM_CHEMISTRY" and r.op == "min" and r.value == 25


def test_distinct_and_same():
    r = _one(_req(2, -1, 8, [3], "Ligas en la plantilla: Exactamente 3"))
    assert r.kind == "DISTINCT_LEAGUES" and r.op == "exact" and r.value == 3
    r = _one(_req(1, -1, 6, [2], "Futbolistas que comparten Club: Máx. 2"))
    assert r.kind == "SAME_CLUB" and r.op == "max" and r.value == 2


def test_players_by_id_uses_count_as_value_and_values_as_ids():
    r = _one(_req(0, 2, 10, [45, 14], "España O Inglaterra: Mín. 2 futbolista(s)"))
    assert r.kind == "NATION_PLAYERS" and r.op == "min" and r.value == 2
    assert r.ids == [45, 14]


def test_level_players_count():
    r = _one(_req(0, 10, 17, [2], "Plata: Mín. 10 futbolista(s)"))
    assert r.kind == "LEVEL_PLAYERS" and r.op == "min" and r.value == 10 and r.tags == ["silver"]


def test_quality_floor_exact_is_single_tier_for_whole_squad():
    r = _one(_req(2, -1, 3, [1], "Calidad de futbolista: Exactamente Bronce"))
    assert r.kind == "LEVEL_PLAYERS" and r.value == 11 and r.tags == ["bronze"]


def test_quality_floor_min_includes_better_tiers():
    r = _one(_req(0, -1, 3, [2], "Calidad de futbolista: Mín. Plata"))
    assert r.kind == "LEVEL_PLAYERS" and r.value == 11 and r.tags == ["silver", "gold"]


def test_rating_players_min():
    r = _one(_req(0, 2, 26, [65], "Futbolistas con GRL mínima de 65: Mín. 2"))
    assert r.kind == "RATING_PLAYERS" and r.op == "min" and r.value == 2
    assert r.min_rating == 65 and r.max_rating is None


def test_rating_players_max():
    r = _one(_req(0, 3, 28, [70], "Futbolistas con GRL máxima de 70: Máx. 3"))
    assert r.kind == "RATING_PLAYERS" and r.op == "max" and r.value == 3
    assert r.max_rating == 70 and r.min_rating is None


def test_unsupported_code_skips_whole_challenge():
    # Código 40 (topes de rating de un clic) aún sin traducir: el reto se omite.
    raw = _challenge([_req(0, 2, 40, [65], "Requisito aún no soportado")])
    assert ea.parse({"challenges": [raw]}) == []


def test_real_capture_loads_all_as_ea_source():
    challenges = ea.load()
    assert len(challenges) == 22
    assert all(c.source == "ea" for c in challenges)
    ids = {c.id for c in challenges}
    assert {"ea-18", "ea-217", "ea-168"} <= ids
    # Todos sus requisitos deben poder resolverse (kinds soportados por el solver).
    for c in challenges:
        assert c.requirements, c.id
        assert len(c.slots()) == 11
