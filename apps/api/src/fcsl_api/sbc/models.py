"""Modelo de dominio de un SBC y la respuesta de resolverlo.

Un `SbcChallenge` lleva sus requisitos ya en el modelo del solver (`solver.models
.Requirement`), así que resolverlo es cargar el club y llamar al solver. La capa que
traduce el formato crudo de EA a esto vive aparte (sbc/ea.py) y se valida con muestras.
"""

from pydantic import BaseModel, Field

from ..solver.models import Objective, Requirement
from .formations import slots_for


class SbcChallenge(BaseModel):
    id: str
    set_id: str
    set_name: str
    name: str
    formation: str = "442"
    requirements: list[Requirement] = Field(default_factory=list)
    reward: str | None = None
    repeatable: bool = False
    category: str | None = None
    # De dónde salió el reto: "seed" (ejemplos propios) | "ea" (capturado de EA).
    source: str = "seed"

    def slots(self) -> list[str]:
        return slots_for(self.formation)


class SbcChallengeSummary(BaseModel):
    id: str
    set_id: str
    set_name: str
    name: str
    formation: str
    requirements: int
    reward: str | None = None
    repeatable: bool = False
    category: str | None = None
    source: str = "seed"

    @classmethod
    def of(cls, c: SbcChallenge) -> "SbcChallengeSummary":
        return cls(
            id=c.id,
            set_id=c.set_id,
            set_name=c.set_name,
            name=c.name,
            formation=c.formation,
            requirements=len(c.requirements),
            reward=c.reward,
            repeatable=c.repeatable,
            category=c.category,
            source=c.source,
        )


class SquadSlot(BaseModel):
    slot_index: int
    position: str
    card_id: str
    resource_id: int
    name: str
    rating: int
    positions: list[str]
    source: str  # "club" | "market"
    untradeable: bool
    price: int | None = None


class SbcSolveResult(BaseModel):
    challenge_id: str
    status: str  # optimal | feasible | infeasible | unknown
    pool: str  # club | both | market
    objective: Objective
    formation: str
    squad: list[SquadSlot] = Field(default_factory=list)
    cost: int = 0
    team_rating: int = 0
    team_chemistry: int = 0
    buys: int = 0  # cartas del mercado (no estaban en tu club)
    solve_time_s: float = 0.0
    message: str | None = None
