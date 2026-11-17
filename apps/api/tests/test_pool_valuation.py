import random
import time

import pytest

from fcsl_api.solver import cpsat
from fcsl_api.solver.chemistry import team_chemistry
from fcsl_api.solver.cpsat import build_base_model, solve_model
from fcsl_api.solver.models import (
    Objective,
    Requirement,
    RequirementKind,
    ValuationSettings,
)
from fcsl_api.solver.pool import build_pool
from fcsl_api.solver.rating import team_rating
from fcsl_api.solver.requirements import apply_requirement
from fcsl_api.solver.valuation import BIG, card_cost, objective_terms

from .bruteforce import brute_force
from .fixtures import make_card
from .synthetic import FORMATION_433, market_cards

V = ValuationSettings()


def _card(i, **spec):
    base = {"card_id": f"market:{i}", "resource_id": i, "asset_id": i, "name": f"J{i}"}
    base.update(spec)
    return make_card(**base)


def _club(i, **spec):
    base = {"card_id": f"club:{i}", "source": "club"}
    base.update(spec)
    return _card(i, **base)


def _ids(cards):
    return sorted(c.card_id for c in cards)


# --- valoración ---------------------------------------------------------------


def test_cost_rules():
    assert card_cost(_card(1, price=1234), V) == 1234
    assert card_cost(_club(2, untradeable=True, price=5000), V) == 0
    assert card_cost(_club(3, price=1000), V) == 950
    assert card_cost(_club(4, price=None), V) == 0
    assert card_cost(_club(5, price=1000, duplicate=True), V) == 855
    assert card_cost(_club(6, price=1000, in_sbc_storage=True), V) == 855
    # Si aplican ambos descuentos se usa el mayor (no se acumulan).
    v = ValuationSettings(duplicate_discount=0.10, storage_discount=0.30)
    assert card_cost(_club(7, price=1000, duplicate=True, in_sbc_storage=True), v) == 665
    assert card_cost(_club(8, untradeable=True, duplicate=True, price=1000), V) == 0


def _single_slot_terms(cards, objective):
    costs = [card_cost(c, V) for c in cards]
    m = build_base_model(cards, ["CM"], costs)
    card_of = {u.index: card.card_id for u, card in zip(m.used, cards, strict=True)}
    return {card_of[var.index]: coef for coef, var in objective_terms(m, costs, objective)}


def test_objective_coefficients():
    cards = [
        _card(1, price=1000),
        _club(2, untradeable=True, price=500),
        _club(3, price=1000, duplicate=True),
        _club(4, price=1000),
    ]
    assert _single_slot_terms(cards, Objective.CHEAPEST) == {
        "market:1": 100_000,
        "club:2": -1,
        "club:3": 85_500 - 1,
        "club:4": 95_000,
    }
    assert _single_slot_terms(cards, Objective.FEWEST_BUYS) == {
        "market:1": BIG + 1000,
        "club:2": 0,
        "club:3": 855,
        "club:4": 950,
    }
    assert _single_slot_terms(cards, Objective.USE_CLUB) == {
        "market:1": 1000,
        "club:2": -BIG,
        "club:3": -BIG + 855,
        "club:4": 950,
    }


def test_objective_fewest_buys_prefers_club():
    # La propia transferible cuesta algo más que la de mercado.
    cards = [_card(1, price=1000), _club(2, asset_id=2, price=1100)]
    costs = [card_cost(c, V) for c in cards]

    def solve(objective):
        m = build_base_model(cards, ["CM"], costs)
        status, assignments, _ = solve_model(m, objective_terms(m, costs, objective), 5.0)
        assert status == "optimal"
        return [a.card_id for a in assignments]

    assert solve(Objective.FEWEST_BUYS) == ["club:2"]
    assert solve(Objective.CHEAPEST) == ["market:1"]


def test_cheapest_breaks_ties_towards_owned():
    # A igualdad de coste, el bonus decide a favor de la propia duplicada.
    cards = [_card(1, price=855), _club(2, price=1000, duplicate=True)]  # 855 == 855
    costs = [card_cost(c, V) for c in cards]
    assert costs[0] == costs[1]
    m = build_base_model(cards, ["CM"], costs)
    _, assignments, _ = solve_model(m, objective_terms(m, costs, Objective.CHEAPEST), 5.0)
    assert [a.card_id for a in assignments] == ["club:2"]


# --- pool y poda ----------------------------------------------------------------


def test_market_without_price_excluded():
    cards = [_card(1, price=None), _card(2, price=500)]
    assert _ids(build_pool(cards, "market", ["CM"], [], [], [])) == ["market:2"]


def test_pool_filters_by_source():
    cards = [_card(1), _club(2)]
    assert _ids(build_pool(cards, "club", ["CM"], [], [], [])) == ["club:2"]
    assert _ids(build_pool(cards, "market", ["CM"], [], [], [])) == ["market:1"]
    assert _ids(build_pool(cards, "both", ["CM"], [], [], [])) == ["club:2", "market:1"]


