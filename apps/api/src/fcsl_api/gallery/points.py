"""Puntos de Galería de una carta: tabla base por media × factor de rareza.

Calibrado (2026-11-19) con ~200 cartas de soluciones de EasySBC como guía de desarrollo; no
depende de EasySBC en tiempo de ejecución. Lo observado:

- Cartas "normales" (oro/plata/bronce, común o rara): puntos = tabla por media, sin más.
- Cartas especiales: tabla × factor (1,25 · 1,5 · 1,875 · 2,25) según su rareza.
- Una carta evolucionada puntúa con su media nueva y ×1,875.

`exact=False` cuando el factor o la media están extrapolados, no observados.
"""

from dataclasses import dataclass

# (media máxima, puntos). Observado hasta 89 y 91; 90 y ≥92 extrapolados (+4000, +5000 …).
_BASE: tuple[tuple[int, int], ...] = (
    (64, 20),
    (74, 35),
    (75, 90),
    (76, 100),
    (77, 120),
    (78, 140),
    (79, 160),
    (80, 180),
    (81, 280),
    (82, 340),
    (83, 410),
    (84, 830),
    (85, 2100),
    (86, 4100),
    (87, 5500),
    (88, 8300),
    (89, 11000),
)
# observado: 91 (23750 = 19000 × 1,25), 90, 92 y 93 con Iconos (×2,25)
_OBSERVED_TOP = {90: 14000, 91: 19000, 92: 20000, 93: 25000}
_ESTIMATED_TOP = {94: 31000, 95: 37000}
_CAP = 45000  # ≥ 96 (estimado)

# Factor por rareza EA (`rarity_ea_id`), observado salvo los marcados como estimados.
RARITY_FACTOR: dict[int, float] = {
    0: 1.0,  # común
    1: 1.0,  # rara
    103: 1.0,  # FC Heritage
    87: 1.0,  # Squad Foundations
    12: 2.25,  # Icono base
    3: 1.25,  # Team of the Week
    72: 1.25,  # Héroe base
    22: 1.25,  # Destined for Glory
    177: 1.25,  # POTM
    50: 1.25,  # UEFA RTTK
    10: 1.5,  # Hall of FUT: Unleashed
    71: 1.5,  # Future Stars
    151: 1.5,  # Ultimate Scream
}
_ESTIMATED_FACTOR: dict[int, float] = {9: 2.25, 150: 1.25}  # Hall of FUT, Season 1 (a confirmar)
DEFAULT_SPECIAL_FACTOR = 1.25  # rarezas especiales no observadas aún
EVOLVED_FACTOR = 1.875


@dataclass(frozen=True)
class CardPoints:
    points: int
    exact: bool


def base_points(rating: int | None) -> tuple[int, bool]:
    """Puntos de una carta común de esa media y si el valor está observado (no extrapolado)."""
    if rating is None:
        return 20, False
    for top, pts in _BASE:
        if rating <= top:
            return pts, True
    if rating in _OBSERVED_TOP:
        return _OBSERVED_TOP[rating], True
    if rating in _ESTIMATED_TOP:
        return _ESTIMATED_TOP[rating], False
    return _CAP, False


def rarity_factor(
    rarity_ea_id: int | None, *, special: bool, icon: bool = False
) -> tuple[float, bool]:
    if rarity_ea_id in RARITY_FACTOR:
        return RARITY_FACTOR[rarity_ea_id], True  # type: ignore[index]
    if rarity_ea_id in _ESTIMATED_FACTOR:
        return _ESTIMATED_FACTOR[rarity_ea_id], False  # type: ignore[index]
    if icon:  # otros Iconos (Prime, Momentos…): como los base, sin confirmar
        return 2.25, False
    return (DEFAULT_SPECIAL_FACTOR, False) if special else (1.0, True)


def card_points(
    rating: int | None, rarity_ea_id: int | None, *, special: bool = False, icon: bool = False
) -> CardPoints:
    """Puntos que aporta una carta al coleccionarla."""
    base, base_exact = base_points(rating)
    factor, factor_exact = rarity_factor(rarity_ea_id, special=special, icon=icon)
    return CardPoints(points=round(base * factor), exact=base_exact and factor_exact)
