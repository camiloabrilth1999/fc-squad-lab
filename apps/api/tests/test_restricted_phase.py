"""Fase restringida de `solve_model` (vecindarios por ventana de media)."""

import random

import pytest
from ortools.sat.python import cp_model

from fcsl_api.solver import cpsat
from fcsl_api.solver.chemistry import team_chemistry
from fcsl_api.solver.cpsat import build_base_model, solve_model
from fcsl_api.solver.models import (
    Objective,
    Requirement,
    RequirementKind,
    ValuationSettings,
)
from fcsl_api.solver.rating import team_rating
from fcsl_api.solver.requirements import apply_requirement
from fcsl_api.solver.valuation import card_cost, objective_terms

from .bruteforce import brute_force
from .fixtures import make_card

V = ValuationSettings()
SLOTS = ["CB", "CM", "ST"]
RATING = Requirement(kind=RequirementKind.TEAM_RATING, op="min", value=80)
CHEM = Requirement(kind=RequirementKind.TEAM_CHEMISTRY, op="min", value=3)


def _card(i, **spec):
    base = {"card_id": f"market:{i}", "resource_id": i, "asset_id": i, "name": f"J{i}"}
    base.update(spec)
    return make_card(**base)


def _random_cards(seed, n=9):
    rng = random.Random(seed)
    return [
        _card(
            i,
            rating=rng.randint(72, 90),
            positions=[rng.choice(SLOTS)],
            league_id=rng.randint(1, 2),
            nation_id=rng.randint(1, 2),
            club_id=rng.randint(1, 3),
            price=rng.randint(1, 50) * 100,
        )
        for i in range(1, n + 1)
    ]


def _model(cards, reqs, slots=SLOTS):
    costs = [card_cost(c, V) for c in cards]
    m = build_base_model(cards, slots, costs)
    for req in reqs:
        apply_requirement(m, req)
    return m, costs


def _force_restricted(monkeypatch):
    monkeypatch.setattr(cpsat, "RESTRICTED_MIN_CARDS", 1)
    monkeypatch.setattr(cpsat, "CHEAP_SUBSET_MIN_CARDS", 1)
    monkeypatch.setattr(cpsat, "CHEAP_SUBSET_CARDS", 3)


def _cost(cards, costs, assignments):
    by_id = {c.card_id: costs[i] for i, c in enumerate(cards)}
    return sum(by_id[a.card_id] for a in assignments)


def test_requirements_are_recorded():
    m, _ = _model(_random_cards(0), [RATING, CHEM])
    assert m.requirements == [RATING, CHEM]


def test_rating_windows_around_team_rating_target():
    cards = [_card(i, rating=r, positions=["ST"]) for i, r in enumerate(range(76, 93), start=1)]
    m, costs = _model(cards, [Requirement(kind=RequirementKind.TEAM_RATING, op="min", value=84)])
    hoods = cpsat._neighbourhoods(m, costs)
    ratings = [sorted(cards[c].rating for c in hood) for hood in hoods]
    assert ratings == [list(range(81, 87)), list(range(80, 88))]


def test_no_rating_target_uses_cheap_subset_only_for_large_pools(monkeypatch):
    cards = _random_cards(1)
    m, costs = _model(cards, [CHEM])
    assert cpsat._neighbourhoods(m, costs) == []
    _force_restricted(monkeypatch)
    assert [len(h) for h in cpsat._neighbourhoods(m, costs)] == [3]


@pytest.mark.parametrize("seed", range(6))
@pytest.mark.parametrize("reqs", [[RATING, CHEM], [CHEM]], ids=["window", "cheap"])
def test_restricted_phase_keeps_optimum(monkeypatch, seed, reqs):
    # Con la fase restringida forzada en pools pequeños, el óptimo coincide con la
    # fuerza bruta: los vecindarios solo aportan pistas y respaldo.
    _force_restricted(monkeypatch)
    cards = _random_cards(seed)
    m, costs = _model(cards, reqs)

    def check(chosen):
        ok = team_chemistry(chosen) >= 3
        if RATING in reqs:
            ok = ok and team_rating([c.rating for c in chosen]) >= 80
        return ok

    expected = brute_force(cards, SLOTS, costs, check)
    status, assignments, _ = solve_model(m, objective_terms(m, costs, Objective.CHEAPEST), 5.0)
    if expected is None:
        assert status == "infeasible"
    else:
        assert status == "optimal"
        assert _cost(cards, costs, assignments) == expected


