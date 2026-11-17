"""Modelo CP-SAT base: huecos, elegibilidad por posición, jugador único y coste."""

import time
from collections import defaultdict
from dataclasses import dataclass

from ortools.sat.python import cp_model

from .chemistry import (
    CLUB_THRESHOLDS,
    HERO_LEAGUE_WEIGHT,
    ICON_NATION_WEIGHT,
    LEAGUE_THRESHOLDS,
    MAX_PLAYER_CHEM,
    NATION_THRESHOLDS,
)
from .models import Assignment, Card, Position


@dataclass
class SbcModel:
    model: cp_model.CpModel
    cards: list[Card]
    slots: list[Position]
    x: dict[tuple[int, int], cp_model.IntVar]  # (carta, hueco) -> 0/1, solo si es elegible
    used: list[cp_model.IntVar]  # used[c] = Σ_s x[c, s]
    sum_rating: cp_model.IntVar  # Σ rating·used
    # k_r = nº de cartas usadas con rating r; se crean bajo demanda (TEAM_RATING).
    rating_count: dict[int, cp_model.IntVar] | None = None
    # química 0..MAX_PLAYER_CHEM por índice de carta (0 si no se usa); ver add_chemistry.
    chem: dict[int, cp_model.IntVar] | None = None
    # present_g ⇔ Σ used del grupo ≥ 1, por familia ("league"/"nation"/"club") e id
    # de grupo; se crean bajo demanda (DISTINCT_*).
    group_present: dict[str, dict[int, cp_model.IntVar]] | None = None


def eligibility_problem(cards: list[Card], slots: list[Position]) -> str | None:
    """Mensaje si es imposible cubrir los huecos por posición; None si no hay problema."""
    eligible_assets: set[int] = set()
    for pos in slots:
        eligible = [c for c in cards if pos in c.positions]
        if not eligible:
            return f"Ningún jugador puede ocupar la posición {pos}"
        eligible_assets.update(c.asset_id for c in eligible)
    if len(eligible_assets) < len(slots):
        return f"No hay suficientes jugadores distintos para {len(slots)} huecos"
    return None


def build_base_model(cards: list[Card], slots: list[Position], costs: list[int]) -> SbcModel:
    # `costs` se acepta por contrato; el objetivo llega vía `objective_terms` en solve_model.
    if len(costs) != len(cards):
        raise ValueError("costs debe tener una entrada por carta")
    model = cp_model.CpModel()
    x: dict[tuple[int, int], cp_model.IntVar] = {}
    for c, card in enumerate(cards):
        for s, pos in enumerate(slots):
            if pos in card.positions:
                x[c, s] = model.new_bool_var(f"x_{c}_{s}")

    for s in range(len(slots)):
        model.add_exactly_one(x[c, s] for c in range(len(cards)) if (c, s) in x)

    used: list[cp_model.IntVar] = []
    for c in range(len(cards)):
        u = model.new_int_var(0, 1, f"used_{c}")
        model.add(u == sum(x[c, s] for s in range(len(slots)) if (c, s) in x))
        used.append(u)

    by_asset: dict[int, list[int]] = defaultdict(list)
    for c, card in enumerate(cards):
        by_asset[card.asset_id].append(c)
    for idxs in by_asset.values():
        if len(idxs) > 1:
            model.add(sum(used[c] for c in idxs) <= 1)

    sum_rating = model.new_int_var(0, 99 * len(slots), "sum_rating")
    model.add(sum_rating == sum(card.rating * used[c] for c, card in enumerate(cards)))

    return SbcModel(model, cards, slots, x, used, sum_rating)


def add_chemistry(m: SbcModel) -> dict[int, cp_model.IntVar]:
    """Química por carta dentro del modelo (espejo de `chemistry.player_chemistry`).

    Se crea una sola vez y se cachea en `m.chem`. Para cada grupo (club, liga,
    nación) count = Σ peso·used y reach_t ⇔ count ≥ umbral_t; los puntos del
    grupo son Σ reach_t. Carta normal: min(MAX, pc+pl+pn), 0 si no se usa.
    Icono/héroe: MAX·used.
    """
    if m.chem is not None:
        return m.chem
    model = m.model

    def weighted(kind: str, card: Card) -> tuple[int, int]:
        if kind == "club":
            return card.club_id, 1
        if kind == "league":
            return card.league_id, HERO_LEAGUE_WEIGHT if card.is_hero else 1
        return card.nation_id, ICON_NATION_WEIGHT if card.is_icon else 1

    thresholds = {
        "club": CLUB_THRESHOLDS,
        "league": LEAGUE_THRESHOLDS,
        "nation": NATION_THRESHOLDS,
    }
    # points[kind][group_id] = expresión lineal Σ reach_t (o 0 si nada es alcanzable)
    points: dict[str, dict[int, cp_model.LinearExprT]] = {}
    for kind, ts in thresholds.items():
        members: dict[int, list[tuple[int, int]]] = defaultdict(list)
        for c, card in enumerate(m.cards):
            gid, w = weighted(kind, card)
            members[gid].append((c, w))
        points[kind] = {}
        for gid, ms in members.items():
            count = sum(w * m.used[c] for c, w in ms)
            reachable = sum(w for _, w in ms)
            reach = []
            for t in ts:
                if reachable < t:
                    continue
                b = model.new_bool_var(f"reach_{kind}_{gid}_{t}")
                model.add(count >= t).only_enforce_if(b)
                model.add(count <= t - 1).only_enforce_if(~b)
                reach.append(b)
            points[kind][gid] = sum(reach)

    chem: dict[int, cp_model.IntVar] = {}
    for c, card in enumerate(m.cards):
        v = model.new_int_var(0, MAX_PLAYER_CHEM, f"chem_{c}")
        if card.is_icon or card.is_hero:
            model.add(v == MAX_PLAYER_CHEM * m.used[c])
        else:
            total = (
                points["club"][card.club_id]
                + points["league"][card.league_id]
                + points["nation"][card.nation_id]
            )
            raw = model.new_int_var(0, MAX_PLAYER_CHEM, f"chem_raw_{c}")
            model.add_min_equality(raw, [MAX_PLAYER_CHEM, total])
            # v = raw si used, 0 si no
            model.add(v <= MAX_PLAYER_CHEM * m.used[c])
            model.add(v <= raw)
            model.add(v >= raw - MAX_PLAYER_CHEM * (1 - m.used[c]))
        chem[c] = v
    m.chem = chem
    return chem


