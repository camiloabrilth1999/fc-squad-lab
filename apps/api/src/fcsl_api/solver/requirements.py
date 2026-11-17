"""Traducción de requisitos SBC a restricciones CP-SAT sobre un `SbcModel`."""

from ortools.sat.python import cp_model

from .cpsat import SbcModel, add_chemistry
from .models import Requirement, RequirementKind


def apply_requirement(m: SbcModel, req: Requirement) -> None:
    """Añade al modelo las restricciones de `req` (despacha por `req.kind`)."""
    handler = _HANDLERS.get(req.kind)
    if handler is None:
        raise NotImplementedError(f"Requirement kind {req.kind} not implemented yet")
    handler(m, req)


def _rating_excess(m: SbcModel) -> list[cp_model.IntVar]:
    """e_c = max(0, n·rating_c·used_c − sum_rating), creadas una vez por modelo.

    Es n veces el exceso max(0, r − S/n) de la fórmula de media; con used_c = 0
    la expresión es −sum_rating ≤ 0, así que e_c = 0.
    """
    if m.rating_excess is None:
        n = len(m.slots)
        excess: list[cp_model.IntVar] = []
        for c, card in enumerate(m.cards):
            e = m.model.new_int_var(0, 99 * n * n, f"rating_excess_{c}")
            m.model.add_max_equality(e, [0, n * card.rating * m.used[c] - m.sum_rating])
            excess.append(e)
        m.rating_excess = excess
    return m.rating_excess


def _team_rating(m: SbcModel, req: Requirement) -> None:
    # team_rating = floor((S + Σ max(0, r − S/n)) / n). Multiplicando por n²:
    # team_rating ≥ v  ⇔  n·S + Σ e_c ≥ n²·v
    # team_rating ≤ v  ⇔  n·S + Σ e_c < n²·(v + 1)
    n = len(m.slots)
    scaled = n * m.sum_rating + sum(_rating_excess(m))
    if req.op in ("min", "exact"):
        m.model.add(scaled >= n * n * req.value)
    if req.op in ("max", "exact"):
        m.model.add(scaled < n * n * (req.value + 1))


def _player_rating(m: SbcModel, req: Requirement) -> None:
    # rating es constante: basta con prohibir las cartas que no cumplen.
    for c, card in enumerate(m.cards):
        if not _compare(card.rating, req.op, req.value):
            m.model.add(m.used[c] == 0)


def _team_chemistry(m: SbcModel, req: Requirement) -> None:
    total = sum(add_chemistry(m).values())
    if req.op in ("min", "exact"):
        m.model.add(total >= req.value)
    if req.op in ("max", "exact"):
        m.model.add(total <= req.value)


def _player_chemistry(m: SbcModel, req: Requirement) -> None:
    if req.op != "min":
        raise ValueError(f"PLAYER_CHEMISTRY solo admite op 'min', no {req.op!r}")
    for c, v in add_chemistry(m).items():
        m.model.add(v >= req.value * m.used[c])


def _compare(actual: int, op: str, value: int) -> bool:
    if op == "min":
        return actual >= value
    if op == "max":
        return actual <= value
    return actual == value


_HANDLERS = {
    RequirementKind.TEAM_RATING: _team_rating,
    RequirementKind.PLAYER_RATING: _player_rating,
    RequirementKind.TEAM_CHEMISTRY: _team_chemistry,
    RequirementKind.PLAYER_CHEMISTRY: _player_chemistry,
}
