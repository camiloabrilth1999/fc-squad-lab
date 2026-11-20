from fcsl_api.sbc import formations
from fcsl_api.solver.models import Card
from fcsl_api.squad.builder import build_squad


def _card(i: int, pos: str, league: int, nation: int = 1, club: int = 1) -> Card:
    return Card(
        card_id=f"club:{i}",
        resource_id=i,
        asset_id=i,
        name=f"J{i}",
        rating=80,
        positions=[pos],
        league_id=league,
        nation_id=nation,
        club_id=club,
        rare=False,
        source="club",
    )


def _pool() -> tuple[list[Card], dict[str, float]]:
    slots = formations.slots_for("442")
    cards, meta, i = [], {}, 0
    for pos in slots:
        # el mejor de cada puesto es de la liga 1; el segundo, de la liga 2
        for league, m in ((1, 90.0), (2, 70.0)):
            i += 1
            cards.append(_card(i, pos, league, nation=league, club=league))
            meta[cards[-1].card_id] = m
    return cards, meta


def test_group_min_forces_players_from_a_league_even_if_worse() -> None:
    cards, meta = _pool()
    slots = formations.slots_for("442")
    free = build_squad(cards, meta, slots, chem_weight=0)
    assert free.status in ("optimal", "feasible")

    def in_league_2(r) -> int:
        return sum(1 for a in r.assignments if int(a.card_id.split(":")[1]) % 2 == 0)

    assert in_league_2(free) == 0  # sin restricción todo es de la liga 1 (meta mayor)

    forced = build_squad(cards, meta, slots, chem_weight=0, group_mins=[("league", 2, 3)])
    assert forced.status in ("optimal", "feasible")
    assert in_league_2(forced) == 3  # justo los exigidos: lo mínimo que cuesta meta
    assert forced.total_meta < free.total_meta


def test_group_min_is_infeasible_when_the_club_lacks_players() -> None:
    cards, meta = _pool()
    res = build_squad(cards, meta, formations.slots_for("442"), group_mins=[("nation", 2, 12)])
    assert res.status == "infeasible"
