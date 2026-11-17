"""Química de FC como función pura; el modelo CP-SAT se verifica contra esto."""

from collections import Counter
from collections.abc import Sequence

from .models import Card

# Validar contra el juego
CLUB_THRESHOLDS = (2, 5, 7)
LEAGUE_THRESHOLDS = (3, 5, 8)
NATION_THRESHOLDS = (2, 5, 8)
MAX_PLAYER_CHEM = 3
ICON_NATION_WEIGHT = 2  # Validar contra el juego
HERO_LEAGUE_WEIGHT = 2  # Validar contra el juego


def points(count: int, thresholds: tuple[int, int, int]) -> int:
    return sum(1 for t in thresholds if count >= t)


def group_counts(
    cards: Sequence[Card],
) -> tuple[Counter[int], Counter[int], Counter[int]]:
    clubs: Counter[int] = Counter()
    leagues: Counter[int] = Counter()
    nations: Counter[int] = Counter()
    for c in cards:
        clubs[c.club_id] += 1
        leagues[c.league_id] += HERO_LEAGUE_WEIGHT if c.is_hero else 1
        nations[c.nation_id] += ICON_NATION_WEIGHT if c.is_icon else 1
    return clubs, leagues, nations


def player_chemistry(cards: Sequence[Card]) -> dict[str, int]:
    clubs, leagues, nations = group_counts(cards)
    result: dict[str, int] = {}
    for c in cards:
        if c.is_icon or c.is_hero:
            result[c.card_id] = MAX_PLAYER_CHEM
            continue
        total = (
            points(clubs[c.club_id], CLUB_THRESHOLDS)
            + points(leagues[c.league_id], LEAGUE_THRESHOLDS)
            + points(nations[c.nation_id], NATION_THRESHOLDS)
        )
        result[c.card_id] = min(MAX_PLAYER_CHEM, total)
    return result


def team_chemistry(cards: Sequence[Card]) -> int:
    return sum(player_chemistry(cards).values())