def test_pool_drops_excluded_unplayable_and_player_rating():
    cards = [
        _card(1, rating=80),
        _card(2, rating=80, positions=["ST"]),  # no juega en ningún hueco
        _card(3, rating=70),  # viola PLAYER_RATING
        _card(4, rating=82),
    ]
    reqs = [Requirement(kind=RequirementKind.PLAYER_RATING, op="min", value=75)]
    pool = build_pool(cards, "market", ["CM", "CM"], reqs, [], ["market:4"])
    assert _ids(pool) == ["market:1"]


def test_pruning_keeps_two_cheapest():
    # Grupo idéntico con 2 huecos donde puede jugar: sobran las más caras.
    cards = [_card(i, price=p) for i, p in enumerate([900, 300, 700, 500, 800], start=1)]
    pool = build_pool(cards, "market", ["CM", "CM"], [], [], [])
    assert _ids(pool) == ["market:2", "market:4"]


def test_pruning_groups_by_attributes():
    cards = [
        _card(1, price=100),
        _card(2, price=200),
        _card(3, price=300),
        _card(4, price=900, nation_id=9),  # otra nación (la mira un requisito)
        _card(5, price=900, positions=["CM", "ST"]),  # ST no es hueco: mismo grupo
        _card(6, price=900, rare=True),  # rara (la mira un requisito)
    ]
    reqs = [
        Requirement(kind=RequirementKind.NATION_PLAYERS, value=1, ids=[9]),
        Requirement(kind=RequirementKind.RARE_PLAYERS, value=1),
    ]
    pool = build_pool(cards, "market", ["CM", "CM"], reqs, [], [])
    assert _ids(pool) == ["market:1", "market:2", "market:4", "market:6"]


def test_pruning_ignores_attributes_no_requirement_uses():
    # Sin requisitos, nación y rareza no distinguen: sobran las caras.
    cards = [
        _card(1, price=100),
        _card(2, price=200),
        _card(4, price=900, nation_id=9),
        _card(6, price=900, rare=True),
    ]
    pool = build_pool(cards, "market", ["CM", "CM"], [], [], [])
    assert _ids(pool) == ["market:1", "market:2"]


def test_pruning_chemistry_keeps_link_attributes():
    cards = [
        _card(1, price=100),
        _card(2, price=200),
        _card(3, price=900, club_id=7),
        _card(4, price=900, league_id=7),
        _card(5, price=900, nation_id=7),
        _card(6, price=900, is_icon=True),
        _card(7, price=900),
    ]
    reqs = [Requirement(kind=RequirementKind.TEAM_CHEMISTRY, value=1)]
    pool = build_pool(cards, "market", ["CM", "CM"], reqs, [], [])
    assert _ids(pool) == [f"market:{i}" for i in range(1, 7)]


def test_pruning_by_rating_dominance():
    # Con media mínima, una carta mejor y más barata domina; con máxima, no.
    cards = [_card(1, rating=85, price=50), _card(2, rating=80, price=100)]
    team_min = [Requirement(kind=RequirementKind.TEAM_RATING, op="min", value=80)]
    team_max = [Requirement(kind=RequirementKind.TEAM_RATING, op="max", value=82)]
    assert _ids(build_pool(cards, "market", ["CM"], team_min, [], [])) == ["market:1"]
    assert _ids(build_pool(cards, "market", ["CM"], team_max, [], [])) == ["market:1", "market:2"]
    # Sin requisito de media, el rating no importa: la más barata basta.
    assert _ids(build_pool(cards[::-1], "market", ["CM"], [], [], [])) == ["market:1"]


def test_pruning_by_position_superset():
    # Las que juegan en CM y ST dominan a la de solo CM, pero hace falta que haya
    # n (= 2) dominadoras: una sola podría estar ocupando el hueco ST.
    flex = [_card(1, positions=["CM", "ST"], price=50), _card(2, positions=["CM", "ST"], price=60)]
    only_cm = _card(3, positions=["CM"], price=100)
    slots = ["CM", "ST"]
    assert _ids(build_pool([flex[0], only_cm], "market", slots, [], [], [])) == [
        "market:1",
        "market:3",
    ]
    assert _ids(build_pool([*flex, only_cm], "market", slots, [], [], [])) == [
        "market:1",
        "market:2",
    ]


def test_pruning_keeps_enough_for_every_eligible_slot():
    # 3 huecos CB y un requisito de 3 del mismo club: con solo 2 sería infactible.
    cards = [_card(i, positions=["CB"], price=100 * i) for i in range(1, 6)]
    reqs = [Requirement(kind=RequirementKind.SAME_CLUB, op="min", value=3)]
    pool = build_pool(cards, "market", ["CB", "CB", "CB"], reqs, [], [])
    assert _ids(pool) == ["market:1", "market:2", "market:3"]