def test_restricted_solution_is_returned_when_full_solve_finds_nothing(monkeypatch):
    _force_restricted(monkeypatch)
    cards = _random_cards(2)
    m, costs = _model(cards, [RATING, CHEM])
    real = cpsat._run_solver

    def full_solve_times_out(model, time_limit_s):
        if model is m.model:
            return cp_model.UNKNOWN, None, None
        return real(model, time_limit_s)

    monkeypatch.setattr(cpsat, "_run_solver", full_solve_times_out)
    status, assignments, _ = solve_model(m, objective_terms(m, costs, Objective.CHEAPEST), 5.0)
    assert status == "feasible"
    chosen = [c for c in cards if c.card_id in {a.card_id for a in assignments}]
    assert [a.slot_index for a in assignments] == [0, 1, 2]
    assert team_rating([c.rating for c in chosen]) >= 80
    assert team_chemistry(chosen) >= 3


def test_restricted_phase_respects_forced_cards(monkeypatch):
    # Una carta obligada fuera de la ventana de media: los vecindarios no la
    # contienen, pero el resultado final la incluye y sigue siendo el óptimo.
    _force_restricted(monkeypatch)
    cards = _random_cards(3, n=8) + [_card(99, rating=72, positions=["ST"], price=9000)]
    m, costs = _model(cards, [RATING, CHEM])
    m.model.add(m.used[len(cards) - 1] == 1)

    def check(chosen):
        return (
            any(c.card_id == "market:99" for c in chosen)
            and team_rating([c.rating for c in chosen]) >= 80
            and team_chemistry(chosen) >= 3
        )

    expected = brute_force(cards, SLOTS, costs, check)
    status, assignments, _ = solve_model(m, objective_terms(m, costs, Objective.CHEAPEST), 5.0)
    if expected is None:
        assert status == "infeasible"
    else:
        assert status == "optimal"
        assert "market:99" in {a.card_id for a in assignments}
        assert _cost(cards, costs, assignments) == expected


def _included_far_from_window(restricted_min_cards, monkeypatch):
    # ≥150 cartas: la fase restringida corre con los umbrales reales. La carta
    # incluida (media 60) queda muy fuera de las ventanas alrededor de 80.
    monkeypatch.setattr(cpsat, "RESTRICTED_MIN_CARDS", restricted_min_cards)
    rng = random.Random(7)
    slots = ["CB", "CB", "CM", "ST", "ST"]
    cards = [
        _card(
            i,
            rating=rng.randint(70, 90),
            positions=[rng.choice(slots)],
            price=rng.randint(1, 100) * 100,
        )
        for i in range(1, 161)
    ] + [_card(999, rating=60, positions=["ST"], price=50_000)]
    m, costs = _model(cards, [RATING], slots)
    cpsat.include_card(m, len(cards) - 1)
    status, assignments, _ = solve_model(m, objective_terms(m, costs, Objective.CHEAPEST), 10.0)
    return status, assignments, _cost(cards, costs, assignments)


def test_restricted_phase_keeps_included_cards(monkeypatch):
    found = []
    real = cpsat._restricted_phase

    def spy(m, coef, budget_s):
        result = real(m, coef, budget_s)
        found.append(result)
        return result

    monkeypatch.setattr(cpsat, "_restricted_phase", spy)
    status, assignments, cost = _included_far_from_window(cpsat.RESTRICTED_MIN_CARDS, monkeypatch)
    assert len(found) == 1 and found[0] is not None  # la fase encontró solución
    assert status == "optimal"
    assert "market:999" in {a.card_id for a in assignments}

    # Mismo óptimo que el modelo completo sin fase restringida.
    full_status, _, full_cost = _included_far_from_window(10**6, monkeypatch)
    assert full_status == "optimal"
    assert cost == full_cost
