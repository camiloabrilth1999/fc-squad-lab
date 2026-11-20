import pytest

from fcsl_api.gallery.points import base_points, card_points

# (media, puntos) observados en soluciones de EasySBC para cartas normales.
OBSERVED_COMMON = [
    (54, 20), (60, 20), (64, 20), (65, 35), (70, 35), (74, 35), (75, 90), (76, 100),
    (77, 120), (78, 140), (79, 160), (80, 180), (81, 280), (82, 340), (83, 410),
    (84, 830), (85, 2100), (86, 4100), (87, 5500), (88, 8300),
]  # fmt: skip


@pytest.mark.parametrize(("rating", "pts"), OBSERVED_COMMON)
def test_base_points_match_observed_common_cards(rating: int, pts: int) -> None:
    assert base_points(rating) == (pts, True)


# (media, rareza EA, puntos) de cartas especiales observadas.
OBSERVED_SPECIAL = [
    (85, 3, 2625),  # TOTW
    (86, 3, 5125),
    (91, 3, 23750),
    (86, 71, 6150),  # Future Stars
    (85, 71, 3150),
    (86, 151, 6150),  # Ultimate Scream
    (80, 3, 225),
    (82, 3, 425),
    (85, 103, 2100),  # FC Heritage
    (91, 12, 42750),  # Icono base
    (92, 12, 45000),
    (93, 12, 56250),
    (90, 12, 31500),
    (82, 87, 340),  # Squad Foundations
]


@pytest.mark.parametrize(("rating", "rarity", "pts"), OBSERVED_SPECIAL)
def test_special_cards_apply_the_rarity_factor(rating: int, rarity: int, pts: int) -> None:
    got = card_points(rating, rarity, special=True)
    assert got.points == pts
    assert got.exact


def test_base_heroes_are_estimated_because_the_factor_varies_between_cards() -> None:
    got = card_points(88, 72, special=True)
    assert got.points == 10375 and not got.exact


def test_unknown_special_rarity_uses_the_default_factor_and_is_not_exact() -> None:
    got = card_points(85, 999, special=True)
    assert got.points == round(2100 * 1.25)
    assert not got.exact


def test_ratings_90_to_93_are_observed_and_the_rest_extrapolated() -> None:
    assert card_points(90, 0).exact and card_points(93, 0).points == 25000
    assert card_points(95, 0).exact is False
    assert card_points(99, 0).points > card_points(93, 0).points


def test_other_icon_rarities_default_to_the_icon_factor_but_are_flagged() -> None:
    got = card_points(91, 999, special=True, icon=True)
    assert got.points == 42750 and not got.exact