def test_pruning_never_drops_club_or_included():
    cards = [_card(i, price=100 * i) for i in range(1, 6)] + [
        _club(10, price=5000),
        _club(11, untradeable=True),
    ]
    pool = build_pool(cards, "both", ["CM"], [], ["market:5"], [])
    assert _ids(pool) == ["club:10", "club:11", "market:1", "market:5"]


def test_pruning_accounts_for_shared_assets():
    # La barata comparte jugador (asset) con una propia: si se usa la propia, hace
    # falta la siguiente de mercado del grupo.
    cards = [
        _card(1, price=100, asset_id=50),
        _card(2, price=200),
        _card(3, price=300),
        _club(4, asset_id=50, positions=["ST"], untradeable=True),
    ]
    pool = build_pool(cards, "both", ["CM", "ST"], [], [], [])
    assert _ids(pool) == ["club:4", "market:1", "market:2"]


# --- rendimiento ------------------------------------------------------------------

LARGE_REQS = [
    Requirement(kind=RequirementKind.TEAM_RATING, op="min", value=84),
    Requirement(kind=RequirementKind.TEAM_CHEMISTRY, op="min", value=25),
]


def _solve_large(time_limit_s, whole_flow=True):
    """Poda + modelo + solve. Con `whole_flow`, todo dentro de `time_limit_s` de
    reloj; si no, `time_limit_s` es el límite que recibe `solve_model`."""
    cards = market_cards(5000, seed=27)
    start = time.perf_counter()
    pool = build_pool(cards, "market", FORMATION_433, LARGE_REQS, [], [])
    costs = [card_cost(c, V) for c in pool]
    m = build_base_model(pool, FORMATION_433, costs)
    for req in LARGE_REQS:
        apply_requirement(m, req)
    # Margen para construir la respuesta tras el solve (el solve agota su límite).
    remaining = time_limit_s
    if whole_flow:
        remaining = max(0.0, time_limit_s - (time.perf_counter() - start) - 0.5)
    status, assignments, _ = solve_model(
        m, objective_terms(m, costs, Objective.CHEAPEST), remaining
    )
    return status, assignments, time.perf_counter() - start


def test_large_pool_under_10s():
    status, assignments, elapsed = _solve_large(10.0)
    assert status in ("optimal", "feasible")
    assert len(assignments) == 11
    assert elapsed < 10.0


def test_timeout_returns_feasible_or_unknown():
    status, _, _ = _solve_large(0.05, whole_flow=False)
    assert status in ("feasible", "unknown")


@pytest.mark.parametrize("seed", range(4))
def test_warm_start_keeps_optimum(monkeypatch, seed):
    # Forzando el arranque en caliente (subconjunto mínimo) en pools pequeños, el
    # óptimo coincide con la fuerza bruta: la pista no cambia el resultado.
    rng = random.Random(seed)
    cards = [
        _card(
            i,
            rating=rng.randint(70, 90),
            positions=[rng.choice(["CB", "CM", "ST"])],
            league_id=rng.randint(1, 2),
            nation_id=rng.randint(1, 2),
            club_id=rng.randint(1, 3),
            price=rng.randint(1, 50) * 100,
        )
        for i in range(1, 9)
    ]
    slots = ["CB", "CM", "ST"]
    reqs = [
        Requirement(kind=RequirementKind.TEAM_RATING, op="min", value=80),
        Requirement(kind=RequirementKind.TEAM_CHEMISTRY, op="min", value=3),
    ]
    costs = [card_cost(c, V) for c in cards]

    def check(chosen):
        return team_rating([c.rating for c in chosen]) >= 80 and team_chemistry(chosen) >= 3

    expected = brute_force(cards, slots, costs, check)
    monkeypatch.setattr(cpsat, "WARM_START_MIN_CARDS", 1)
    monkeypatch.setattr(cpsat, "WARM_START_CARDS", 3)
    m = build_base_model(cards, slots, costs)
    for req in reqs:
        apply_requirement(m, req)
    status, assignments, _ = solve_model(m, objective_terms(m, costs, Objective.CHEAPEST), 5.0)
    if expected is None:
        assert status == "infeasible"
    else:
        assert status == "optimal"
        by_id = {c.card_id: costs[i] for i, c in enumerate(cards)}
        assert sum(by_id[a.card_id] for a in assignments) == expected


@pytest.mark.parametrize("objective", list(Objective))
def test_objective_terms_one_per_card(objective):
    cards = [_card(1), _card(2)]
    costs = [card_cost(c, V) for c in cards]
    m = build_base_model(cards, ["CM"], costs)
    terms = objective_terms(m, costs, objective)
    assert [var.index for _, var in terms] == [u.index for u in m.used]
