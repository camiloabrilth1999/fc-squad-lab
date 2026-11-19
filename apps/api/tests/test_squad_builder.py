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
