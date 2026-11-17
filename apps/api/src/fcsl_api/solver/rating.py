import math
from collections.abc import Sequence
from fractions import Fraction


def team_rating(ratings: Sequence[int]) -> int:
    """Media de equipo: (S + sum(max(0, r - S/n))) / n, redondeada (floor)."""
    n = len(ratings)
    if n == 0:
        return 0
    total = sum(ratings)
    mean = Fraction(total, n)  # exacto: evita errores de coma flotante en el floor
    excess = sum((max(Fraction(0), r - mean) for r in ratings), Fraction(0))
    return math.floor((total + excess) / n)  # floor: Validar contra el juego
