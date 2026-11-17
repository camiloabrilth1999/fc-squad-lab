import random
from collections import Counter

import pytest

from fcsl_api.solver.chemistry import team_chemistry
from fcsl_api.solver.cpsat import build_base_model, solve_model
from fcsl_api.solver.models import Requirement, RequirementKind
from fcsl_api.solver.rating import team_rating
from fcsl_api.solver.requirements import _HANDLERS, apply_requirement

from .bruteforce import brute_force
from .fixtures import make_card

K = RequirementKind


def _cards(specs):
    return [
        make_card(card_id=f"market:{i}", resource_id=i, asset_id=i, name=f"J{i}", **spec)
        for i, spec in enumerate(specs, start=1)
    ]


def _solve(cards, slots, costs, reqs, time_limit_s=5.0):
    m = build_base_model(cards, slots, costs)
    for req in reqs:
        apply_requirement(m, req)
    terms = [(costs[c], m.used[c]) for c in range(len(cards))]
    status, assignments, _ = solve_model(m, terms, time_limit_s)
    by_id = {card.card_id: (c, card) for c, card in enumerate(cards)}
    chosen = [by_id[a.card_id] for a in assignments]
    return status, [card for _, card in chosen], sum(costs[c] for c, _ in chosen)


def _req(kind, op, value, ids=(), tags=()):
    return Requirement(kind=kind, op=op, value=value, ids=list(ids), tags=list(tags))


OPS = {
    "min": lambda a, v: a >= v,
    "max": lambda a, v: a <= v,
    "exact": lambda a, v: a == v,
}

ATTR = {"league": "league_id", "nation": "nation_id", "club": "club_id"}
PLAYERS_KIND = {"league": K.LEAGUE_PLAYERS, "nation": K.NATION_PLAYERS, "club": K.CLUB_PLAYERS}
DISTINCT_KIND = {
    "league": K.DISTINCT_LEAGUES,
    "nation": K.DISTINCT_NATIONS,
    "club": K.DISTINCT_CLUBS,
}
SAME_KIND = {"league": K.SAME_LEAGUE, "nation": K.SAME_NATION, "club": K.SAME_CLUB}


# --- Comprobaciones en Python (semántica de referencia) ---


def check_players(attr, ids, op, value):
    return lambda chosen: OPS[op](sum(getattr(c, attr) in ids for c in chosen), value)


def check_distinct(attr, op, value):
    return lambda chosen: OPS[op](len({getattr(c, attr) for c in chosen}), value)


def check_same(attr, op, value):
    def check(chosen):
        biggest = max(Counter(getattr(c, attr) for c in chosen).values())
        return OPS[op](biggest, value)

    return check


def check_level(levels, op, value):
    return lambda chosen: OPS[op](sum(c.level in levels for c in chosen), value)


def check_rare(op, value):
    return lambda chosen: OPS[op](sum(c.rare for c in chosen), value)


def check_tag(tags, op, value):
    return lambda chosen: OPS[op](
        sum(any(t in c.rarity_tags for t in tags) for c in chosen), value
    )


# --- *_PLAYERS ---


@pytest.mark.parametrize("family", ["league", "nation", "club"])
@pytest.mark.parametrize("op", ["min", "max", "exact"])
def test_players_by_id(family, op):
    attr = ATTR[family]
    # 3 cartas del grupo 1, 1 del grupo 2, 4 de otros grupos.
    groups = [1, 1, 1, 2, 3, 4, 5, 6]
    cards = _cards([{attr: g} for g in groups])
    # min/exact: los del grupo son caros; max: son baratos.
    if op == "max":
        costs = [1, 1, 1, 1, 50, 50, 50, 50]
    else:
        costs = [50, 50, 50, 50, 1, 1, 1, 1]
    req = _req(PLAYERS_KIND[family], op, 2, ids=[1, 2])
    status, chosen, _ = _solve(cards, ["CM"] * 4, costs, [req])
    assert status == "optimal"
    assert check_players(attr, {1, 2}, op, 2)(chosen)
    n_in = sum(getattr(c, attr) in {1, 2} for c in chosen)
    assert n_in == 2  # el coste empuja justo hasta la cota


