import random

from fcsl_api.solver.cpsat import build_base_model, eligibility_problem, solve_model

from .bruteforce import brute_force
from .fixtures import make_card


def _cards(specs):
    return [
        make_card(card_id=f"market:{i}", resource_id=i, asset_id=i, name=f"J{i}", **spec)
        for i, spec in enumerate(specs, start=1)
    ]


def _solve(cards, slots, costs, time_limit_s=5.0):
    m = build_base_model(cards, slots, costs)
    terms = [(costs[c], m.used[c]) for c in range(len(cards))]
    return solve_model(m, terms, time_limit_s)


def test_fills_every_slot():
    cards = _cards([{"positions": ["CM"]}] * 3)
    status, assignments, _ = _solve(cards, ["CM", "CM"], [10, 20, 30])
    assert status == "optimal"
    assert [a.slot_index for a in assignments] == [0, 1]
    assert len({a.card_id for a in assignments}) == 2


def test_allows_out_of_position():
    # Como en EA, una carta puede ocupar un hueco fuera de su posición: el solver
    # prefiere dos CM baratas (una en el hueco GK, fuera de posición) antes que
    # pagar por el GK caro. La posición no limita la elegibilidad.
    cards = _cards([{"positions": ["CM"]}, {"positions": ["GK"]}, {"positions": ["CM"]}])
    status, assignments, _ = _solve(cards, ["GK", "CM"], [1, 500, 1])
    assert status == "optimal"
    assert {a.card_id for a in assignments} == {"market:1", "market:3"}
    assert all(a.card_id != "market:2" for a in assignments)  # no se usa el GK caro


def test_picks_cheapest():
    cards = _cards([{"positions": ["ST"]}] * 3)
    status, assignments, _ = _solve(cards, ["ST"], [300, 100, 200])
    assert status == "optimal"
    assert assignments[0].card_id == "market:2"


def test_never_same_asset():
    cards = [
        make_card(card_id="market:1", asset_id=7, positions=["ST"]),
        make_card(card_id="club:2", asset_id=7, positions=["ST"]),
        make_card(card_id="market:3", asset_id=9, positions=["ST"]),
    ]
    status, assignments, _ = _solve(cards, ["ST", "ST"], [1, 1, 1000])
    assert status == "optimal"
    ids = {a.card_id for a in assignments}
    assert "market:3" in ids
    assert len(ids & {"market:1", "club:2"}) == 1


def test_position_never_makes_it_infeasible():
    # Antes un hueco sin cartas de esa posición era infactible; ahora cualquier
    # carta puede cubrirlo (fuera de posición), así que hay solución.
    cards = _cards([{"positions": ["CM"]}, {"positions": ["CB"]}])
    assert eligibility_problem(cards, ["CM", "ST"]) is None
    assert eligibility_problem(cards, ["CM", "CB"]) is None
    status, assignments, _ = _solve(cards, ["CM", "ST"], [1, 1])
    assert status == "optimal"
    assert len(assignments) == 2


def test_not_enough_distinct_players():
    cards = [
        make_card(card_id="a", asset_id=5, positions=["CM"]),
        make_card(card_id="b", asset_id=5, positions=["CM"]),
    ]
    msg = eligibility_problem(cards, ["CM", "CM"])
    assert msg == "No hay suficientes jugadores distintos para 2 huecos"


def test_sum_rating_domain():
    cards = _cards([{"positions": ["CM"], "rating": r} for r in (80, 70, 90)])
    m = build_base_model(cards, ["CM", "CM"], [1, 1, 1])
    # `.proto` (propiedad), no `.Proto()`: en ortools 9.15 el método deprecado corrompe
    # el CpModelProto y el proceso hace segfault al liberarlo.
    assert list(m.sum_rating.proto.domain) == [0, 198]


def test_matches_bruteforce():
    rng = random.Random(42)
    pool_positions = ["ST", "CM", "CB"]
    slots = ["ST", "CM", "CB"]
    for _ in range(5):
        n = rng.randint(6, 8)
        specs = []
        for _i in range(n):
            pos = rng.sample(pool_positions, rng.randint(1, 2))
            specs.append({"positions": pos, "rating": rng.randint(60, 90)})
        cards = _cards(specs)
        for i in rng.sample(range(n), 2):  # fuerza duplicados de asset_id
            cards[i] = cards[i].model_copy(update={"asset_id": 999})
        costs = [rng.randint(1, 100) for _ in range(n)]
        expected = brute_force(cards, slots, costs, lambda chosen, slots: True)
        status, assignments, _ = _solve(cards, slots, costs)
        if expected is None:
            assert status == "infeasible"
        else:
            assert status == "optimal"
            by_id = {c.card_id: costs[i] for i, c in enumerate(cards)}
            assert sum(by_id[a.card_id] for a in assignments) == expected
