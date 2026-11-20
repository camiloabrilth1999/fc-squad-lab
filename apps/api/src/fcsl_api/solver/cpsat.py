"""Modelo CP-SAT base: huecos, jugador único y coste.

Como en los DCP de EA, cualquier carta puede ocupar cualquier hueco (fuera de
posición): la posición no limita la elegibilidad, solo la química. `inpos[c]` vale
1 si la carta `c` se usa en un hueco que es una de sus posiciones; la química se
calcula sobre `inpos` (una carta fuera de posición no aporta nada ni se lleva nada).
"""

import time
from collections import Counter, defaultdict
from dataclasses import dataclass, field

from ortools.sat.python import cp_model

from .chemistry import (
    CLUB_THRESHOLDS,
    HERO_LEAGUE_WEIGHT,
    ICON_NATION_WEIGHT,
    LEAGUE_THRESHOLDS,
    MAX_PLAYER_CHEM,
    NATION_THRESHOLDS,
)
from .models import Assignment, Card, Position, Requirement, RequirementKind


@dataclass
class SbcModel:
    model: cp_model.CpModel
    cards: list[Card]
    slots: list[Position]
    # x[c, k] -> 0/1: la carta c ocupa un hueco. Clave k = posición (str, modelo por
    # cupos: huecos de igual posición comparten cupo) o índice de hueco (int, modelo
    # en posición hueco a hueco en pools pequeños). `_assignments` distingue ambas.
    x: dict[tuple[int, int | str], cp_model.IntVar]
    used: list[cp_model.IntVar]  # used[c] = Σ x[c, ·]
    # inpos[c] = 1 si la carta c ocupa un hueco de una de sus posiciones; 0 si no se
    # usa o se usa fuera de posición. La química depende de inpos, no de used.
    inpos: list[cp_model.IntVar]
    sum_rating: cp_model.IntVar  # Σ rating·used
    # k_r = nº de cartas usadas con rating r; se crean bajo demanda (TEAM_RATING).
    rating_count: dict[int, cp_model.IntVar] | None = None
    # química 0..MAX_PLAYER_CHEM por índice de carta (0 si no se usa); ver add_chemistry.
    chem: dict[int, cp_model.IntVar] | None = None
    # present_g ⇔ Σ used del grupo ≥ 1, por familia ("league"/"nation"/"club") e id
    # de grupo; se crean bajo demanda (DISTINCT_*).
    group_present: dict[str, dict[int, cp_model.IntVar]] | None = None
    # requisitos aplicados (apply_requirement); guían la fase restringida.
    requirements: list[Requirement] = field(default_factory=list)
    # índices de carta fijados a used = 1 (include_card); siempre entran en los
    # vecindarios de la fase restringida.
    included: set[int] = field(default_factory=set)


def include_card(m: SbcModel, c: int) -> None:
    """Obliga a usar la carta `c` y la registra para la fase restringida."""
    m.model.add(m.used[c] == 1)
    m.included.add(c)


def eligibility_problem(cards: list[Card], slots: list[Position]) -> str | None:
    """Mensaje si es imposible cubrir los huecos; None si no hay problema.

    Cualquier carta puede ir en cualquier hueco (fuera de posición), así que lo
    único que puede impedir una plantilla es no tener suficientes jugadores
    distintos (por asset) para los huecos.
    """
    distinct_assets = {c.asset_id for c in cards}
    if len(distinct_assets) < len(slots):
        return f"No hay suficientes jugadores distintos para {len(slots)} huecos"
    return None