def test_players_by_id_infeasible():
    cards = _cards([{"league_id": 1}, {"league_id": 2}, {"league_id": 3}])
    req = _req(K.LEAGUE_PLAYERS, "min", 2, ids=[1])
    status, _, _ = _solve(cards, ["CM"] * 2, [1, 1, 1], [req])
    assert status == "infeasible"


@pytest.mark.parametrize("kind", [K.LEAGUE_PLAYERS, K.NATION_PLAYERS, K.CLUB_PLAYERS])
def test_players_by_id_requires_ids(kind):
    m = build_base_model(_cards([{}]), ["CM"], [1])
    with pytest.raises(ValueError, match="ids"):
        apply_requirement(m, _req(kind, "min", 1))


def test_icon_and_hero_count_by_their_own_ids_without_weights():
    # Icono (peso doble en nación para química) y héroe (doble en liga) cuentan 1.
    cards = _cards(
        [
            {"is_icon": True, "nation_id": 7, "league_id": 9, "club_id": 9},
            {"is_hero": True, "nation_id": 8, "league_id": 7, "club_id": 8},
            {"nation_id": 1, "league_id": 1, "club_id": 1},
        ]
    )
    costs = [1, 1, 50]
    # Exactamente 1 de la nación 7: el icono vale 1, no 2.
    status, chosen, _ = _solve(
        cards, ["CM"] * 2, costs, [_req(K.NATION_PLAYERS, "exact", 1, ids=[7])]
    )
    assert status == "optimal"
    assert {c.card_id for c in chosen} == {"market:1", "market:2"}
    # Máximo 1 de la liga 7: el héroe vale 1, así que sigue cabiendo.
    status, chosen, _ = _solve(
        cards, ["CM"] * 2, costs, [_req(K.LEAGUE_PLAYERS, "max", 1, ids=[7])]
    )
    assert status == "optimal"
    assert {c.card_id for c in chosen} == {"market:1", "market:2"}


# --- DISTINCT_* ---


@pytest.mark.parametrize("family", ["league", "nation", "club"])
def test_distinct_min(family):
    attr = ATTR[family]
    # Los del grupo 1 son baratos: sin la cota se elegirían 4 iguales.
    cards = _cards([{attr: 1}] * 4 + [{attr: g} for g in (2, 3, 4)])
    costs = [1, 1, 1, 1, 50, 50, 50]
    status, chosen, _ = _solve(cards, ["CM"] * 4, costs, [_req(DISTINCT_KIND[family], "min", 3)])
    assert status == "optimal"
    assert len({getattr(c, attr) for c in chosen}) == 3


@pytest.mark.parametrize("family", ["league", "nation", "club"])
@pytest.mark.parametrize("op", ["max", "exact"])
def test_distinct_max_and_exact(family, op):
    attr = ATTR[family]
    # Los de grupos distintos son baratos: sin la cota se elegirían 4 distintos.
    cards = _cards([{attr: 1}] * 4 + [{attr: g} for g in (2, 3, 4)])
    costs = [50, 50, 50, 50, 1, 1, 1]
    status, chosen, _ = _solve(cards, ["CM"] * 4, costs, [_req(DISTINCT_KIND[family], op, 2)])
    assert status == "optimal"
    assert len({getattr(c, attr) for c in chosen}) == 2


def test_distinct_infeasible():
    cards = _cards([{"club_id": 1}] * 3 + [{"club_id": 2}])
    status, _, _ = _solve(cards, ["CM"] * 3, [1] * 4, [_req(K.DISTINCT_CLUBS, "min", 3)])
    assert status == "infeasible"


def test_distinct_presence_is_cached_per_family():
    cards = _cards([{"club_id": g} for g in (1, 1, 2, 3)])
    m = build_base_model(cards, ["CM"] * 3, [1] * 4)
    apply_requirement(m, _req(K.DISTINCT_CLUBS, "min", 2))
    first = m.group_present["club"]
    apply_requirement(m, _req(K.DISTINCT_CLUBS, "max", 2))
    assert m.group_present["club"] is first
    assert set(first) == {1, 2, 3}


