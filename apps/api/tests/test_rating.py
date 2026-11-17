import pytest
from pydantic import ValidationError

from fcsl_api.solver.rating import team_rating

from .fixtures import make_card


def test_all_equal():
    assert team_rating([84] * 11) == 84


def test_excess_lifts():
    assert team_rating([83] * 10 + [90]) == 84


def test_floor():
    assert team_rating([83] * 10 + [84]) == 83


def test_small_squad():
    assert team_rating([80, 90, 70]) == 83


def test_empty():
    assert team_rating([]) == 0


@pytest.mark.parametrize(
    ("rating", "level"),
    [(64, "bronze"), (65, "silver"), (74, "silver"), (75, "gold")],
)
def test_card_level(rating, level):
    assert make_card(rating=rating).level == level


def test_card_requires_positions():
    with pytest.raises(ValidationError):
        make_card(positions=[])
