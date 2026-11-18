"""Química de FC como función pura; el modelo CP-SAT se verifica contra esto.

En FC un jugador solo suma química si juega en una de sus posiciones. Fuera de
posición no aporta nada a los recuentos de club/liga/nación del equipo y su propia
química es 0. Las funciones aceptan `slots`: la posición en la que juega cada carta,
en el mismo orden que `cards`. Si `slots` es `None`, se asume que todas están en
posición (atajo para plantillas ya construidas en posición y para los tests que no
dependen de la colocación).
"""

from collections import Counter
from collections.abc import Sequence

from .models import Card, Position

# Validar contra el juego
CLUB_THRESHOLDS = (2, 5, 7)
LEAGUE_THRESHOLDS = (3, 5, 8)
NATION_THRESHOLDS = (2, 5, 8)
MAX_PLAYER_CHEM = 3
ICON_NATION_WEIGHT = 2  # Validar contra el juego
HERO_LEAGUE_WEIGHT = 2  # Validar contra el juego


def points(count: int, thresholds: tuple[int, int, int]) -> int:
    return sum(1 for t in thresholds if count >= t)


def _in_position(card: Card, slot: Position | None) -> bool:
    return slot is None or slot in card.positions


def _slots_for(cards: Sequence[Card], slots: Sequence[Position] | None) -> list[Position | None]:
    if slots is None:
        return [None] * len(cards)
    if len(slots) != len(cards):
        raise ValueError("slots debe tener una entrada por carta")
    return list(slots)


def group_counts(
    cards: Sequence[Card],
    slots: Sequence[Position] | None = None,
) -> tuple[Counter[int], Counter[int], Counter[int]]:
    clubs: Counter[int] = Counter()
    leagues: Counter[int] = Counter()
    nations: Counter[int] = Counter()
    for c, slot in zip(cards, _slots_for(cards, slots), strict=True):
        if not _in_position(c, slot):
            continue  # fuera de posición: no cuenta para los vínculos del equipo
        clubs[c.club_id] += 1
        leagues[c.league_id] += HERO_LEAGUE_WEIGHT if c.is_hero else 1
        nations[c.nation_id] += ICON_NATION_WEIGHT if c.is_icon else 1
    return clubs, leagues, nations


def player_chemistry(
    cards: Sequence[Card],
    slots: Sequence[Position] | None = None,
) -> dict[str, int]:
    clubs, leagues, nations = group_counts(cards, slots)
    result: dict[str, int] = {}
    for c, slot in zip(cards, _slots_for(cards, slots), strict=True):
        if not _in_position(c, slot):
            result[c.card_id] = 0  # fuera de posición: 0 química
            continue
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


def team_chemistry(
    cards: Sequence[Card],
    slots: Sequence[Position] | None = None,
) -> int:
    return sum(player_chemistry(cards, slots).values())