# --- SAME_* ---


@pytest.mark.parametrize("family", ["league", "nation", "club"])
def test_same_min(family):
    attr = ATTR[family]
    # Sueltos baratos; hace falta un bloque de 3 del mismo grupo.
    cards = _cards([{attr: 1}] * 2 + [{attr: 2}] * 3 + [{attr: g} for g in (3, 4, 5, 6)])
    costs = [5, 5, 20, 20, 20, 1, 1, 1, 1]
    status, chosen, _ = _solve(cards, ["CM"] * 4, costs, [_req(SAME_KIND[family], "min", 3)])
    assert status == "optimal"
    assert check_same(attr, "min", 3)(chosen)


@pytest.mark.parametrize("family", ["league", "nation", "club"])
def test_same_max(family):
    attr = ATTR[family]
    # Los del grupo 1 son baratos: sin la cota se elegirían 4 iguales.
    cards = _cards([{attr: 1}] * 4 + [{attr: g} for g in (2, 3, 4)])
    costs = [1, 1, 1, 1, 50, 50, 50]
    status, chosen, cost = _solve(cards, ["CM"] * 4, costs, [_req(SAME_KIND[family], "max", 2)])
    assert status == "optimal"
    assert check_same(attr, "max", 2)(chosen)
    assert cost == 1 + 1 + 50 + 50


@pytest.mark.parametrize("family", ["league", "nation", "club"])
@pytest.mark.parametrize("cheap_group", [True, False])
def test_same_exact(family, cheap_group):
    attr = ATTR[family]
    # cheap_group: el grupo 1 es barato (presiona hacia > value);
    # si no, los sueltos son baratos (presiona hacia < value).
    cards = _cards([{attr: 1}] * 4 + [{attr: g} for g in (2, 3, 4)])
    costs = [1, 1, 1, 1, 50, 50, 50] if cheap_group else [50, 50, 50, 50, 1, 1, 1]
    status, chosen, _ = _solve(cards, ["CM"] * 4, costs, [_req(SAME_KIND[family], "exact", 2)])
    assert status == "optimal"
    assert check_same(attr, "exact", 2)(chosen)


def test_same_min_infeasible():
    cards = _cards([{"nation_id": g} for g in (1, 1, 2, 2, 3)])
    status, _, _ = _solve(cards, ["CM"] * 4, [1] * 5, [_req(K.SAME_NATION, "min", 3)])
    assert status == "infeasible"


# --- LEVEL / RARE / TAG ---


LEVEL_RATINGS = [60, 62, 70, 72, 80, 82]  # bronce, bronce, plata, plata, oro, oro


@pytest.mark.parametrize("op", ["min", "max", "exact"])
def test_level_players(op):
    cards = _cards([{"rating": r} for r in LEVEL_RATINGS])
    # min/exact: los oros son caros; max: son baratos.
    costs = [1, 1, 1, 1, 50, 50] if op != "max" else [50, 50, 50, 50, 1, 1]
    req = _req(K.LEVEL_PLAYERS, op, 1, tags=["gold"])
    status, chosen, _ = _solve(cards, ["CM"] * 3, costs, [req])
    assert status == "optimal"
    assert sum(c.level == "gold" for c in chosen) == 1


def test_level_players_multiple_levels():
    cards = _cards([{"rating": r} for r in LEVEL_RATINGS])
    costs = [1, 1, 50, 50, 50, 50]
    req = _req(K.LEVEL_PLAYERS, "min", 3, tags=["silver", "gold"])
    status, chosen, _ = _solve(cards, ["CM"] * 4, costs, [req])
    assert status == "optimal"
    assert check_level({"silver", "gold"}, "min", 3)(chosen)
    assert sum(c.level == "bronze" for c in chosen) == 1


