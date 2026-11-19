"""Cruce de las Evoluciones con tu club: candidatas, mejor evolución por carta y plan global."""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from ortools.sat.python import cp_model
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from ..models_db import Card, CardAttributes, Catalog, ClubItem, Evolution
from .projection import project_meta
from .requirements import Requirement, check, decode, describe, facts_for


@dataclass
class Match:
    """Una carta de tu club frente a una evolución."""

    item_id: int
    resource_id: int
    name: str | None
    rating: int | None
    positions: list[str]
    eligible: bool | None  # True cumple; None = falta algún dato para saberlo
    unknown: list[str] = field(default_factory=list)
    meta_before: float | None = None
    meta_after: float | None = None

    @property
    def meta_gain(self) -> float | None:
        if self.meta_before is None or self.meta_after is None:
            return None
        return round(self.meta_after - self.meta_before, 1)


def active_evolutions(session: Session, *, include_expired: bool = False) -> list[Evolution]:
    """Evoluciones guardadas; por defecto sin las ya caducadas."""
    stmt = select(Evolution).order_by(Evolution.category_id, Evolution.slot_id)
    if not include_expired:
        now = int(datetime.now(UTC).timestamp())
        stmt = stmt.where(
            or_(Evolution.end_time.is_(None), Evolution.end_time == 0, Evolution.end_time > now)
        )
    return list(session.scalars(stmt))


class ClubEvaluator:
    """Carga tu club una vez y lo evalúa contra cualquier evolución."""

    def __init__(self, session: Session) -> None:
        self.names = {(c.kind, c.ea_id): c.name for c in session.scalars(select(Catalog))}
        self.rows = session.execute(
            select(ClubItem, Card)
            .join(Card, Card.resource_id == ClubItem.resource_id)
            .where(ClubItem.location.is_distinct_from("watchlist"))
        ).all()
        self.stats = dict(
            session.execute(select(CardAttributes.resource_id, CardAttributes.stats)).all()
        )

    def requirements(self, evo: Evolution) -> tuple[list[Requirement], list[str]]:
        reqs = decode((evo.data or {}).get("requirements") or [])
        return reqs, [describe(r, self.names) for r in reqs]

    def _match(
        self,
        item: ClubItem,
        card: Card,
        reqs: list[Requirement],
        texts: list[str],
        levels: list[Any],
    ) -> Match | None:
        stats = self.stats.get(card.resource_id)
        facts = facts_for(card, stats, untradeable=item.untradeable)
        verdicts = [check(r, facts) for r in reqs]
        if any(v is False for v in verdicts):
            return None
        missing = [t for t, v in zip(texts, verdicts, strict=True) if v is None]
        before, after = project_meta(card, stats, levels)
        return Match(
            item_id=item.item_id,
            resource_id=card.resource_id,
            name=card.name,
            rating=card.rating,
            positions=card.positions or [],
            eligible=None if missing else True,
            unknown=missing,
            meta_before=round(before, 1) if before is not None else None,
            meta_after=round(after, 1) if after is not None else None,
        )

    def matches(self, evo: Evolution) -> list[Match]:
        """Cartas del club que no incumplen ningún requisito (con o sin datos completos)."""
        reqs, texts = self.requirements(evo)
        levels = (evo.data or {}).get("levels") or []
        found = (self._match(item, card, reqs, texts, levels) for item, card in self.rows)
        return [m for m in found if m is not None]

    def for_card(
        self, item_id: int, evos: list[Evolution]
    ) -> tuple[Card | None, list[tuple[Evolution, Match]]]:
        """Evoluciones que esta carta puede tomar."""
        for item, card in self.rows:
            if item.item_id != item_id:
                continue
            out: list[tuple[Evolution, Match]] = []
            for evo in evos:
                reqs, texts = self.requirements(evo)
                m = self._match(item, card, reqs, texts, (evo.data or {}).get("levels") or [])
                if m is not None:
                    out.append((evo, m))
            return card, out
        return None, []


def plan(
    pairs: list[tuple[Evolution, Match]], *, min_after: float = 0.0, time_limit_s: float = 5.0
) -> list[tuple[Evolution, Match]]:
    """Asignación óptima: cada evolución a una carta y cada carta a una evolución como mucho,
    maximizando la mejora total de meta. Solo cuentan cartas aptas y proyectables."""
    usable = [
        (e, m)
        for e, m in pairs
        if m.eligible is True
        and m.meta_gain is not None
        and m.meta_gain > 0
        and (m.meta_after or 0) >= min_after
    ]
    if not usable:
        return []
    model = cp_model.CpModel()
    x = [model.new_bool_var(f"x_{i}") for i in range(len(usable))]
    by_evo: dict[int, list[int]] = {}
    by_item: dict[int, list[int]] = {}
    for i, (e, m) in enumerate(usable):
        by_evo.setdefault(e.slot_id, []).append(i)
        by_item.setdefault(m.item_id, []).append(i)
    for idxs in (*by_evo.values(), *by_item.values()):
        model.add(sum(x[i] for i in idxs) <= 1)
    model.maximize(
        sum(round((usable[i][1].meta_gain or 0) * 10) * x[i] for i in range(len(usable)))
    )
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = time_limit_s
    solver.parameters.random_seed = 0
    status = solver.solve(model)
    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return []
    chosen = [usable[i] for i in range(len(usable)) if solver.value(x[i])]
    return sorted(chosen, key=lambda p: -(p[1].meta_gain or 0))
