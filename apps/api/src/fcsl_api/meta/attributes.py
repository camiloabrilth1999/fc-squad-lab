"""Atributos in-game de una carta: la entrada del meta rating.

Los stats que falten (dato incompleto de EA/FUT.GG) quedan en 0 y `get` devuelve 0
para cualquier nombre que no sea un stat conocido, para no romper el cálculo.
"""

from typing import Literal

from pydantic import BaseModel, Field

AccelerateType = Literal["EXPLOSIVE", "CONTROLLED", "LENGTHY"]

# Los ~29 stats in-game (los 6 de la cara se derivan de estos en el juego).
STATS: frozenset[str] = frozenset(
    {
        "acceleration",
        "sprint_speed",
        "positioning",
        "finishing",
        "shot_power",
        "long_shots",
        "volleys",
        "penalties",
        "vision",
        "crossing",
        "fk_accuracy",
        "short_passing",
        "long_passing",
        "curve",
        "agility",
        "balance",
        "reactions",
        "ball_control",
        "dribbling",
        "composure",
        "interceptions",
        "heading",
        "def_awareness",
        "standing_tackle",
        "sliding_tackle",
        "jumping",
        "stamina",
        "strength",
        "aggression",
    }
)


class PlayerAttributes(BaseModel):
    acceleration: int = 0
    sprint_speed: int = 0
    positioning: int = 0
    finishing: int = 0
    shot_power: int = 0
    long_shots: int = 0
    volleys: int = 0
    penalties: int = 0
    vision: int = 0
    crossing: int = 0
    fk_accuracy: int = 0
    short_passing: int = 0
    long_passing: int = 0
    curve: int = 0
    agility: int = 0
    balance: int = 0
    reactions: int = 0
    ball_control: int = 0
    dribbling: int = 0
    composure: int = 0
    interceptions: int = 0
    heading: int = 0
    def_awareness: int = 0
    standing_tackle: int = 0
    sliding_tackle: int = 0
    jumping: int = 0
    stamina: int = 0
    strength: int = 0
    aggression: int = 0
    skill_moves: int = 0
    weak_foot: int = 0
    accelerate: AccelerateType | None = None
    play_styles: list[int] = Field(default_factory=list)
    play_styles_plus: list[int] = Field(default_factory=list)

    def get(self, stat: str) -> int:
        """Valor del stat (0 si no se dio o no es un stat conocido)."""
        return getattr(self, stat, 0) if stat in STATS else 0
