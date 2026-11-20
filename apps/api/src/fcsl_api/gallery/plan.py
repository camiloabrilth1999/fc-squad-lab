"""Plan multi-set: qué grado completar en cada set para conseguir fichas al menor coste.

Cada set ofrece una opción por grado (D…S) con sus fichas ganadas, el impuesto (5 % de lo que
se compra), el nº de compras y las monedas que hay que tener a mano. El plan elige a lo sumo una
opción por set.

Cartas compartidas: una carta que está a la vez en un set de club y en uno de liga se compra una
sola vez. `make_plan` parte del plan con los sets independientes y lo refina: resuelve los sets en
orden y cada uno reutiliza (gratis) lo que ya se compró en los anteriores, y vuelve a planificar
con esos costes mientras mejore. El resultado final siempre es un plan válido en ese orden.
"""

from dataclasses import dataclass, field, replace
from datetime import datetime

from ortools.sat.python import cp_model
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..models_db import Price
from .service import PoolCard, collected_ids, current_grade, load_pool, progress, solve_set
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
    bought: frozenset[int] = frozenset()  # cartas que hay que comprar


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
    independent_tax: int = 0  # impuesto si cada set se resolviera por separado


@dataclass
class Built:
    """Opciones por set y sus pools, para poder volver a resolver con cartas compartidas."""

    complete: bool
    options: list[SetOptions]
    pools: dict[int, list[PoolCard]]
    pool_ids: dict[int, frozenset[int]]
    gains: dict[tuple[int, str], int]  # (set, grado) → fichas nuevas
    plans: dict[tuple[int | None, ...], PlanResult] = field(default_factory=dict)  # memoria


_cache: dict[tuple[object, ...], Built] = {}


def _cumulative(s: GallerySet) -> dict[str, int]:
    out: dict[str, int] = {}
    total = 0
    for g in s.grades:
        total += g.tokens
        out[g.name] = total
    return out


def _option(
    s: GallerySet,
    pool: list[PoolCard],
    grade: str,
    threshold: int,
    gain: int,
    complete: bool,
    extra: frozenset[int] = frozenset(),
) -> Option | None:
    """Opción de un grado; las cartas de `extra` cuentan como ya coleccionadas (compartidas)."""
    if extra:
        pool = [replace(c, collected=True) if c.resource_id in extra else c for c in pool]
    sel = solve_set(pool, s.required, threshold, complete=complete, time_limit_s=2.0)
    if sel.status not in _REACHABLE:
        return None
    return Option(
        grade=grade,
        tokens=gain,
        points=sel.points,
        cost=sel.cost,
        tax=sel.tax,
        buys=sel.buys,
        coins_needed=sel.coins_needed,
        bought=frozenset(c.resource_id for c in sel.cards if not c.collected),
    )


def build(session: Session, *, complete: bool = True) -> Built:
    """Opciones por set; cacheadas mientras no cambien lo coleccionado ni los precios."""
    collected = collected_ids(session)
    last_price: datetime | None = session.scalar(select(func.max(Price.captured_at)))
    key = (frozenset(collected), last_price, complete)
    if key in _cache:
        return _cache[key]

    sets = list(load_sets())
    done = progress(session, sets)
    options: list[SetOptions] = []
    pools: dict[int, list[PoolCard]] = {}
    gains: dict[tuple[int, str], int] = {}
    for s in sets:
        cur = current_grade(s, done[s.id][1])
        cum = _cumulative(s)
        have = cum.get(cur, 0) if cur else 0
        entry = SetOptions(set=s, current=cur)
        pool = load_pool(session, s, collected)
        pools[s.id] = pool
        for g in s.grades:
            gain = cum[g.name] - have
            if gain <= 0:
                continue  # ya lo tienes, o no da fichas nuevas
            gains[s.id, g.name] = gain
            opt = _option(s, pool, g.name, g.threshold, gain, complete)
            if opt is not None:
                entry.options.append(opt)
        options.append(entry)
    built = Built(
        complete=complete,
        options=options,
        pools=pools,
        pool_ids={sid: frozenset(c.resource_id for c in p) for sid, p in pools.items()},
        gains=gains,
    )
    _cache.clear()  # una sola entrada: el club y los precios actuales
    _cache[key] = built
    return built


def build_options(session: Session, *, complete: bool = True) -> list[SetOptions]:
    return build(session, complete=complete).options


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


