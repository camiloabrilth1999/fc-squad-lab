import random

import pytest
from ortools.sat.python import cp_model

from fcsl_api.solver.chemistry import (
    HERO_LEAGUE_WEIGHT,
    ICON_NATION_WEIGHT,
    LEAGUE_THRESHOLDS,
    MAX_PLAYER_CHEM,
    NATION_THRESHOLDS,
    player_chemistry,
    team_chemistry,
)
from fcsl_api.solver.cpsat import add_chemistry, build_base_model, solve_model
from fcsl_api.solver.models import Requirement, RequirementKind
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
    return Requirement(kind=RequirementKind.TEAM_CHEMISTRY, op=op, value=value)


def _player(value, op="min"):
    return Requirement(kind=RequirementKind.PLAYER_CHEMISTRY, op=op, value=value)


def _distinct(i, **spec):
    """Carta sin vínculos con nadie (club/liga/nación únicos) salvo lo que se pise."""
    base = {"club_id": 100 + i, "league_id": 100 + i, "nation_id": 100 + i}
    base.update(spec)
    return base


def test_team_chem_min():
    # 3 del mismo club/liga/nación (caros) frente a 4 sueltos (baratos).
    specs = [{"club_id": 1, "league_id": 1, "nation_id": 1}] * 3 + [_distinct(i) for i in range(4)]
    cards = _cards(specs)
    costs = [50, 50, 50, 1, 1, 1, 1]
    status, chosen, _ = _solve(cards, ["CM"] * 3, costs, [_team("min", 7)])
    assert status == "optimal"
    assert team_chemistry(chosen) >= 7


@pytest.mark.parametrize("op", ["max", "exact"])
def test_team_chem_max_and_exact(op):
    # Los vinculados son baratos: sin la cota el solver tomaría química 9.
    specs = [{"club_id": 1, "league_id": 1, "nation_id": 1}] * 3 + [_distinct(i) for i in range(4)]
    cards = _cards(specs)
    costs = [1, 1, 1, 50, 50, 50, 50]
    status, chosen, _ = _solve(cards, ["CM"] * 3, costs, [_team(op, 4)])
    assert status == "optimal"
    chem = team_chemistry(chosen)
    assert chem == 4 if op == "exact" else chem <= 4


def test_team_chem_infeasible():
    cards = _cards([_distinct(i) for i in range(4)])
    status, chosen, _ = _solve(cards, ["CM"] * 3, [1, 1, 1, 1], [_team("min", 1)])
    assert status == "infeasible"
    assert chosen == []


def test_player_chem_min():
    # Pareja club+nación (2 cada uno) cara; sueltos baratos con 0.
    specs = [{"club_id": 1, "league_id": 1, "nation_id": 1}] * 2 + [_distinct(i) for i in range(3)]
    cards = _cards(specs)
    status, chosen, _ = _solve(cards, ["CM"] * 2, [40, 40, 1, 1, 1], [_player(2)])
    assert status == "optimal"
    assert all(v >= 2 for v in player_chemistry(chosen).values())


def test_player_chem_rejects_other_ops():
    cards = _cards([{"positions": ["CM"]}])
    m = build_base_model(cards, ["CM"], [1])
    for op in ("max", "exact"):
        with pytest.raises(ValueError, match="PLAYER_CHEMISTRY"):
            apply_requirement(m, _player(1, op=op))


def test_icon_counts_double():
    # 3 normales de la nación 7 + icono de la nación 7 → 3 + peso ≥ 5 → 2 puntos.
    # Con un cuarto normal (barato) solo llegan a 4 → 1 punto: no cumple min 2.
    assert 3 + 1 < NATION_THRESHOLDS[1] <= 3 + ICON_NATION_WEIGHT
    normals = [_distinct(i, nation_id=7) for i in range(3)]
    control = _distinct(3, nation_id=7)
    icon = _distinct(4, nation_id=7, is_icon=True)
    cards = _cards([*normals, control, icon])
    costs = [1, 1, 1, 1, 100]
    status, chosen, _ = _solve(cards, ["CM"] * 4, costs, [_player(2)])
    assert status == "optimal"
    assert any(c.is_icon for c in chosen)
    assert all(v >= 2 for v in player_chemistry(chosen).values())


def test_hero_counts_double_in_league():
    assert 3 + 1 < LEAGUE_THRESHOLDS[1] <= 3 + HERO_LEAGUE_WEIGHT
    normals = [_distinct(i, league_id=7) for i in range(3)]
    control = _distinct(3, league_id=7)
    hero = _distinct(4, league_id=7, is_hero=True)
    cards = _cards([*normals, control, hero])
    costs = [1, 1, 1, 1, 100]
    status, chosen, _ = _solve(cards, ["CM"] * 4, costs, [_player(2)])
    assert status == "optimal"
    assert any(c.is_hero for c in chosen)
    assert all(v >= 2 for v in player_chemistry(chosen).values())


