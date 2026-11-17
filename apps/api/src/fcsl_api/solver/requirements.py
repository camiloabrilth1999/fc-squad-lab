"""Traducción de requisitos SBC a restricciones CP-SAT sobre un `SbcModel`."""

from collections import Counter, defaultdict
from collections.abc import Callable

from ortools.sat.python import cp_model

from .cpsat import SbcModel, add_chemistry
from .models import Card, Requirement, RequirementKind

LEVELS = frozenset({"bronze", "silver", "gold"})

# Familia de grupo -> atributo de la carta. Iconos y héroes cuentan por sus
# propios ids y con peso 1 (los pesos dobles son solo de química).
_GROUP_ATTR = {"league": "league_id", "nation": "nation_id", "club": "club_id"}


def apply_requirement(m: SbcModel, req: Requirement) -> None:
    """Añade al modelo las restricciones de `req` (despacha por `req.kind`)."""
    handler = _HANDLERS.get(req.kind)
    if handler is None:
        raise NotImplementedError(f"Requirement kind {req.kind} not implemented yet")
    handler(m, req)
    m.requirements.append(req)


def _rating_counts(m: SbcModel) -> dict[int, cp_model.IntVar]:
    """k_r = nº de cartas usadas con rating r, cacheado por modelo (compartido)."""
    if m.rating_count is None:
        n = len(m.slots)
        by_rating: dict[int, list[int]] = defaultdict(list)
        for c, card in enumerate(m.cards):
            by_rating[card.rating].append(c)
        m.rating_count = {}
        for r, idxs in sorted(by_rating.items()):
            count = m.model.new_int_var(0, min(n, len(idxs)), f"rating_count_{r}")
            m.model.add(count == sum(m.used[c] for c in idxs))
            m.rating_count[r] = count
    return m.rating_count