def _totals(items: list[PlanItem], base: PlanResult) -> PlanResult:
    return PlanResult(
        status=base.status,
        items=items,
        tokens=sum(it.option.tokens for it in items),
        tax=sum(it.option.tax for it in items),
        cost=sum(it.option.cost for it in items),
        transfers=sum(it.option.buys for it in items),
        coins_needed=max((it.option.coins_needed for it in items), default=0),
        max_tokens=base.max_tokens,
        independent_tax=base.independent_tax,
    )


def _sequential(built: Built, items: list[PlanItem]) -> list[PlanItem]:
    """Resuelve los sets del plan en orden; cada uno reutiliza lo comprado en los anteriores."""
    ordered = sorted(items, key=lambda it: (-it.set.required, it.option.tax))
    extra: set[int] = set()
    out: list[PlanItem] = []
    for it in ordered:
        threshold = next(g.threshold for g in it.set.grades if g.name == it.option.grade)
        opt = _option(
            it.set,
            built.pools[it.set.id],
            it.option.grade,
            threshold,
            it.option.tokens,
            built.complete,
            frozenset(extra),
        )
        if opt is None:  # no debería pasar: más cartas gratis nunca empeoran un set
            opt = it.option
        out.append(PlanItem(set=it.set, from_grade=it.from_grade, option=opt))
        extra |= opt.bought
    return out


def _shared_options(built: Built, items: list[PlanItem]) -> list[SetOptions]:
    """Opciones de todos los sets suponiendo que ya se compró lo del resto del plan."""
    bought: dict[int, frozenset[int]] = {it.set.id: it.option.bought for it in items}
    out: list[SetOptions] = []
    for so in built.options:
        extra = frozenset().union(*(b for sid, b in bought.items() if sid != so.set.id))
        if not extra & built.pool_ids[so.set.id]:
            out.append(so)  # nada compartido: mismas opciones
            continue
        entry = SetOptions(set=so.set, current=so.current)
        for g in so.set.grades:
            gain = built.gains.get((so.set.id, g.name))
            if gain is None:
                continue
            opt = _option(
                so.set, built.pools[so.set.id], g.name, g.threshold, gain, built.complete, extra
            )
            if opt is not None:
                entry.options.append(opt)
        out.append(entry)
    return out


def _meets(
    res: PlanResult,
    target_tokens: int | None,
    max_tax: int | None,
    max_transfers: int | None,
    max_sets: int | None,
    max_coins: int | None,
) -> bool:
    return (
        (target_tokens is None or res.tokens >= target_tokens)
        and (max_tax is None or res.tax <= max_tax)
        and (max_transfers is None or res.transfers <= max_transfers)
        and (max_sets is None or len(res.items) <= max_sets)
        and (max_coins is None or res.coins_needed <= max_coins)
    )


def _score(res: PlanResult, target_tokens: int | None) -> tuple[int, int, int]:
    """Mayor es mejor: con objetivo, menos impuesto; sin él, más fichas y luego menos impuesto."""
    if target_tokens is not None:
        return (0, -res.tax, -res.transfers)
    return (res.tokens, -res.tax, -res.transfers)


def make_plan(
    built: Built,
    *,
    target_tokens: int | None = None,
    max_tax: int | None = None,
    max_transfers: int | None = None,
    max_sets: int | None = None,
    max_coins: int | None = None,
    rounds: int = 3,
) -> PlanResult:
    """Plan con cartas compartidas entre sets (ver la cabecera del módulo)."""
    limits = {
        "target_tokens": target_tokens,
        "max_tax": max_tax,
        "max_transfers": max_transfers,
        "max_sets": max_sets,
        "max_coins": max_coins,
    }
    memo_key = (*limits.values(), rounds)
    if memo_key in built.plans:
        return built.plans[memo_key]
    first = plan(built.options, **limits)
    if first.status not in ("optimal", "feasible"):
        return first
    first.independent_tax = first.tax
    best = _totals(_sequential(built, first.items), first)
    for _ in range(rounds):
        trial = plan(_shared_options(built, best.items), **limits)
        if trial.status not in ("optimal", "feasible"):
            break
        trial.independent_tax = first.independent_tax
        cand = _totals(_sequential(built, trial.items), trial)
        if not _meets(cand, **limits) or _score(cand, target_tokens) <= _score(best, target_tokens):
            break
        best = cand
    built.plans[memo_key] = best
    return best
