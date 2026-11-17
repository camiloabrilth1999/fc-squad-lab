from fcsl_api.solver import service
from fcsl_api.solver.chemistry import player_chemistry, team_chemistry
from fcsl_api.solver.models import Requirement, RequirementKind, SolveRequest
from fcsl_api.solver.rating import team_rating

from .fixtures import make_card


def _cards(specs):
    return [
        make_card(
            card_id=f"market:{i}", resource_id=i, asset_id=i, name=f"J{i}", **spec
        )
        for i, spec in enumerate(specs, start=1)
    ]


def test_service_infeasible_message():
    req = SolveRequest(slots=["GK", "CM"], cards=_cards([{"positions": ["CM"]}] * 3))
    sol = service.solve(req)
    assert sol.status == "infeasible"
    assert "GK" in sol.message
    assert sol.solve_time_s == 0.0


def test_service_include_missing():
    req = SolveRequest(
        slots=["CM"],
        cards=_cards([{"positions": ["CM"]}] * 2),
        include_card_ids=["market:99"],
    )
    sol = service.solve(req)
    assert sol.status == "infeasible"
    assert sol.message == "Jugador incluido no disponible: market:99"


def test_service_metrics_consistent():
    cards = _cards(
        [
            {"positions": ["CM"], "rating": 80, "price": 1000},
            {"positions": ["CM"], "rating": 82, "price": 2000, "league_id": 2},
            {"positions": ["ST"], "rating": 78, "price": 900},
            {"positions": ["ST"], "rating": 85, "price": 5000},
        ]
    )
    req = SolveRequest(
        slots=["CM", "CM", "ST"],
        cards=cards,
        requirements=[
            Requirement(kind=RequirementKind.TEAM_RATING, op="min", value=80)
        ],
    )
    sol = service.solve(req)
    assert sol.status == "optimal"
    by_id = {c.card_id: c for c in cards}
    chosen = [by_id[a.card_id] for a in sol.assignments]
    assert sol.team_rating == team_rating([c.rating for c in chosen]) >= 80
    assert sol.team_chemistry == team_chemistry(chosen)
    assert sol.player_chemistry == player_chemistry(chosen)
    assert sol.cost == sum(service.card_cost(c, req.valuation) for c in chosen)


def test_service_include_forced():
    cards = _cards(
        [{"positions": ["CM"], "price": 100}, {"positions": ["CM"], "price": 9000}]
    )
    req = SolveRequest(slots=["CM"], cards=cards, include_card_ids=["market:2"])
    sol = service.solve(req)
    assert [a.card_id for a in sol.assignments] == ["market:2"]


def test_solve_all_pools_order_and_skip():
    market_only = SolveRequest(slots=["CM"], cards=_cards([{"positions": ["CM"]}]))
    assert [s.pool for s in service.solve_all_pools(market_only)] == ["market"]

    club = make_card(
        card_id="club:1", resource_id=5, asset_id=5, source="club", positions=["CM"]
    )
    mixed = SolveRequest(slots=["CM"], cards=[club, *_cards([{"positions": ["CM"]}])])
    assert [s.pool for s in service.solve_all_pools(mixed)] == [
        "club",
        "both",
        "market",
    ]
