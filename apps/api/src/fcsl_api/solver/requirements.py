"""Traducción de requisitos SBC a restricciones CP-SAT sobre un `SbcModel`."""

from collections import defaultdict
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


def _rating_le(m: SbcModel, s: int) -> cp_model.IntVar:
    """Literal le_s ⇔ sum_rating ≤ s, cacheado por modelo (compartido entre requisitos)."""
    if m.rating_le is None:
        m.rating_le = {}
    if s not in m.rating_le:
        b = m.model.new_bool_var(f"sum_rating_le_{s}")
        m.model.add(m.sum_rating <= s).only_enforce_if(b)
        m.model.add(m.sum_rating >= s + 1).only_enforce_if(~b)
        m.rating_le[s] = b
    return m.rating_le[s]


def _team_rating(m: SbcModel, req: Requirement) -> None:
    # team_rating = floor((S + Σ max(0, r_c − S/n)) / n). Multiplicando por n²:
    #   team_rating ≥ v  ⇔  g_S ≥ n²·v        team_rating ≤ v  ⇔  g_S < n²·(v + 1)
    # con g_s = n·s + Σ_c max(0, n·r_c − s)·used_c, lineal para s fijo.
    # Como se usan exactamente n cartas, g_s es no decreciente en s (pendiente
    # n − #{c usada: n·r_c > s} ≥ 0). Por eso, sin perder exactitud:
    #   min: (S ≤ s) ⇒ g_s ≥ n²·v        para cada s posible (en s = S es la definición)
    #   max: (S ≥ s) ⇒ g_s < n²·(v + 1)
    # Estas implicaciones con literales de orden sobre S dan una relajación mucho
    # más fuerte que modelar max(0, ·) con variables auxiliares.
    n = len(m.slots)
    ratings = sorted(card.rating for card in m.cards)
    s_lo, s_hi = sum(ratings[:n]), sum(ratings[-n:])  # cotas de S

    def g(s: int) -> cp_model.LinearExprT:
        above = [c for c, card in enumerate(m.cards) if n * card.rating > s]
        return n * s + cp_model.LinearExpr.weighted_sum(
            [m.used[c] for c in above], [n * m.cards[c].rating - s for c in above]
        )

    if req.op in ("min", "exact"):
        target = n * n * req.value
        # Mejor caso de g_s: las n cartas con mayor exceso. Si ni así llega, S > s.
        excess_desc = sorted(ratings, reverse=True)[:n]
        s_start = s_lo
        while s_start < n * req.value and n * s_start + sum(
            max(0, n * r - s_start) for r in excess_desc
        ) < target:
            s_start += 1
        m.model.add(m.sum_rating >= s_start)
        # Para s ≥ n·v, g_s ≥ n·s ≥ n²·v se cumple solo.
        for s in range(s_start, min(s_hi, n * req.value - 1) + 1):
            m.model.add(g(s) >= target).only_enforce_if(_rating_le(m, s))
    if req.op in ("max", "exact"):
        bound = n * n * (req.value + 1) - 1
        # Para s ≥ n·(v + 1), g_s ≥ n·s > bound: S no puede llegar ahí.
        m.model.add(m.sum_rating <= n * (req.value + 1) - 1)
        for s in range(s_lo, min(s_hi, n * (req.value + 1) - 1) + 1):
            m.model.add(g(s) <= bound).only_enforce_if(~_rating_le(m, s - 1))


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
