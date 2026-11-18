import random

import pytest

from fcsl_api.solver.cpsat import build_base_model, solve_model
from fcsl_api.solver.models import Requirement, RequirementKind
from fcsl_api.solver.rating import team_rating
from fcsl_api.solver.requirements import apply_requirement

from .bruteforce import brute_force
from .fixtures import make_card


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


def _team(op, value):
    return Requirement(kind=RequirementKind.TEAM_RATING, op=op, value=value)


def test_team_rating_min():
    ratings = [70, 72, 75, 78, 80, 83, 85]
    cards = _cards([{"rating": r, "positions": ["CM"]} for r in ratings])
    costs = [r * 10 for r in ratings]
    status, chosen, _ = _solve(cards, ["CM"] * 4, costs, [_team("min", 80)])
    assert status == "optimal"
    assert len(chosen) == 4
    assert team_rating([c.rating for c in chosen]) >= 80


def test_team_rating_uses_excess():
    # Media simple de [90, 77, 77] = 81.33 → 81, pero con el exceso:
    # S=244, e=90-81.33=8.67 → (244+8.67)/3 = 84.2 → 84. Objetivo 84:
    # sin el exceso habría que poner tres cartas caras de 84.
    cards = _cards(
        [{"rating": 90, "positions": ["CM"]}]
        + [{"rating": 77, "positions": ["CM"]}] * 2
        + [{"rating": 84, "positions": ["CM"]}] * 3
    )
    costs = [500, 10, 10, 400, 400, 400]
    assert sum([90, 77, 77]) // 3 < 84  # la media simple no llega
    assert team_rating([90, 77, 77]) >= 84  # con exceso sí
    status, chosen, cost = _solve(cards, ["CM"] * 3, costs, [_team("min", 84)])
    assert status == "optimal"
    assert sorted(c.rating for c in chosen) == [77, 77, 90]
    assert cost == 520  # vs. 3×400 = 1200 subiendo a todos


def test_team_rating_exact():
    ratings = [60, 70, 75, 80, 85, 90, 95]
    cards = _cards([{"rating": r, "positions": ["CM"]} for r in ratings])
    # Las caras son baratas: sin `exact` el solver se pasaría del objetivo.
    costs = [100 - r for r in ratings]
    status, chosen, _ = _solve(cards, ["CM"] * 3, costs, [_team("exact", 78)])
    assert status == "optimal"
    assert team_rating([c.rating for c in chosen]) == 78


def test_team_rating_max():
    ratings = [60, 70, 75, 80, 85, 90, 95]
    cards = _cards([{"rating": r, "positions": ["CM"]} for r in ratings])
    costs = [100 - r for r in ratings]
    status, chosen, _ = _solve(cards, ["CM"] * 3, costs, [_team("max", 75)])
    assert status == "optimal"
    assert team_rating([c.rating for c in chosen]) <= 75


def test_team_rating_infeasible():
    cards = _cards([{"rating": 70, "positions": ["CM"]}] * 3)
    status, chosen, _ = _solve(cards, ["CM"] * 2, [1, 1, 1], [_team("min", 71)])
    assert status == "infeasible"
    assert chosen == []


def test_two_team_rating_requirements_share_counts():
    ratings = [60, 70, 75, 80, 85, 90, 95]
    cards = _cards([{"rating": r, "positions": ["CM"]} for r in ratings])
    costs = [100 - r for r in ratings]
    m = build_base_model(cards, ["CM"] * 3, costs)
    apply_requirement(m, _team("min", 76))
    first = m.rating_count
    shared = dict(first)
    apply_requirement(m, _team("max", 77))
    assert m.rating_count is first
    # Los conteos por rating se crean una vez y los comparten ambos requisitos.
    assert all(m.rating_count[r] is var for r, var in shared.items())
    terms = [(costs[c], m.used[c]) for c in range(len(cards))]
    status, assignments, _ = solve_model(m, terms, 5.0)
    assert status == "optimal"
    ids = {a.card_id for a in assignments}
    assert 76 <= team_rating([c.rating for c in cards if c.card_id in ids]) <= 77


@pytest.mark.parametrize(
    ("op", "value", "ok"),
    [
        ("min", 80, lambda r: r >= 80),
        ("max", 70, lambda r: r <= 70),
        ("exact", 75, lambda r: r == 75),
    ],
)
def test_player_rating_bounds(op, value, ok):
    ratings = [65, 70, 75, 80, 85, 90]
    cards = _cards([{"rating": r, "positions": ["CM"]} for r in ratings])
    costs = [1, 2, 3, 4, 5, 6] if op != "max" else [6, 5, 4, 3, 2, 1]
    req = Requirement(kind=RequirementKind.PLAYER_RATING, op=op, value=value)
    slots = ["CM"] if op == "exact" else ["CM", "CM"]
    status, chosen, _ = _solve(cards, slots, costs, [req])
    assert status == "optimal"
    assert len(chosen) == len(slots)
    assert all(ok(c.rating) for c in chosen)


def _random_pool(rng, size):
    positions = ["GK", "CB", "CM", "ST"]
    specs = []
    for _ in range(size):
        rating = rng.randint(60, 92)
        specs.append({"rating": rating, "positions": rng.sample(positions, rng.randint(1, 2))})
    cards = _cards(specs)
    # Coste correlacionado con la media (con ruido) para que el objetivo importe.
    costs = [max(1, (c.rating - 55) ** 2 + rng.randint(-50, 50)) for c in cards]
    return cards, costs


# La valoración no depende de la posición; `slots` se acepta por la firma de
# brute_force (chosen, slots) pero se ignora.
CHECKS = {
    "min": lambda t: lambda chosen, slots=None: team_rating([c.rating for c in chosen]) >= t,
    "max": lambda t: lambda chosen, slots=None: team_rating([c.rating for c in chosen]) <= t,
    "exact": lambda t: lambda chosen, slots=None: team_rating([c.rating for c in chosen]) == t,
}


@pytest.mark.parametrize("op", ["min", "max", "exact"])
@pytest.mark.parametrize("seed", range(5))
def test_rating_matches_bruteforce(seed, op):
    rng = random.Random(seed)
    cards, costs = _random_pool(rng, 8)
    slots = ["GK", "CB", "CM", "ST"]
    target = rng.randint(70, 84)
    expected = brute_force(cards, slots, costs, CHECKS[op](target))
    status, chosen, cost = _solve(cards, slots, costs, [_team(op, target)])
    if expected is None:
        assert status == "infeasible"
    else:
        assert status == "optimal"
        assert cost == expected
        assert CHECKS[op](target)(chosen)
