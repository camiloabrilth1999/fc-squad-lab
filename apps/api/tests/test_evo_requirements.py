from types import SimpleNamespace

from fcsl_api.evolutions.requirements import (
    POSITION_IDS,
    check,
    decode,
    describe,
    facts_for,
)

# Filas crudas reales de EA: "Introducción a las Evoluciones" y "Bajo los focos".
ATTR, SCOPE, TARGET, EXTRA = (
    "PLAYER_ATTRIBUTE",
    "SCOPE",
    "ACADEMY_PLAYER_SLOTTING",
    "ADDITIONAL_TARGET_VALUE",
)


def _row(kind: str, key: int, slot: int, value: int) -> dict:
    return {"type": kind, "key": key, "slot": slot, "value": value}


def _req(slot: int, attribute: int, scope: int, value: int, *extra: int) -> list[dict]:
    rows = [
        _row(ATTR, 41, slot, attribute),
        _row(SCOPE, 13, slot, scope),
        _row(TARGET, 40, slot, value),
    ]
    rows += [_row(EXTRA, 42, slot, v) for v in extra]
    return rows


INTRO = (
    _req(1, 1, 1, 75)  # GRL máximo 75
    + _req(2, 47, 2, 3)  # posición LD
    + _req(3, 48, 2, 5)  # no debe ser DFC
    + _req(4, 49, 1, 2)  # posiciones totales máx. 2
    + _req(5, 2, 1, 80)  # ritmo máximo 80
    + _req(6, 50, 1, 7)  # estilos de juego máx. 7
)
FOCOS = (
    _req(1, 1, 1, 80)
    + _req(2, 47, 2, 18, 14)  # posición MCO o MC
    + _req(3, 2, 1, 86)
    + _req(4, 14, 1, 82)
    + _req(5, 50, 1, 7)
    + _req(6, 51, 1, 0)
)


def test_decode_groups_rows_by_slot():
    reqs = decode(FOCOS)
    assert [(r.attribute, r.scope, r.values) for r in reqs] == [
        (1, 1, [80]),
        (47, 2, [18, 14]),
        (2, 1, [86]),
        (14, 1, [82]),
        (50, 1, [7]),
        (51, 1, [0]),
    ]


def test_decode_ignores_incomplete_slots():
    rows = [_row(ATTR, 41, 1, 1)]  # sin scope ni valor
    assert decode(rows) == []


def test_describe_matches_the_texts_the_game_shows():
    texts = [describe(r) for r in decode(FOCOS)]
    assert texts == [
        "GRL máximo: 80",
        "Posición: MCO O MC",
        "Ritmo máximo: 86",
        "Fuerza máxima: 82",
        "N.º de Estilo de juego máx.: 7",
        "N.º de Estilo de juego+ máx.: 0",
    ]
    intro = [describe(r) for r in decode(INTRO)]
    assert intro[1:4] == ["Posición: LD", "No debe ser: DFC", "Posiciones totales máx.: 2"]


def _card(**kw):
    base = {
        "rating": 74,
        "positions": ["CAM", "CM"],
        "face_stats": {"pace": 80, "strength": 70},
        "play_styles": [1, 2],
        "play_styles_plus": [],
        "weak_foot": 3,
        "skill_moves": 4,
        "rarity_ea_id": 0,
        "league_id": 13,
        "nation_id": 14,
        "club_id": 5,
    }
    base.update(kw)
    return SimpleNamespace(**base)


def test_check_focos_accepts_a_matching_midfielder():
    facts = facts_for(_card(), {"strength": 75})
    assert all(check(r, facts) is True for r in decode(FOCOS))


def test_check_rejects_by_each_criterion():
    reqs = {r.attribute: r for r in decode(FOCOS)}
    assert check(reqs[1], facts_for(_card(rating=81), None)) is False  # GRL > 80
    assert check(reqs[47], facts_for(_card(positions=["ST"]), None)) is False  # posición
    assert check(reqs[2], facts_for(_card(face_stats={"pace": 90}), None)) is False  # ritmo
    assert check(reqs[51], facts_for(_card(play_styles_plus=[22]), None)) is False  # EJ+ máx. 0


def test_check_negated_position_and_counts():
    reqs = {r.attribute: r for r in decode(INTRO)}
    assert check(reqs[47], facts_for(_card(positions=["RB"]), None)) is True
    # «Posición» es la preferida: un LD con DFC alternativo cumple; un DFC no
    assert check(reqs[48], facts_for(_card(positions=["RB", "CB"]), None)) is True
    assert check(reqs[48], facts_for(_card(positions=["CB", "RB"]), None)) is False
    assert check(reqs[49], facts_for(_card(positions=["RB", "RWB", "RM"]), None)) is False  # 3 > 2


def test_check_returns_none_when_the_data_is_missing():
    strength = next(r for r in decode(FOCOS) if r.attribute == 14)
    # sin stats detallados ni fuerza en la cara no se puede saber
    facts = facts_for(_card(face_stats={"pace": 80}), None)
    assert check(strength, facts) is None
    # con la fuerza de la cara sí
    assert check(strength, facts_for(_card(), None)) is True


def test_between_and_min_scopes():
    between = decode(_req(1, 1, 3, 70, 80))[0]
    assert check(between, facts_for(_card(rating=75), None)) is True
    assert check(between, facts_for(_card(rating=81), None)) is False
    minimum = decode(_req(1, 1, 0, 76))[0]
    assert check(minimum, facts_for(_card(rating=75), None)) is False
    assert describe(minimum) == "GRL mínimo: 76"


def test_position_ids_use_ea_standard():
    assert POSITION_IDS["GK"] == 0 and POSITION_IDS["RB"] == 3 and POSITION_IDS["CAM"] == 18