def test_add_chemistry_is_cached():
    cards = _cards([{"positions": ["CM"]}] * 3)
    m = build_base_model(cards, ["CM"] * 2, [1, 1, 1])
    chem = add_chemistry(m)
    assert m.chem is chem
    assert add_chemistry(m) is chem
    apply_requirement(m, _team("min", 1))
    apply_requirement(m, _player(1))
    assert m.chem is chem
    assert sorted(chem) == [0, 1, 2]


class _Collector(cp_model.CpSolverSolutionCallback):
    """Por cada solución, compara la química del modelo con la función pura."""

    def __init__(self, m, chem):
        super().__init__()
        self._m = m
        self._chem = chem
        self.solutions = 0
        self.mismatches: list[tuple[dict, dict]] = []

    def on_solution_callback(self):
        self.solutions += 1
        used = [c for c in range(len(self._m.cards)) if self.value(self._m.used[c])]
        expected = player_chemistry([self._m.cards[c] for c in used])
        model_chem = {self._m.cards[c].card_id: self.value(v) for c, v in self._chem.items()}
        got = {cid: v for cid, v in model_chem.items() if cid in expected}
        unused_nonzero = {cid: v for cid, v in model_chem.items() if cid not in expected and v}
        if got != expected or unused_nonzero:
            self.mismatches.append((expected, model_chem))


def _enumerate_and_compare(cards, slots):
    m = build_base_model(cards, slots, [1] * len(cards))
    chem = add_chemistry(m)
    collector = _Collector(m, chem)
    solver = cp_model.CpSolver()
    solver.parameters.enumerate_all_solutions = True
    solver.parameters.num_workers = 1
    status = solver.solve(m.model, collector)
    assert status == cp_model.OPTIMAL
    assert collector.solutions > 0
    assert collector.mismatches == []
    return collector.solutions


def _random_chem_pool(rng, size, specials=True):
    specs = []
    for _ in range(size):
        kind = rng.random() if specials else 1.0
        specs.append(
            {
                "rating": rng.randint(60, 90),
                "positions": ["CM"],
                "club_id": rng.randint(1, 3),
                "league_id": rng.randint(1, 2),
                "nation_id": rng.randint(1, 3),
                "is_icon": kind < 0.15,
                "is_hero": 0.15 <= kind < 0.3,
            }
        )
    return _cards(specs)


@pytest.mark.parametrize("seed", range(5))
def test_model_chem_equals_pure(seed):
    rng = random.Random(seed)
    cards = _random_chem_pool(rng, 8)
    _enumerate_and_compare(cards, ["CM"] * 5)


def test_model_chem_pins_icon_and_hero_weights():
    # Cubre lo que Task 5 dejó abierto: el icono pesa 1 en club y liga, el héroe
    # 1 en club y nación. Cada grupo tiene 4 miembros (1 especial + 3 normales):
    # con peso 1 suma 4, con peso 2 sumaría 5 y cruzaría el umbral siguiente;
    # con peso 0 los subconjuntos pequeños no llegarían al primero.
    icon = {"is_icon": True}
    hero = {"is_hero": True}
    cards = _cards(
        [
            {"club_id": 1, "league_id": 1, "nation_id": 1, **icon},
            {"club_id": 1, "league_id": 1, "nation_id": 2},
            {"club_id": 1, "league_id": 1, "nation_id": 2},
            {"club_id": 1, "league_id": 2, "nation_id": 2},
            {"club_id": 2, "league_id": 3, "nation_id": 2, **hero},
            {"club_id": 2, "league_id": 3, "nation_id": 3},
            {"club_id": 2, "league_id": 1, "nation_id": 3},
            {"club_id": 2, "league_id": 3, "nation_id": 3},
        ]
    )
    assert _enumerate_and_compare(cards, ["CM"] * 6) > 0


def test_model_chem_unused_is_zero():
    cards = _cards([{"club_id": 1, "league_id": 1, "nation_id": 1}] * 4)
    _enumerate_and_compare(cards, ["CM"] * 2)


def _chem_check(team_min=None, player_min=None):
    def check(chosen):
        if team_min is not None and team_chemistry(chosen) < team_min:
            return False
        return player_min is None or min(player_chemistry(chosen).values()) >= player_min

    return check


@pytest.mark.parametrize("seed", range(6))
def test_chem_matches_bruteforce(seed):
    rng = random.Random(100 + seed)
    positions = ["GK", "CB", "CM", "ST"]
    cards = _random_chem_pool(rng, 8)
    cards = [
        c.model_copy(update={"positions": rng.sample(positions, rng.randint(1, 3))}) for c in cards
    ]
    slots = ["GK", "CB", "CM", "ST"]
    costs = [rng.randint(1, 100) for _ in cards]
    team_min = rng.randint(4, 4 * MAX_PLAYER_CHEM)
    player_min = rng.choice([None, 1, 2])
    reqs = [_team("min", team_min)]
    if player_min is not None:
        reqs.append(_player(player_min))
    check = _chem_check(team_min, player_min)
    expected = brute_force(cards, slots, costs, check)
    status, chosen, cost = _solve(cards, slots, costs, reqs)
    if expected is None:
        assert status == "infeasible"
    else:
        assert status == "optimal"
        assert cost == expected
        assert check(chosen)
