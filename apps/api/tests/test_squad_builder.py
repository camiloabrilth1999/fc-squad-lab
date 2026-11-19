from fcsl_api.solver.chemistry import team_chemistry
from fcsl_api.squad.builder import build_squad
from tests.fixtures import make_card

SLOTS = ["GK", "CB", "ST"]


def _c(i: int, pos: str, **kw):
    return make_card(card_id=f"club:{i}", resource_id=i, asset_id=i, positions=[pos], **kw)


def test_picks_highest_meta_per_slot():
    cards = [_c(1, "GK"), _c(2, "CB"), _c(3, "CB"), _c(4, "ST")]
    meta = {"club:1": 80.0, "club:2": 70.0, "club:3": 90.0, "club:4": 85.0}
    r = build_squad(cards, meta, SLOTS, chem_weight=0)
    assert r.status in ("optimal", "feasible")
    assert {a.slot_index: a.card_id for a in r.assignments} == {
        0: "club:1",
        1: "club:3",
        2: "club:4",
    }
    assert r.total_meta == 255.0


def test_chemistry_can_beat_slightly_higher_meta():
    # CB 3 tiene un poco más de meta pero ninguna química con el resto (otra liga/nación/club)
    shared = {"league_id": 5, "nation_id": 5, "club_id": 5}
    cards = [
        _c(1, "GK", **shared),
        _c(2, "CB", **shared),
        _c(3, "CB", league_id=9, nation_id=9, club_id=9),
        _c(4, "ST", **shared),
    ]
    meta = {"club:1": 80.0, "club:2": 80.0, "club:3": 81.0, "club:4": 80.0}
    r = build_squad(cards, meta, SLOTS, chem_weight=2.0)
    assert [a.card_id for a in r.assignments if a.slot_index == 1] == ["club:2"]
    chosen = [next(c for c in cards if c.card_id == a.card_id) for a in r.assignments]
    assert r.team_chemistry == team_chemistry(chosen, SLOTS)


def test_min_chemistry_is_enforced():
    shared = {"league_id": 5, "nation_id": 5, "club_id": 5}
    cards = [
        _c(1, "GK", **shared),
        _c(2, "CB", **shared),
        _c(3, "CB", league_id=9, nation_id=9, club_id=9),
        _c(4, "ST", **shared),
    ]
    meta = {"club:1": 80.0, "club:2": 50.0, "club:3": 99.0, "club:4": 80.0}
    r = build_squad(cards, meta, SLOTS, chem_weight=0, min_chemistry=9)
    assert r.team_chemistry >= 9
    assert [a.card_id for a in r.assignments if a.slot_index == 1] == ["club:2"]


def test_infeasible_when_no_card_for_a_slot():
    cards = [_c(1, "GK"), _c(2, "CB")]  # nadie juega de ST
    r = build_squad(cards, {"club:1": 80.0, "club:2": 80.0}, SLOTS)
    assert r.status == "infeasible" and r.assignments == []


def test_excluded_cards_are_not_used():
    cards = [_c(1, "GK"), _c(2, "CB"), _c(3, "CB"), _c(4, "ST")]
    meta = {"club:1": 80.0, "club:2": 70.0, "club:3": 90.0, "club:4": 85.0}
    r = build_squad(cards, meta, SLOTS, chem_weight=0, exclude_card_ids=["club:3"])
    assert [a.card_id for a in r.assignments if a.slot_index == 1] == ["club:2"]


def test_out_of_position_allowed_picks_better_card_there():
    # el único ST natural es flojo; el CB-2 (meta alto) puede jugar de ST fuera de posición
    cards = [_c(1, "GK"), _c(2, "CB"), _c(3, "CB"), _c(4, "ST")]
    meta = {"club:1": 80.0, "club:2": 70.0, "club:3": 95.0, "club:4": 60.0}
    allowed = {"club:1": {"GK"}, "club:2": {"CB"}, "club:3": {"CB", "ST"}, "club:4": {"ST"}}
    r = build_squad(cards, meta, SLOTS, chem_weight=0, allowed=allowed)
    assert {a.slot_index: a.card_id for a in r.assignments} == {
        0: "club:1",
        1: "club:2",
        2: "club:3",
    }
    assert r.out_of_position == ["club:3"]


