"""Squad Builder sobre tu club: meta de cada carta desde sus stats guardados."""

from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..meta.attributes import STATS, PlayerAttributes
from ..meta.rating import meta_rating
from ..meta.roles import role_for
from ..models_db import CardAttributes
from ..sbc import formations
from ..sbc.pool import club_cards
from ..solver.models import Card
from .builder import DEFAULT_CHEM_WEIGHT, build_squad


class SquadBuildRequest(BaseModel):
    formation: str = formations.DEFAULT_FORMATION
    chem_weight: float = Field(default=DEFAULT_CHEM_WEIGHT, ge=0, le=20)
    min_chemistry: int = Field(default=0, ge=0, le=33)
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


class SquadBuildResponse(BaseModel):
    status: Literal["optimal", "feasible", "infeasible", "unknown"]
    formation: str
    slots: list[SquadSlot] = Field(default_factory=list)
    total_meta: float = 0.0
    team_rating: int = 0
    team_chemistry: int = 0
    solve_time_s: float = 0.0
    message: str | None = None


def _meta_for(card: Card, stats: dict | None) -> tuple[float, Literal["stats", "rating"]]:
    """Meta de la carta en el rol de su posición preferida; el rating si no hay stats
    o es portero (el rol GK aún no tiene stats propios)."""
    pos = card.positions[0]
    if not stats or pos == "GK":
        return float(card.rating), "rating"
    attrs = PlayerAttributes(**{k: v for k, v in stats.items() if k in STATS})
    return round(meta_rating(attrs, role_for(pos)), 1), "stats"


def build_club_squad(session: Session, req: SquadBuildRequest) -> SquadBuildResponse:
    formation = formations.normalize(req.formation)
    slots = formations.slots_for(formation)
    cards = club_cards(session, datetime.now(UTC))
    stats = {
        rid: s
        for rid, s in session.execute(select(CardAttributes.resource_id, CardAttributes.stats))
    }
    meta: dict[str, float] = {}
    source: dict[str, Literal["stats", "rating"]] = {}
    for card in cards:
        meta[card.card_id], source[card.card_id] = _meta_for(card, stats.get(card.resource_id))

    result = build_squad(
        cards,
        meta,
        slots,
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
            meta=meta[a.card_id],
            meta_source=source[a.card_id],
            chemistry=result.player_chemistry.get(a.card_id, 0),
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
