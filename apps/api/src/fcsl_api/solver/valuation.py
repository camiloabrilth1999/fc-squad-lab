"""Coste de cada carta y términos del objetivo (lexicográfico vía multiplicador)."""

from ortools.sat.python import cp_model

from .cpsat import SbcModel
from .models import Card, Objective, ValuationSettings

BIG = 10**6  # separa el criterio principal del coste (lexicográfico)


def card_cost(card: Card, v: ValuationSettings) -> int:
    """Mercado: precio. Propia intransferible: 0. Propia transferible: precio·factor.

    Duplicada o en almacén SBC: además ·(1 − descuento), con el mayor descuento
    de los que apliquen (no se acumulan).
    """
    if card.source == "market":
        cost = float(card.price or 0)
    elif card.untradeable:
        return 0
    else:
        cost = float(round((card.price or 0) * v.tradeable_factor))
    discounts = []
    if card.duplicate:
        discounts.append(v.duplicate_discount)
    if card.in_sbc_storage:
        discounts.append(v.storage_discount)
    if discounts:
        cost *= 1 - max(discounts)
    return round(cost)


def _owned_untradeable(card: Card) -> bool:
    return card.source == "club" and card.untradeable


def _spare(card: Card) -> bool:
    """Duplicada o en almacén: conviene gastarla."""
    return card.duplicate or card.in_sbc_storage


def objective_terms(
    m: SbcModel, costs: list[int], objective: Objective
) -> list[tuple[int, cp_model.IntVar]]:
    """Un término (coef, used_c) por carta; `solve_model` minimiza Σ coef·used.

    - CHEAPEST: 100·coste − bonus (1 si propia intransferible, +1 si duplicada o
      en almacén): el coste manda y el bonus solo desempata.
    - FEWEST_BUYS: BIG·[mercado] + coste.
    - USE_CLUB: −BIG·[propia intransferible o duplicada] + coste.
    """
    if len(costs) != len(m.cards):
        raise ValueError("costs debe tener una entrada por carta")
    terms: list[tuple[int, cp_model.IntVar]] = []
    for c, card in enumerate(m.cards):
        cost = costs[c]
        if objective == Objective.CHEAPEST:
            bonus = int(_owned_untradeable(card)) + int(_spare(card))
            coef = 100 * cost - bonus
        elif objective == Objective.FEWEST_BUYS:
            coef = BIG * int(card.source == "market") + cost
        elif objective == Objective.USE_CLUB:
            preferred = card.source == "club" and (card.untradeable or card.duplicate)
            coef = -BIG * int(preferred) + cost
        else:
            raise ValueError(f"Objetivo desconocido: {objective!r}")
        terms.append((coef, m.used[c]))
    return terms
