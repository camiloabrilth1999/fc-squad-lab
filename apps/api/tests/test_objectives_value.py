import pytest

from fcsl_api.objectives.value import PriceBook, allocate, award_value, parse_pack

BOOK = PriceBook(
    by_rating={75: 1000, 80: 2000, 83: 5000, 85: 20000},
    by_card={999: 7000},
    pack_names={
        1: "Sobre de futb. Oro x3 81+",
        2: "Sobre de futbolista Oro 80+",
        3: "Sobre Oro gigante",
        4: "Sobre de futbolista Oro 75-83",
        5: "Sobre misterioso",
    },
)


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("Sobre de futb. Oro x3 81+", (3, 81)),
        ("Sobre de futb. Oro x10 78+", (10, 78)),
        ("Sobre de futbolista Oro 80+", (1, 80)),
        ("Sobre de futbolista Oro 75-83", (1, 79)),
        ("Sobre Oro gigante", (12, 75)),
        ("Sobre pequeño de futbolistas Oro", (3, 75)),
        ("Sobre grande de futb. Plata", (6, 68)),
        ("Sobre de futbolistas x2", (2, 70)),
        ("Sobre misterioso", None),
        ("", None),
    ],
)
def test_pack_names_become_count_and_minimum_rating(
    name: str, expected: tuple[int, int] | None
) -> None:
    assert parse_pack(name) == expected


def test_price_book_uses_the_nearest_rating_within_two_points() -> None:
    assert BOOK.at(80) == 2000
    assert BOOK.at(81) == 2000  # el más cercano
    assert BOOK.at(95) == 0  # sin datos cerca


def test_coins_and_items_and_packs_are_valued_in_coins() -> None:
    assert award_value({"type": "coin", "value": 5000, "count": 2}, BOOK).value == 10000
    # carta con precio propio, intransferible: la mitad
    item = {
        "type": "item",
        "value": 999,
        "count": 1,
        "untradeable": True,
        "item": {"resource_id": 999, "rating": 85},
    }
    assert award_value(item, BOOK).value == 3500
    # sin precio propio: el de una carta común de esa media
    item2 = {
        "type": "item",
        "value": 5,
        "count": 1,
        "untradeable": False,
        "item": {"resource_id": 5, "rating": 83},
    }
    assert award_value(item2, BOOK).value == 5000
    pack = {"type": "pack", "value": 1, "count": 1, "untradeable": False}
    assert award_value(pack, BOOK).value == 3 * BOOK.at(81)
    two = {"type": "pack", "value": 2, "count": 2, "untradeable": False}
    assert award_value(two, BOOK).value == 2 * 2000


def test_unvaluable_awards_are_flagged_not_invented() -> None:
    xp = award_value({"type": "xp", "value": 200, "count": 1}, BOOK)
    assert (xp.value, xp.valued) == (0, True) and "XP" in xp.label
    mystery = award_value({"type": "pack", "value": 5, "count": 1}, BOOK)
    assert (mystery.value, mystery.valued) == (0, False)
    star = award_value(
        {"type": "item", "value": 1, "count": 1, "item": {"resource_id": 1, "rating": 99}}, BOOK
    )
    assert star.valued is False


def test_allocate_picks_the_best_value_within_the_match_budget() -> None:
    # sesión A: dos objetivos (3 partidos → 100, 10 partidos → 500); sesión B: uno (5 → 400)
    sessions = [[(3, 100), (10, 500)], [(5, 400)]]
    plays, value = allocate(sessions, budget=8)
    assert plays == [3, 5] and value == 500  # A al paso corto + B entero
    plays, value = allocate(sessions, budget=15)
    assert plays == [10, 5] and value == 1000
    plays, value = allocate(sessions, budget=2)
    assert plays == [0, 0] and value == 0


def test_allocate_with_a_huge_budget_completes_everything() -> None:
    plays, value = allocate([[(4, 10)], [(6, 20)]], budget=1000)
    assert plays == [4, 6] and value == 30