def test_max_out_of_position_zero_forbids_it():
    cards = [_c(1, "GK"), _c(2, "CB"), _c(3, "CB"), _c(4, "ST")]
    meta = {"club:1": 80.0, "club:2": 70.0, "club:3": 95.0, "club:4": 60.0}
    allowed = {"club:1": {"GK"}, "club:2": {"CB"}, "club:3": {"CB", "ST"}, "club:4": {"ST"}}
    r = build_squad(cards, meta, SLOTS, chem_weight=0, allowed=allowed, max_out_of_position=0)
    assert [a.card_id for a in r.assignments if a.slot_index == 2] == ["club:4"]
    assert r.out_of_position == []


def test_out_of_position_card_has_zero_chemistry():
    shared = {"league_id": 5, "nation_id": 5, "club_id": 5}
    cards = [
        _c(1, "GK", **shared),
        _c(2, "CB", **shared),
        _c(3, "CB", **shared),
        _c(4, "ST", **shared),
    ]
    meta = {"club:1": 80.0, "club:2": 70.0, "club:3": 95.0, "club:4": 60.0}
    allowed = {"club:1": {"GK"}, "club:2": {"CB"}, "club:3": {"CB", "ST"}, "club:4": {"ST"}}
    r = build_squad(cards, meta, SLOTS, chem_weight=0, allowed=allowed)
    assert r.player_chemistry["club:3"] == 0  # fuera de posición: sin química


def test_meta_can_depend_on_position():
    cards = [_c(1, "GK"), _c(2, "CB"), _c(3, "CB"), _c(4, "ST")]
    meta = {
        "club:1": 80.0,
        "club:2": 70.0,
        "club:3": {"CB": 60.0, "ST": 90.0},  # vale más de delantero que de central
        "club:4": 60.0,
    }
    allowed = {"club:1": {"GK"}, "club:2": {"CB"}, "club:3": {"CB", "ST"}, "club:4": {"ST"}}
    r = build_squad(cards, meta, SLOTS, chem_weight=0, allowed=allowed)
    assert [a.card_id for a in r.assignments if a.slot_index == 2] == ["club:3"]
    assert r.total_meta == 80.0 + 70.0 + 90.0


def test_budget_limits_total_price_of_priced_cards():
    cards = [_c(1, "GK"), _c(2, "CB"), _c(3, "CB"), _c(4, "ST")]
    meta = {"club:1": 80.0, "club:2": 70.0, "club:3": 95.0, "club:4": 85.0}
    prices = {"club:3": 5000}  # la carta de mercado, mejor que club:2
    free = build_squad(cards, meta, SLOTS, chem_weight=0, prices=prices, budget=10000)
    assert [a.card_id for a in free.assignments if a.slot_index == 1] == ["club:3"]
    assert free.spent == 5000
    tight = build_squad(cards, meta, SLOTS, chem_weight=0, prices=prices, budget=4000)
    assert [a.card_id for a in tight.assignments if a.slot_index == 1] == ["club:2"]
    assert tight.spent == 0


def test_no_budget_means_prices_are_ignored():
    cards = [_c(1, "GK"), _c(2, "CB"), _c(3, "CB"), _c(4, "ST")]
    meta = {"club:1": 80.0, "club:2": 70.0, "club:3": 95.0, "club:4": 85.0}
    r = build_squad(cards, meta, SLOTS, chem_weight=0, prices={"club:3": 999999})
    assert [a.card_id for a in r.assignments if a.slot_index == 1] == ["club:3"]
    assert r.spent == 999999


def test_included_card_is_forced_even_if_worse():
    cards = [_c(1, "GK"), _c(2, "CB"), _c(3, "CB"), _c(4, "ST")]
    meta = {"club:1": 80.0, "club:2": 70.0, "club:3": 95.0, "club:4": 85.0}
    r = build_squad(cards, meta, SLOTS, chem_weight=0, include_card_ids=["club:2"])
    assert [a.card_id for a in r.assignments if a.slot_index == 1] == ["club:2"]


def test_included_card_missing_from_pool_is_reported():
    cards = [_c(1, "GK"), _c(2, "CB"), _c(4, "ST")]
    r = build_squad(cards, {c.card_id: 80.0 for c in cards}, SLOTS, include_card_ids=["club:99"])
    assert r.status == "infeasible" and "club:99" in (r.message or "")