@pytest.mark.parametrize("tags", [[], ["platinum"], ["gold", "Gold"]])
def test_level_players_rejects_bad_tags(tags):
    m = build_base_model(_cards([{}]), ["CM"], [1])
    with pytest.raises(ValueError, match="LEVEL_PLAYERS"):
        apply_requirement(m, _req(K.LEVEL_PLAYERS, "min", 1, tags=tags))


@pytest.mark.parametrize("op", ["min", "max", "exact"])
def test_rare_players(op):
    cards = _cards([{"rare": r} for r in (True, True, True, False, False, False)])
    costs = [50, 50, 50, 1, 1, 1] if op != "max" else [1, 1, 1, 50, 50, 50]
    status, chosen, _ = _solve(cards, ["CM"] * 3, costs, [_req(K.RARE_PLAYERS, op, 2)])
    assert status == "optimal"
    assert sum(c.rare for c in chosen) == 2


@pytest.mark.parametrize("op", ["min", "max", "exact"])
def test_tag_players(op):
    tags = [["TOTW"], ["TOTW", "SPECIAL"], ["SPECIAL"], [], [], ["OTHER"]]
    cards = _cards([{"rarity_tags": t} for t in tags])
    costs = [50, 50, 50, 1, 1, 1] if op != "max" else [1, 1, 1, 50, 50, 50]
    req = _req(K.TAG_PLAYERS, op, 2, tags=["TOTW", "SPECIAL"])
    status, chosen, _ = _solve(cards, ["CM"] * 3, costs, [req])
    assert status == "optimal"
    # Una carta con dos etiquetas aceptadas cuenta una vez.
    assert check_tag(["TOTW", "SPECIAL"], "exact", 2)(chosen)


def test_tag_players_requires_tags():
    m = build_base_model(_cards([{}]), ["CM"], [1])
    with pytest.raises(ValueError, match="tags"):
        apply_requirement(m, _req(K.TAG_PLAYERS, "min", 1))


def test_every_kind_has_a_handler():
    assert set(_HANDLERS) == set(RequirementKind)


# --- Cruce con fuerza bruta ---


def _random_pool(rng, size):
    positions = ["GK", "CB", "CM", "ST"]
    specs = []
    for _ in range(size):
        specs.append(
            {
                "rating": rng.randint(58, 90),
                "positions": rng.sample(positions, rng.randint(1, 2)),
                "league_id": rng.randint(1, 3),
                "nation_id": rng.randint(1, 4),
                "club_id": rng.randint(1, 5),
                "rare": rng.random() < 0.4,
                "rarity_tags": rng.sample(["TOTW", "SPECIAL"], rng.randint(0, 1)),
            }
        )
    cards = _cards(specs)
    costs = [rng.randint(1, 100) for _ in cards]
    return cards, costs


def _random_case(rng, family_kind):
    """(requisito, comprobación) aleatorios para la familia pedida."""
    op = rng.choice(["min", "max"])
    if family_kind == "players":
        family = rng.choice(["league", "nation", "club"])
        ids = sorted(rng.sample(range(1, 5), 2))
        value = rng.randint(1, 3)
        return (
            _req(PLAYERS_KIND[family], op, value, ids=ids),
            check_players(ATTR[family], set(ids), op, value),
        )
    if family_kind == "distinct":
        family = rng.choice(["league", "nation", "club"])
        value = rng.randint(1, 4)
        return _req(DISTINCT_KIND[family], op, value), check_distinct(ATTR[family], op, value)
    if family_kind == "same":
        family = rng.choice(["league", "nation", "club"])
        op = rng.choice(["min", "max", "exact"])
        value = rng.randint(1, 4)
        return _req(SAME_KIND[family], op, value), check_same(ATTR[family], op, value)
    choice = rng.choice(["level", "rare", "tag"])
    value = rng.randint(1, 3)
    if choice == "level":
        levels = rng.sample(["bronze", "silver", "gold"], rng.randint(1, 2))
        return _req(K.LEVEL_PLAYERS, op, value, tags=levels), check_level(set(levels), op, value)
    if choice == "rare":
        return _req(K.RARE_PLAYERS, op, value), check_rare(op, value)
    tags = rng.sample(["TOTW", "SPECIAL"], rng.randint(1, 2))
    return _req(K.TAG_PLAYERS, op, value, tags=tags), check_tag(tags, op, value)


