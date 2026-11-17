"""Fuerza bruta para validar el modelo CP-SAT (solo pools pequeños)."""

from collections.abc import Callable
from itertools import permutations

from fcsl_api.solver.models import Card, Position


def brute_force(
    cards: list[Card],
    slots: list[Position],
    costs: list[int],
    check: Callable[[list[Card]], bool],
) -> int | None:
    """Coste mínimo entre asignaciones válidas que cumplen `check` (None si ninguna)."""
    best: int | None = None
    for combo in permutations(range(len(cards)), len(slots)):
        if any(slot not in cards[c].positions for c, slot in zip(combo, slots, strict=True)):
            continue
        if len({cards[c].asset_id for c in combo}) < len(combo):
            continue
        chosen = [cards[c] for c in combo]
        if not check(chosen):
            continue
        cost = sum(costs[c] for c in combo)
        if best is None or cost < best:
            best = cost
    return best
