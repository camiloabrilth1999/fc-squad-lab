"""Squad Builder sobre tu club: meta de cada carta desde sus stats guardados."""

from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..meta.compute import compute_meta
from ..meta.roles import role_for
from ..models_db import Card as CardRow
from ..models_db import CardAttributes
from ..sbc import formations
from ..sbc.pool import club_cards
from ..solver.models import Card
from .builder import DEFAULT_CHEM_WEIGHT, build_squad


class SquadBuildRequest(BaseModel):
    formation: str = formations.DEFAULT_FORMATION
    chem_weight: float = Field(default=DEFAULT_CHEM_WEIGHT, ge=0, le=20)
    min_chemistry: int = Field(default=0, ge=0, le=33)
    # none = solo en posición; family = también en posiciones de su misma familia de rol
    # (p. ej. un LW en LM/RM); any = cualquier posición de campo (portero siempre aparte)
    out_of_position: Literal["none", "family", "any"] = "family"
    max_out_of_position: int | None = Field(default=None, ge=0, le=10)
    exclude_card_ids: list[str] = Field(default_factory=list)
    time_limit_s: float = Field(default=10.0, gt=0, le=60)


class SquadSlot(BaseModel):
    slot_index: int
    position: str
    card_id: str
    resource_id: int
    name: str
    rating: int
    meta: float
    meta_source: Literal["stats", "rating"]  # "rating" = sin stats (o portero): se usa el rating
    chemistry: int
    in_position: bool = True


class SquadBuildResponse(BaseModel):
    status: Literal["optimal", "feasible", "infeasible", "unknown"]
    formation: str
    slots: list[SquadSlot] = Field(default_factory=list)
    total_meta: float = 0.0
    team_rating: int = 0
    team_chemistry: int = 0
    solve_time_s: float = 0.0
    message: str | None = None


def _allowed_positions(card: Card, slot_positions: set[str], mode: str) -> set[str]:
    """Posiciones de la formación donde puede jugar la carta según el modo."""
    own = set(card.positions)
    gk = "GK" in own
    if mode == "none" or gk:
        return own & slot_positions if gk else own
    if mode == "any":
        return {p for p in slot_positions if p != "GK"} | own
    family = role_for(card.positions[0])
    return {p for p in slot_positions if p != "GK" and role_for(p) == family} | own


def build_club_squad(session: Session, req: SquadBuildRequest) -> SquadBuildResponse:
    formation = formations.normalize(req.formation)
    slots = formations.slots_for(formation)
    cards = club_cards(session, datetime.now(UTC))
    stats = {
        rid: s
        for rid, s in session.execute(select(CardAttributes.resource_id, CardAttributes.stats))
    }
    rows = {
        r.resource_id: r
        for r in session.scalars(
            select(CardRow).where(CardRow.resource_id.in_({c.resource_id for c in cards}))
        )
    }
    slot_positions = set(slots)
    allowed: dict[str, set[str]] = {}
    meta: dict[str, dict[str, float]] = {}
    source: dict[str, Literal["stats", "rating"]] = {}
    for card in cards:
        row = rows.get(card.resource_id) or card
        card_stats = stats.get(card.resource_id)
        allowed[card.card_id] = _allowed_positions(card, slot_positions, req.out_of_position)
        by_pos: dict[str, float] = {}
        for p in allowed[card.card_id] | set(card.positions):
            m = compute_meta(
                card_stats,
                row,
                role=role_for(p) if p in slot_positions else None,
                fallback_rating=card.rating,
            )
            by_pos[p] = round(m.value if m.value is not None else float(card.rating), 1)
            if p == card.positions[0]:
                source[card.card_id] = m.source
        meta[card.card_id] = by_pos
        source.setdefault(card.card_id, "rating")

    result = build_squad(
        cards,
        meta,
        slots,
        allowed=allowed,
        max_out_of_position=req.max_out_of_position,
        chem_weight=req.chem_weight,
        min_chemistry=req.min_chemistry,
        exclude_card_ids=req.exclude_card_ids,
        time_limit_s=req.time_limit_s,
    )
    by_id = {c.card_id: c for c in cards}
    out = [
        SquadSlot(
            slot_index=a.slot_index,
            position=a.position,
            card_id=a.card_id,
            resource_id=by_id[a.card_id].resource_id,
            name=by_id[a.card_id].name,
            rating=by_id[a.card_id].rating,
            meta=meta[a.card_id].get(a.position, 0.0),
            meta_source=source[a.card_id],
            chemistry=result.player_chemistry.get(a.card_id, 0),
            in_position=a.position in by_id[a.card_id].positions,
        )
        for a in result.assignments
    ]
    return SquadBuildResponse(
        status=result.status,
        formation=formation,
        slots=out,
        total_meta=result.total_meta,
        team_rating=result.team_rating,
        team_chemistry=result.team_chemistry,
        solve_time_s=result.solve_time_s,
        message=result.message,
    )