def build_base_model(
    cards: list[Card],
    slots: list[Position],
    costs: list[int],
    *,
    in_position_only: bool = False,
    allowed: dict[int, set[str]] | None = None,
) -> SbcModel:
    """Modelo base. Cualquier carta puede ocupar cualquier hueco (fuera de posición
    permitido): los huecos se agrupan por posición con un cupo (`x[c, p]`, clave por
    posición), lo que mantiene el modelo pequeño pese a esa libertad. `inpos[c]`
    marca si la carta juega en una de sus posiciones (la química depende de inpos).

    Con `in_position_only` cada carta solo puede ocupar huecos de sus posiciones:
    resuelve rápido una plantilla en posición que es a la vez solución válida (y
    cota) del modelo completo. Es infactible si algún hueco no tiene ninguna carta
    de su posición (en ese caso el modelo completo la resuelve fuera de posición).
    En pools pequeños ese modelo se formula hueco a hueco (`x[c, s]`, clave por
    hueco), más denso pero con mejor convergencia al óptimo; en pools grandes usa
    los mismos cupos que el completo, que escala mejor. `_assignments` distingue las
    dos claves (int = hueco, str = posición).

    Con `allowed` (índice de carta → posiciones donde puede jugar, propias o no) se usa
    siempre el modelo por cupos y cada carta solo entra en sus posiciones permitidas.
    """
    # `costs` se acepta por contrato; el objetivo llega vía `objective_terms` en solve_model.
    if len(costs) != len(cards):
        raise ValueError("costs debe tener una entrada por carta")
    model = cp_model.CpModel()
    x: dict[tuple[int, int | str], cp_model.IntVar] = {}
    used: list[cp_model.IntVar] = []
    inpos: list[cp_model.IntVar] = []

    if allowed is None and in_position_only and len(cards) <= PERSLOT_MAX_CARDS:
        # Formulación densa hueco a hueco: una var por (carta, hueco jugable).
        for c, card in enumerate(cards):
            for s, pos in enumerate(slots):
                if pos in card.positions:
                    x[c, s] = model.new_bool_var(f"x_{c}_{s}")
        for s in range(len(slots)):
            model.add_exactly_one(x[c, s] for c in range(len(cards)) if (c, s) in x)
        for c in range(len(cards)):
            u = model.new_int_var(0, 1, f"used_{c}")
            model.add(u == sum(x[c, s] for s in range(len(slots)) if (c, s) in x))
            used.append(u)
            inpos.append(u)  # en posición: inpos == used
    else:
        # Cupos por posición: cualquier carta en cualquier posición (modelo completo)
        # o solo en las suyas (in_position_only en pools grandes).
        pos_caps = Counter(slots)  # posición -> nº de huecos de esa posición
        positions = list(pos_caps)

        def eligible(c: int, card: Card, p: str) -> bool:
            if allowed is not None:  # posiciones permitidas por carta (fuera de posición acotado)
                return p in allowed[c]
            return not in_position_only or p in card.positions

        for c, card in enumerate(cards):
            for p in positions:
                if eligible(c, card, p):
                    x[c, p] = model.new_bool_var(f"x_{c}_{p}")
        for p in positions:  # cada posición se llena con exactamente su cupo
            model.add(sum(x[c, p] for c in range(len(cards)) if (c, p) in x) == pos_caps[p])
        for c, card in enumerate(cards):
            mine = [p for p in positions if (c, p) in x]
            u = model.new_int_var(0, 1, f"used_{c}")  # ≤ 1 fuerza a la carta a ≤ 1 hueco
            model.add(u == sum(x[c, p] for p in mine))
            used.append(u)
            ip = model.new_int_var(0, 1, f"inpos_{c}")
            model.add(ip == sum(x[c, p] for p in mine if p in card.positions))
            inpos.append(ip)

    by_asset: dict[int, list[int]] = defaultdict(list)
    for c, card in enumerate(cards):
        by_asset[card.asset_id].append(c)
    for idxs in by_asset.values():
        if len(idxs) > 1:
            model.add(sum(used[c] for c in idxs) <= 1)

    sum_rating = model.new_int_var(0, 99 * len(slots), "sum_rating")
    model.add(sum_rating == sum(card.rating * used[c] for c, card in enumerate(cards)))

    return SbcModel(model, cards, slots, x, used, inpos, sum_rating)


