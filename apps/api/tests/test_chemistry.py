from fcsl_api.solver.chemistry import (
    CLUB_THRESHOLDS,
    LEAGUE_THRESHOLDS,
    group_counts,
    player_chemistry,
    points,
    team_chemistry,
)

from .fixtures import make_card


def _card(i: int, **overrides):
    return make_card(card_id=f"c:{i}", asset_id=i, resource_id=i, **overrides)


def test_points():
    assert [points(n, CLUB_THRESHOLDS) for n in (1, 2, 5, 7)] == [0, 1, 2, 3]
    assert [points(n, LEAGUE_THRESHOLDS) for n in (2, 3, 8)] == [0, 1, 3]


def test_single_player_zero():
    cards = [_card(1)]
    assert player_chemistry(cards) == {"c:1": 0}
    assert team_chemistry(cards) == 0


def test_two_same_club_and_nation():
    cards = [_card(1, league_id=1), _card(2, league_id=2)]
    assert player_chemistry(cards) == {"c:1": 2, "c:2": 2}


def test_full_league():
    cards = [_card(i, league_id=9, club_id=i, nation_id=i) for i in range(1, 12)]
    assert set(player_chemistry(cards).values()) == {3}
    assert team_chemistry(cards) == 33


def test_icon_always_three():
    cards = [_card(1, is_icon=True, club_id=10, league_id=10, nation_id=10), _card(2)]
    assert player_chemistry(cards)["c:1"] == 3


def test_icon_doubles_nation():
    icon = _card(1, is_icon=True, club_id=10, league_id=10, nation_id=5)
    mate = _card(2, club_id=20, league_id=20, nation_id=5)
    _, _, nations = group_counts([icon, mate])
    assert nations[5] == 3
    assert player_chemistry([icon, mate])["c:2"] == 1


def test_hero_doubles_league():
    hero = _card(1, is_hero=True, club_id=10, league_id=7, nation_id=10)
    mate = _card(2, club_id=20, league_id=7, nation_id=20)
    _, leagues, _ = group_counts([hero, mate])
    assert leagues[7] == 3
    assert player_chemistry([hero, mate])["c:2"] == 1


def test_cap_three():
    cards = [_card(i) for i in range(1, 12)]
    assert set(player_chemistry(cards).values()) == {3}
    assert team_chemistry(cards) == 33
