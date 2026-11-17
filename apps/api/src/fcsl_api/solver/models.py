from collections import Counter
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, Field, model_validator

Position = str  # "GK","LB","CB","RB","LWB","RWB","CDM","CM","CAM","LM","RM","LW","RW","CF","ST"


class Card(BaseModel):
    card_id: str  # "club:<item_id>" | "market:<resource_id>"
    resource_id: int
    asset_id: int
    name: str
    rating: int = Field(ge=40, le=99)
    positions: list[Position] = Field(min_length=1)  # preferida primero
    league_id: int
    nation_id: int
    club_id: int
    rare: bool = False
    rarity_tags: list[str] = Field(default_factory=list)  # p. ej. "TOTW", "SPECIAL"
    is_icon: bool = False
    is_hero: bool = False
    source: Literal["club", "market"]
    untradeable: bool = False
    duplicate: bool = False
    in_sbc_storage: bool = False
    price: int | None = None  # PC

    @property
    def level(self) -> Literal["bronze", "silver", "gold"]:
        if self.rating < 65:
            return "bronze"
        if self.rating < 75:
            return "silver"
        return "gold"


class RequirementKind(StrEnum):
    TEAM_RATING = "TEAM_RATING"
    TEAM_CHEMISTRY = "TEAM_CHEMISTRY"
    PLAYER_CHEMISTRY = "PLAYER_CHEMISTRY"
    PLAYER_RATING = "PLAYER_RATING"
    LEAGUE_PLAYERS = "LEAGUE_PLAYERS"
    NATION_PLAYERS = "NATION_PLAYERS"
    CLUB_PLAYERS = "CLUB_PLAYERS"
    DISTINCT_LEAGUES = "DISTINCT_LEAGUES"
    DISTINCT_NATIONS = "DISTINCT_NATIONS"
    DISTINCT_CLUBS = "DISTINCT_CLUBS"
    SAME_LEAGUE = "SAME_LEAGUE"
    SAME_NATION = "SAME_NATION"
    SAME_CLUB = "SAME_CLUB"
    LEVEL_PLAYERS = "LEVEL_PLAYERS"
    RARE_PLAYERS = "RARE_PLAYERS"
    TAG_PLAYERS = "TAG_PLAYERS"


class Requirement(BaseModel):
    kind: RequirementKind
    op: Literal["min", "max", "exact"] = "min"
    value: int
    ids: list[int] = Field(default_factory=list)  # *_PLAYERS: ids aceptados
    tags: list[str] = Field(default_factory=list)  # LEVEL: ["gold"]; TAG: ["TOTW"]

    @model_validator(mode="after")
    def _check_inputs(self) -> "Requirement":
        k = self.kind
        if k == RequirementKind.PLAYER_CHEMISTRY and self.op != "min":
            raise ValueError(f"PLAYER_CHEMISTRY solo admite op 'min', no {self.op!r}")
        if k in _IDS_KINDS and not self.ids:
            raise ValueError(f"{k} requiere ids no vacíos")
        if k == RequirementKind.TAG_PLAYERS and not self.tags:
            raise ValueError("TAG_PLAYERS requiere tags no vacíos")
        if k == RequirementKind.LEVEL_PLAYERS and (
            not self.tags or not set(self.tags) <= {"bronze", "silver", "gold"}
        ):
            raise ValueError(
                f"LEVEL_PLAYERS requiere tags no vacíos entre bronze/silver/gold, no {self.tags!r}"
            )
        return self


_IDS_KINDS = frozenset(
    {
        RequirementKind.LEAGUE_PLAYERS,
        RequirementKind.NATION_PLAYERS,
        RequirementKind.CLUB_PLAYERS,
    }
)


class Objective(StrEnum):
    CHEAPEST = "cheapest"
    USE_CLUB = "use_club"
    FEWEST_BUYS = "fewest_buys"


class ValuationSettings(BaseModel):
    tradeable_factor: float = 0.95
    duplicate_discount: float = 0.10
    storage_discount: float = 0.10


class SolveRequest(BaseModel):
    slots: list[Position] = Field(min_length=1, max_length=11)
    requirements: list[Requirement] = Field(default_factory=list)
    cards: list[Card]
    pool: Literal["club", "both", "market"] = "both"
    objective: Objective = Objective.CHEAPEST
    valuation: ValuationSettings = Field(default_factory=ValuationSettings)
    include_card_ids: list[str] = Field(default_factory=list)
    exclude_card_ids: list[str] = Field(default_factory=list)
    # Segundos de reloj por pool (ver service.solve / solve_all_pools).
    time_limit_s: float = Field(default=10.0, gt=0, le=60)

    @model_validator(mode="after")
    def _check_unique_card_ids(self) -> "SolveRequest":
        counts = Counter(c.card_id for c in self.cards)
        duplicates = sorted(card_id for card_id, n in counts.items() if n > 1)
        if duplicates:
            raise ValueError(f"card_id repetidos: {', '.join(duplicates)}")
        return self


class Assignment(BaseModel):
    slot_index: int
    position: Position
    card_id: str


class Solution(BaseModel):
    status: Literal["optimal", "feasible", "infeasible", "unknown"]
    pool: Literal["club", "both", "market"]
    assignments: list[Assignment] = Field(default_factory=list)
    cost: int = 0
    team_rating: int = 0
    team_chemistry: int = 0
    player_chemistry: dict[str, int] = Field(default_factory=dict)
    solve_time_s: float = 0.0
    message: str | None = None