def add_chemistry(m: SbcModel) -> dict[int, cp_model.IntVar]:
    """Química por carta dentro del modelo (espejo de `chemistry.player_chemistry`).

    Se crea una sola vez y se cachea en `m.chem`. Para cada grupo (club, liga,
    nación) count = Σ peso·inpos y reach_t ⇔ count ≥ umbral_t; los puntos del
    grupo son Σ reach_t. Carta normal: min(MAX, pc+pl+pn), 0 si no se usa o se usa
    fuera de posición. Icono/héroe: MAX·inpos. Se usa `inpos` (no `used`) porque
    una carta fuera de posición no aporta ni recibe química.
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
            count = sum(w * m.inpos[c] for c, w in ms)
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
            model.add(v == MAX_PLAYER_CHEM * m.inpos[c])
        else:
            total = (
                points["club"][card.club_id]
                + points["league"][card.league_id]
                + points["nation"][card.nation_id]
            )
            raw = model.new_int_var(0, MAX_PLAYER_CHEM, f"chem_raw_{c}")
            model.add_min_equality(raw, [MAX_PLAYER_CHEM, total])
            # v = raw si en posición, 0 si no se usa o se usa fuera de posición
            model.add(v <= MAX_PLAYER_CHEM * m.inpos[c])
            model.add(v <= raw)
            model.add(v >= raw - MAX_PLAYER_CHEM * (1 - m.inpos[c]))
        chem[c] = v
    m.chem = chem
    return chem


# Fase restringida: antes del modelo completo se resuelven copias del modelo
# limitadas a vecindarios (subconjuntos prometedores de cartas). Una copia solo
# añade used_c = 0 a las cartas de fuera, así que cada solución suya es solución
# del modelo completo: sirve de pista para el solve completo y de respaldo si
# este no encuentra nada mejor. El estado "optimal" solo lo da el modelo completo.
#
# Vecindario principal: ventana de media alrededor del objetivo de TEAM_RATING.
# Las plantillas baratas usan cartas cerca de la media pedida (el precio crece
# muy deprisa con el rating), y con ~100 cartas la química, cuya relajación
# lineal es débil, se resuelve en segundos en vez de minutos.
# El modelo en posición de pools pequeños se formula hueco a hueco (denso), que
# converge más al óptimo; por encima de este tamaño usa cupos por posición (como el
# modelo completo), que escala sin quedarse sin encontrar factible.
PERSLOT_MAX_CARDS = 2000

RESTRICTED_MIN_CARDS = 150
RESTRICTED_MAX_S = 6.0
RESTRICTED_SHARE = 0.6  # fracción máxima del límite para la fase restringida
RATING_WINDOWS = ((-3, 2), (-4, 3))  # desplazamientos sobre la media pedida
MIN_STEP_S = 0.3  # no se empieza un vecindario con menos tiempo que esto
# Sin objetivo de media, en pools grandes: las más baratas por (rating, huecos).
CHEAP_SUBSET_MIN_CARDS = 1000
CHEAP_SUBSET_CARDS = 400

# (status, objetivo, valor de cada variable del proto por índice)
SolverResult = tuple[cp_model.CpSolverStatus, int | None, list[int] | None]


def _cheap_subset(m: SbcModel, coef: list[int]) -> set[int]:
    """Índices de carta baratos: por (rating, posiciones∩huecos), las de menor
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
    return {c for _, _, c in ranked[:CHEAP_SUBSET_CARDS]}


def _rating_target(m: SbcModel) -> int | None:
    values = [
        r.value
        for r in m.requirements
        if r.kind == RequirementKind.TEAM_RATING and r.op in ("min", "exact")
    ]
    return max(values) if values else None


def _neighbourhoods(m: SbcModel, coef: list[int]) -> list[set[int]]:
    """Vecindarios en orden de uso; se omiten los que no restringen nada."""
    target = _rating_target(m)
    hoods: list[set[int]] = []
    if target is not None:
        for lo, hi in RATING_WINDOWS:
            hoods.append(
                {c for c, card in enumerate(m.cards) if target + lo <= card.rating <= target + hi}
            )
    elif len(m.cards) >= CHEAP_SUBSET_MIN_CARDS:
        hoods.append(_cheap_subset(m, coef))
    result: list[set[int]] = []
    for hood in hoods:
        if hood and len(hood) < len(m.cards) and hood not in result:
            result.append(hood)
    return result


def _run_solver(
    model: cp_model.CpModel, time_limit_s: float, *, first_solution: bool = False
) -> SolverResult:
    solver = cp_model.CpSolver()
    solver.parameters.stop_after_first_solution = first_solution  # solo comprobar si cabe
    solver.parameters.max_time_in_seconds = max(0.0, time_limit_s)
    solver.parameters.num_workers = 8
    solver.parameters.random_seed = 0
    status = solver.solve(model)
    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return status, None, None
    values = [
        solver.value(model.get_int_var_from_proto_index(i))
        for i in range(len(model.proto.variables))
    ]
    return status, round(solver.objective_value), values


def _set_hint(model: cp_model.CpModel, values: list[int]) -> None:
    model.clear_hints()
    for i, value in enumerate(values):
        model.add_hint(model.get_int_var_from_proto_index(i), value)


