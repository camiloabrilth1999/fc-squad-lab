"""Plan multi-set: qué grado completar en cada set para conseguir fichas al menor coste.

Cada set ofrece una opción por grado (D…S) con sus fichas ganadas, el impuesto (5 % de lo que
se compra), el nº de compras y las monedas que hay que tener a mano. El plan elige a lo sumo una
opción por set. Aproximación: los sets se resuelven por separado, así que una carta que está a la
vez en un set de club y en uno de liga se cuenta en cada uno.
"""

from dataclasses import dataclass, field
from datetime import datetime

from ortools.sat.python import cp_model
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..models_db import Price
from .service import collected_ids, current_grade, load_pool, progress, solve_set
from .sets import GallerySet, load_sets

_REACHABLE = ("optimal", "feasible", "reached")


@dataclass(frozen=True)
class Option:
    grade: str
    tokens: int  # fichas nuevas respecto a lo que ya tienes en el set
    points: int
    cost: int
    tax: int
    buys: int
    coins_needed: int


@dataclass
class SetOptions:
    set: GallerySet
    current: str | None
    options: list[Option] = field(default_factory=list)


@dataclass
class PlanItem:
    set: GallerySet
    from_grade: str | None
    option: Option


@dataclass
class PlanResult:
    status: str  # optimal | feasible | infeasible | unknown
    items: list[PlanItem] = field(default_factory=list)
    tokens: int = 0
    tax: int = 0
    cost: int = 0
    transfers: int = 0
    coins_needed: int = 0
    max_tokens: int = 0  # lo máximo alcanzable con esas restricciones (si es inalcanzable)


_cache: dict[tuple[object, ...], list[SetOptions]] = {}


def _cumulative(s: GallerySet) -> dict[str, int]:
    out: dict[str, int] = {}
    total = 0
    for g in s.grades:
        total += g.tokens
        out[g.name] = total
    return out


def build_options(session: Session, *, complete: bool = True) -> list[SetOptions]:
    """Opciones por set; cacheadas mientras no cambien lo coleccionado ni los precios."""
    collected = collected_ids(session)
    last_price: datetime | None = session.scalar(select(func.max(Price.captured_at)))
    key = (frozenset(collected), last_price, complete)
    if key in _cache:
        return _cache[key]

    sets = list(load_sets())
    done = progress(session, sets)
    result: list[SetOptions] = []
    for s in sets:
        cur = current_grade(s, done[s.id][1])
        cum = _cumulative(s)
        have = cum.get(cur, 0) if cur else 0
        entry = SetOptions(set=s, current=cur)
        pool = load_pool(session, s, collected)
        for g in s.grades:
            gain = cum[g.name] - have
            if gain <= 0:
                continue  # ya lo tienes, o no da fichas nuevas
            sel = solve_set(pool, s.required, g.threshold, complete=complete, time_limit_s=2.0)
            if sel.status not in _REACHABLE:
                continue
            entry.options.append(
                Option(
                    grade=g.name,
                    tokens=gain,
                    points=sel.points,
                    cost=sel.cost,
                    tax=sel.tax,
                    buys=sel.buys,
                    coins_needed=sel.coins_needed,
                )
            )
        result.append(entry)
    _cache.clear()  # una sola entrada: el club y los precios actuales
    _cache[key] = result
    return result


def plan(
    sets: list[SetOptions],
    *,
    target_tokens: int | None = None,
    max_tax: int | None = None,
    max_transfers: int | None = None,
    max_sets: int | None = None,
    max_coins: int | None = None,
    time_limit_s: float = 10.0,
) -> PlanResult:
    """Con `target_tokens`: mínimo impuesto que llega a esas fichas. Sin él: máximas fichas."""
    usable = [
        (so, [o for o in so.options if max_coins is None or o.coins_needed <= max_coins])
        for so in sets
    ]
    usable = [(so, opts) for so, opts in usable if opts]

    model = cp_model.CpModel()
    y: dict[tuple[int, int], cp_model.IntVar] = {}
    for i, (_, opts) in enumerate(usable):
        for j in range(len(opts)):
            y[i, j] = model.new_bool_var(f"y{i}_{j}")
        model.add_at_most_one(y[i, j] for j in range(len(opts)))

    def total(attr: str) -> cp_model.LinearExpr:
        return sum(
            getattr(opts[j], attr) * y[i, j]
            for i, (_, opts) in enumerate(usable)
            for j in range(len(opts))
        )

    tokens, tax, transfers = total("tokens"), total("tax"), total("buys")
    n_sets = sum(y.values())
    if max_tax is not None:
        model.add(tax <= max_tax)
    if max_transfers is not None:
        model.add(transfers <= max_transfers)
    if max_sets is not None:
        model.add(n_sets <= max_sets)

    ceiling = sum(max((o.tokens for o in opts), default=0) for _, opts in usable)
    if target_tokens is not None:
        model.add(tokens >= target_tokens)
        model.minimize(1000 * tax + transfers)
    else:
        model.maximize(1_000_000 * tokens - 1000 * tax - transfers)

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = time_limit_s
    solver.parameters.num_workers = 4
    status = solver.solve(model)
    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        res = PlanResult(status="infeasible" if status == cp_model.INFEASIBLE else "unknown")
        res.max_tokens = (
            _max_within(usable, max_tax, max_transfers, max_sets) if target_tokens else ceiling
        )
        return res

    items = [
        PlanItem(set=so.set, from_grade=so.current, option=opts[j])
        for i, (so, opts) in enumerate(usable)
        for j in range(len(opts))
        if solver.value(y[i, j])
    ]
    items.sort(key=lambda it: it.option.tax / max(it.option.tokens, 1))
    return PlanResult(
        status="optimal" if status == cp_model.OPTIMAL else "feasible",
        items=items,
        tokens=sum(it.option.tokens for it in items),
        tax=sum(it.option.tax for it in items),
        cost=sum(it.option.cost for it in items),
        transfers=sum(it.option.buys for it in items),
        coins_needed=max((it.option.coins_needed for it in items), default=0),
        max_tokens=ceiling,
    )


def _max_within(
    usable: list[tuple[SetOptions, list[Option]]],
    max_tax: int | None,
    max_transfers: int | None,
    max_sets: int | None,
) -> int:
    """Fichas máximas con los límites dados (para explicar un objetivo inalcanzable)."""
    res = plan(
        [SetOptions(set=so.set, current=so.current, options=opts) for so, opts in usable],
        max_tax=max_tax,
        max_transfers=max_transfers,
        max_sets=max_sets,
        time_limit_s=5.0,
    )
    return res.tokens