# Arranque en caliente para pools grandes: antes del modelo completo se resuelve
# una copia restringida a un subconjunto prometedor y su solución se pasa como
# pista. Solo acelera encontrar soluciones; no cambia el óptimo ni el estado.
WARM_START_MIN_CARDS = 1000
WARM_START_CARDS = 400
WARM_START_MAX_S = 3.0
WARM_START_SHARE = 0.3  # fracción máxima del tiempo total para la fase previa


def _warm_start_subset(m: SbcModel, coef: list[int]) -> list[int]:
    """Índices de carta prometedores: por (rating, posiciones∩huecos), las de menor
    coeficiente de objetivo, tomando antes la 1.ª de cada grupo, luego la 2.ª…"""
    slot_set = frozenset(m.slots)
    groups: dict[tuple[int, frozenset[str]], list[int]] = defaultdict(list)
    for c, card in enumerate(m.cards):
        groups[card.rating, slot_set & frozenset(card.positions)].append(c)
    ranked = []
    for idxs in groups.values():
        idxs.sort(key=lambda c: (coef[c], c))
        ranked.extend((i, coef[c], c) for i, c in enumerate(idxs))
    ranked.sort()
    return [c for _, _, c in ranked[:WARM_START_CARDS]]


def _warm_start(
    m: SbcModel, objective_terms: list[tuple[int, cp_model.IntVar]], time_limit_s: float
) -> None:
    coef = [0] * len(m.cards)
    card_of = {u.index: c for c, u in enumerate(m.used)}
    for k, var in objective_terms:
        if var.index in card_of:
            coef[card_of[var.index]] += k
    keep = set(_warm_start_subset(m, coef))
    sub = m.model.clone()
    for c, u in enumerate(m.used):
        if c not in keep:
            sub.add(sub.get_int_var_from_proto_index(u.index) == 0)
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = time_limit_s
    solver.parameters.num_workers = 8
    solver.parameters.random_seed = 0
    if solver.solve(sub) not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return
    m.model.clear_hints()
    for i in range(len(m.model.proto.variables)):
        value = solver.value(sub.get_int_var_from_proto_index(i))
        m.model.add_hint(m.model.get_int_var_from_proto_index(i), value)


def solve_model(
    m: SbcModel,
    objective_terms: list[tuple[int, cp_model.IntVar]],
    time_limit_s: float,
) -> tuple[str, list[Assignment], float]:
    start = time.perf_counter()
    if objective_terms:
        m.model.minimize(sum(coef * var for coef, var in objective_terms))
        if len(m.cards) >= WARM_START_MIN_CARDS:
            _warm_start(
                m, objective_terms, min(WARM_START_MAX_S, WARM_START_SHARE * time_limit_s)
            )
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = max(0.0, time_limit_s - (time.perf_counter() - start))
    solver.parameters.num_workers = 8
    solver.parameters.random_seed = 0
    status = solver.solve(m.model)
    elapsed = time.perf_counter() - start

    if status == cp_model.MODEL_INVALID:
        raise ValueError(f"Modelo CP-SAT inválido: {m.model.validate()}")
    if status == cp_model.OPTIMAL:
        name = "optimal"
    elif status == cp_model.FEASIBLE:
        name = "feasible"
    elif status == cp_model.INFEASIBLE:
        return "infeasible", [], elapsed
    else:
        return "unknown", [], elapsed

    assignments = [
        Assignment(slot_index=s, position=m.slots[s], card_id=m.cards[c].card_id)
        for (c, s), var in m.x.items()
        if solver.value(var)
    ]
    assignments.sort(key=lambda a: a.slot_index)
    return name, assignments, elapsed