def _team_rating(m: SbcModel, req: Requirement) -> None:
    # team_rating = floor((S + Σ max(0, r_c − S/n)) / n). Multiplicando por n²:
    #   team_rating ≥ v  ⇔  g_S ≥ n²·v        team_rating ≤ v  ⇔  g_S ≤ n²·(v + 1) − 1
    # con g_d = n·d + Σ_r max(0, n·r − d)·k_r, lineal en los conteos k_r para d fijo.
    # Solo depende de los conteos por rating, así que se modela como disyunción
    # sobre el valor d de S en forma de envolvente convexa (Balas): una copia de
    # los conteos k^d por disyunción activa e_d, con Σ_d e_d = 1 y k = Σ_d k^d.
    # Es exacta (en una solución entera solo la disyunción activa tiene k^d = k) y
    # su relajación lineal es mucho más fuerte que los literales de orden.
    #
    # Para acotar las disyunciones, opt(d) = n·d + Σ max(0, n·r − d) sobre los n
    # mejores ratings es una cota superior de g_d para cualquier equipo y es no
    # decreciente en d (pendiente n − #{n·r > d} ≥ 0); además g_d ≥ n·d siempre.
    #   min: d con opt(d) < n²·v es imposible; d ≥ n·v se cumple solo (una
    #        disyunción "alta" con S ≥ n·v).
    #   max: d > ⌊tope / n⌋ es imposible; d con opt(d) ≤ tope se cumple solo (una
    #        disyunción "baja" con S ≤ d_bajo).
    n = len(m.slots)
    by_rating = sorted((card.rating for card in m.cards), reverse=True)
    if len(by_rating) < n:
        return  # el modelo base ya es infactible: no hay cartas para todos los huecos
    k = _rating_counts(m)
    ratings = sorted(k)
    available = Counter(by_rating)
    top = by_rating[:n]
    s_lo, s_hi = sum(by_rating[-n:]), sum(top)

    def opt(d: int) -> int:
        return n * d + sum(max(0, n * r - d) for r in top)

    want_lo = req.op in ("min", "exact")
    want_hi = req.op in ("max", "exact")
    target = n * n * req.value  # g_S ≥ target
    cap = n * n * (req.value + 1) - 1  # g_S ≤ cap
    d_from, d_to = s_lo, s_hi
    high = low = None  # rangos [a, b] resueltos con una sola disyunción
    if want_lo:
        while d_from <= d_to and opt(d_from) < target:
            d_from += 1
        if not want_hi and max(d_from, n * req.value) <= s_hi:
            high = (max(d_from, n * req.value), s_hi)
            d_to = high[0] - 1
    if want_hi:
        d_to = min(d_to, cap // n)
        if not want_lo:
            d_low = d_from - 1
            while d_low + 1 <= d_to and opt(d_low + 1) <= cap:
                d_low += 1
            if d_low >= d_from:
                low = (d_from, d_low)
                d_from = d_low + 1

    model = m.model
    tag = f"{req.op}_{req.value}"
    parts: dict[int, list[cp_model.IntVar]] = {r: [] for r in ratings}
    choices: list[cp_model.IntVar] = []

    def branch(name: str) -> tuple[cp_model.IntVar, dict[int, cp_model.IntVar]]:
        e = model.new_bool_var(f"team_rating_{tag}_{name}")
        kd = {}
        for r in ratings:
            ub = min(n, available[r])
            kd[r] = model.new_int_var(0, ub, f"team_rating_{tag}_{name}_k{r}")
            model.add(kd[r] <= ub * e)
            parts[r].append(kd[r])
        model.add(sum(kd.values()) == n * e)
        choices.append(e)
        return e, kd

    for d in range(d_from, d_to + 1):
        e, kd = branch(str(d))
        model.add(sum(r * kd[r] for r in ratings) == d * e)
        excess = sum(max(0, n * r - d) * kd[r] for r in ratings)
        if want_lo and n * d < target:
            model.add(excess >= (target - n * d) * e)
        if want_hi:
            model.add(excess <= (cap - n * d) * e)
    for name, rng in (("high", high), ("low", low)):
        if rng is not None:
            e, kd = branch(name)
            total = sum(r * kd[r] for r in ratings)
            model.add(total >= rng[0] * e)
            model.add(total <= rng[1] * e)

    model.add_exactly_one(choices)  # sin disyunciones posibles: infactible
    for r in ratings:
        model.add(k[r] == sum(parts[r]))


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


def _bound(m: SbcModel, expr: cp_model.LinearExprT, op: str, value: int) -> None:
    if op in ("min", "exact"):
        m.model.add(expr >= value)
    if op in ("max", "exact"):
        m.model.add(expr <= value)


def _count_where(m: SbcModel, pred: Callable[[Card], bool]) -> cp_model.LinearExprT:
    return sum(m.used[c] for c, card in enumerate(m.cards) if pred(card))


def _groups(m: SbcModel, family: str) -> dict[int, list[int]]:
    """id de grupo -> índices de carta de ese grupo."""
    attr = _GROUP_ATTR[family]
    members: dict[int, list[int]] = defaultdict(list)
    for c, card in enumerate(m.cards):
        members[getattr(card, attr)].append(c)
    return members


def _group_present(m: SbcModel, family: str) -> dict[int, cp_model.IntVar]:
    """present_g ⇔ Σ used del grupo ≥ 1 (equivalencia), cacheado por familia."""
    if m.group_present is None:
        m.group_present = {}
    if family not in m.group_present:
        present: dict[int, cp_model.IntVar] = {}
        for gid, idxs in _groups(m, family).items():
            p = m.model.new_bool_var(f"present_{family}_{gid}")
            count = sum(m.used[c] for c in idxs)
            m.model.add(count >= 1).only_enforce_if(p)
            m.model.add(count == 0).only_enforce_if(~p)
            present[gid] = p
        m.group_present[family] = present
    return m.group_present[family]


def _players_by_id(family: str) -> Callable[[SbcModel, Requirement], None]:
    attr = _GROUP_ATTR[family]

    def handler(m: SbcModel, req: Requirement) -> None:
        if not req.ids:
            raise ValueError(f"{req.kind} requiere ids no vacíos")
        ids = set(req.ids)
        _bound(m, _count_where(m, lambda card: getattr(card, attr) in ids), req.op, req.value)

    return handler


def _distinct(family: str) -> Callable[[SbcModel, Requirement], None]:
    def handler(m: SbcModel, req: Requirement) -> None:
        _bound(m, sum(_group_present(m, family).values()), req.op, req.value)

    return handler


def _same(family: str) -> Callable[[SbcModel, Requirement], None]:
    # min: algún grupo con ≥ value; max: ningún grupo > value;
    # exact: ningún grupo > value y alguno con ≥ value (el mayor tiene value).
    def handler(m: SbcModel, req: Requirement) -> None:
        groups = _groups(m, family)
        counts = {gid: sum(m.used[c] for c in idxs) for gid, idxs in groups.items()}
        if req.op in ("max", "exact"):
            for count in counts.values():
                m.model.add(count <= req.value)
        if req.op in ("min", "exact"):
            picks = []
            for gid, count in counts.items():
                pick = m.model.new_bool_var(f"same_{family}_{gid}_{req.value}")
                m.model.add(count >= req.value).only_enforce_if(pick)
                picks.append(pick)
            m.model.add_bool_or(picks)

    return handler


def _level_players(m: SbcModel, req: Requirement) -> None:
    levels = set(req.tags)
    if not levels or not levels <= LEVELS:
        raise ValueError(
            f"LEVEL_PLAYERS requiere tags no vacíos dentro de {sorted(LEVELS)}, no {req.tags!r}"
        )
    _bound(m, _count_where(m, lambda card: card.level in levels), req.op, req.value)


def _rare_players(m: SbcModel, req: Requirement) -> None:
    _bound(m, _count_where(m, lambda card: card.rare), req.op, req.value)


def _tag_players(m: SbcModel, req: Requirement) -> None:
    if not req.tags:
        raise ValueError("TAG_PLAYERS requiere tags no vacíos")
    tags = set(req.tags)
    _bound(m, _count_where(m, lambda card: bool(tags & set(card.rarity_tags))), req.op, req.value)


_HANDLERS = {
    RequirementKind.TEAM_RATING: _team_rating,
    RequirementKind.PLAYER_RATING: _player_rating,
    RequirementKind.TEAM_CHEMISTRY: _team_chemistry,
    RequirementKind.PLAYER_CHEMISTRY: _player_chemistry,
    RequirementKind.LEAGUE_PLAYERS: _players_by_id("league"),
    RequirementKind.NATION_PLAYERS: _players_by_id("nation"),
    RequirementKind.CLUB_PLAYERS: _players_by_id("club"),
    RequirementKind.DISTINCT_LEAGUES: _distinct("league"),
    RequirementKind.DISTINCT_NATIONS: _distinct("nation"),
    RequirementKind.DISTINCT_CLUBS: _distinct("club"),
    RequirementKind.SAME_LEAGUE: _same("league"),
    RequirementKind.SAME_NATION: _same("nation"),
    RequirementKind.SAME_CLUB: _same("club"),
    RequirementKind.LEVEL_PLAYERS: _level_players,
    RequirementKind.RARE_PLAYERS: _rare_players,
    RequirementKind.TAG_PLAYERS: _tag_players,
}
