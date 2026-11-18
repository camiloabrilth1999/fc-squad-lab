"""Fuerza bruta para validar el modelo CP-SAT (solo pools pequeños).

Como en los DCP de EA, cualquier carta puede ir en cualquier hueco (fuera de
posición); la posición solo afecta a la química. Por eso `check` recibe también la
lista de huecos en los que juega cada carta elegida, en el mismo orden que `chosen`,
y las comprobaciones de química la usan para saber quién está fuera de posición.
"""

from collections.abc import Callable
from itertools import permutations

from fcsl_api.solver.models import Card, Position


def brute_force(
    cards: list[Card],
    slots: list[Position],
    costs: list[int],
    check: Callable[[list[Card], list[Position]], bool],
) -> int | None:
    """Coste mínimo entre asignaciones válidas que cumplen `check` (None si ninguna)."""
    best: int | None = None
    for combo in permutations(range(len(cards)), len(slots)):
        if len({cards[c].asset_id for c in combo}) < len(combo):
            continue
        chosen = [cards[c] for c in combo]
        if not check(chosen, slots):
            continue
        cost = sum(costs[c] for c in combo)
        if best is None or cost < best:
            best = cost
    return best