@pytest.mark.parametrize("family_kind", ["players", "distinct", "same", "attrs"])
@pytest.mark.parametrize("seed", range(6))
def test_requirements_match_bruteforce(seed, family_kind):
    rng = random.Random(1000 * seed + len(family_kind))
    cards, costs = _random_pool(rng, 8)
    slots = ["GK", "CB", "CM", "ST"]
    req, check = _random_case(rng, family_kind)
    expected = brute_force(cards, slots, costs, check)
    status, chosen, cost = _solve(cards, slots, costs, [req])
    if expected is None:
        assert status == "infeasible"
    else:
        assert status == "optimal"
        assert cost == expected
        assert check(chosen)


@pytest.mark.parametrize("seed", range(4))
def test_combined_bruteforce(seed):
    rng = random.Random(seed)
    cards, costs = _random_pool(rng, 8)
    slots = ["GK", "CB", "CM", "ST"]
    cases = [_random_case(rng, f) for f in ("players", "distinct", "same", "attrs")]
    expected = brute_force(cards, slots, costs, lambda ch: all(chk(ch) for _, chk in cases))
    status, chosen, cost = _solve(cards, slots, costs, [r for r, _ in cases])
    if expected is None:
        assert status == "infeasible"
    else:
        assert status == "optimal"
        assert cost == expected
        assert all(chk(chosen) for _, chk in cases)


# --- Caso realista ---


SLOTS_442 = ["GK", "LB", "CB", "CB", "RB", "LM", "CM", "CM", "RM", "ST", "ST"]


PRICE_BY_RATING = {
    78: 700, 79: 900, 80: 1200, 81: 1800, 82: 2600, 83: 4000, 84: 6000,
    85: 9000, 86: 13000, 87: 19000, 88: 27000, 89: 38000, 90: 52000,
}


def _realistic_pool(rng, size=80):
    outfield = ["LB", "CB", "RB", "LM", "CM", "RM", "ST"]
    specs = []
    for i in range(size):
        league = rng.randint(1, 5)
        if i < 8:
            positions = ["GK"]
        else:
            positions = rng.sample(outfield, rng.randint(1, 2))
        specs.append(
            {
                "rating": rng.randint(78, 90),
                "positions": positions,
                "league_id": league,
                "club_id": league * 10 + rng.randint(1, 4),
                "nation_id": rng.randint(1, 8),
                "rarity_tags": ["TOTW"] if rng.random() < 0.1 else [],
                "rare": rng.random() < 0.5,
            }
        )
    cards = _cards(specs)
    # Precio por escalón de media, como en el mercado.
    costs = [PRICE_BY_RATING[c.rating] for c in cards]
    return cards, costs


def test_combined_realistic():
    # Semilla fija; con otras semillas el óptimo se prueba en ~3–11 s (8 workers).
    rng = random.Random(4)
    cards, costs = _realistic_pool(rng)
    reqs = [
        _req(K.TEAM_RATING, "min", 84),
        _req(K.TEAM_CHEMISTRY, "min", 25),
        _req(K.TAG_PLAYERS, "min", 1, tags=["TOTW"]),
        _req(K.SAME_LEAGUE, "max", 5),
    ]
    status, chosen, _ = _solve(cards, SLOTS_442, costs, reqs, time_limit_s=10.0)
    assert status == "optimal"
    assert len(chosen) == 11
    assert all(slot in c.positions for c, slot in zip(chosen, SLOTS_442, strict=True))
    assert team_rating([c.rating for c in chosen]) >= 84
    assert team_chemistry(chosen) >= 25
    assert check_tag(["TOTW"], "min", 1)(chosen)
    assert check_same("league_id", "max", 5)(chosen)