def _restricted_phase(
    m: SbcModel, coef: list[int], budget_s: float
) -> tuple[int, list[int]] | None:
    """Mejor (objetivo, valores) de los vecindarios en `budget_s`, o None.

    Cada vecindario incluye las cartas obligadas (`m.included`) y las de la mejor
    solución hasta el momento, que recibe como pista, así que nunca empeora. El
    primero puede gastar todo el presupuesto; los siguientes solo usan lo que sobre.
    """
    deadline = time.perf_counter() + budget_s
    best: tuple[int, list[int]] | None = None
    for hood in _neighbourhoods(m, coef):
        left = deadline - time.perf_counter()
        if left < MIN_STEP_S:
            break
        keep = hood | m.included  # las incluidas, fuera de la ventana o no
        sub = m.model.clone()
        if best is not None:
            keep.update(c for c, u in enumerate(m.used) if best[1][u.index])
            _set_hint(sub, best[1])
        for c, u in enumerate(m.used):
            if c not in keep:
                sub.add(sub.get_int_var_from_proto_index(u.index) == 0)
        _, objective, values = _run_solver(sub, left)
        if values is not None and (best is None or objective < best[0]):
            best = (objective, values)
    return best


def _objective_coefficients(
    m: SbcModel, objective_terms: list[tuple[int, cp_model.IntVar]]
) -> list[int]:
    coef = [0] * len(m.cards)
    card_of = {u.index: c for c, u in enumerate(m.used)}
    for k, var in objective_terms:
        if var.index in card_of:
            coef[card_of[var.index]] += k
    return coef


def solve_model(
    m: SbcModel,
    objective_terms: list[tuple[int, cp_model.IntVar]],
    time_limit_s: float,
) -> tuple[str, list[Assignment], float]:
    start = time.perf_counter()
    restricted: tuple[int, list[int]] | None = None
    if objective_terms:
        m.model.minimize(sum(coef * var for coef, var in objective_terms))
        if len(m.cards) >= RESTRICTED_MIN_CARDS:
            budget = min(RESTRICTED_MAX_S, RESTRICTED_SHARE * time_limit_s)
            coef = _objective_coefficients(m, objective_terms)
            restricted = _restricted_phase(m, coef, budget)
            if restricted is not None:
                _set_hint(m.model, restricted[1])
    status, objective, values = _run_solver(m.model, time_limit_s - (time.perf_counter() - start))
    elapsed = time.perf_counter() - start

    if status == cp_model.MODEL_INVALID:
        raise ValueError(f"Modelo CP-SAT inválido: {m.model.validate()}")
    if status == cp_model.OPTIMAL:
        name = "optimal"
    elif restricted is not None and (values is None or restricted[0] < objective):
        # El solve completo no mejoró la solución de la fase restringida (o no
        # encontró ninguna en su tiempo): esa solución es válida para el modelo
        # completo, pero sin prueba de optimalidad.
        name, values = "feasible", restricted[1]
    elif status == cp_model.FEASIBLE:
        name = "feasible"
    elif status == cp_model.INFEASIBLE:
        return "infeasible", [], elapsed
    else:
        return "unknown", [], elapsed

    assert values is not None
    return name, _assignments(m, values), elapsed


def _assignments(m: SbcModel, values: list[int]) -> list[Assignment]:
    """Cartas elegidas → huecos concretos. Si la clave es el hueco (int, modelo en
    posición) ya es directa; si es la posición (str, modelo por cupos) se reparten
    las cartas de cada posición en sus huecos (cada posición tiene su cupo lleno)."""
    chosen = [(c, key) for (c, key), var in m.x.items() if values[var.index]]
    assignments: list[Assignment] = []
    if chosen and isinstance(chosen[0][1], int):
        for c, s in chosen:
            assignments.append(
                Assignment(slot_index=s, position=m.slots[s], card_id=m.cards[c].card_id)
            )
    else:
        free: dict[str, list[int]] = defaultdict(list)
        for s, pos in enumerate(m.slots):
            free[pos].append(s)
        for c, p in chosen:
            s = free[p].pop()
            assignments.append(Assignment(slot_index=s, position=p, card_id=m.cards[c].card_id))
    assignments.sort(key=lambda a: a.slot_index)
    return assignments
