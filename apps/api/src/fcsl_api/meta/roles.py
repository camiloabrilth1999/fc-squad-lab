"""Roles y sus pesos: qué atributos importan en cada rol (semilla ajustable).

Los pesos salen de los "top stats por rol" que EasySBC publica + conocimiento del
juego; son **nuestros** y se afinan por calibración (no hace falta que sumen 1, el
cálculo normaliza). `playstyles_plus` lista los ids de PlayStyle+ que más suman en el
rol: los ids son los `eaId` de PlayStyle de EA/FUT.GG y las listas salen del ranking público
`fut.gg/playstyles/best-by-role` (guía de calibración, 2026-11-19): 0 Finesse Shot, 5 Incisive
Pass, 6 Pinged Pass, 10 Jockey, 12 Intercept, 13 Anticipate, 15 Bruiser, 17 Rapid, 22 Quick
Step, 29 Footwork, 30 Cross Claimer, 31 1v1 Close Down, 32 Far Reach, 33 Deflector,
34 Low Driven Shot, 37 Gamechanger.
"""

from dataclasses import dataclass, field, replace


@dataclass(frozen=True)
class RoleWeights:
    key_stats: dict[str, float]
    playstyles_plus: list[int] = field(default_factory=list)
    best_accelerate: str | None = None


# Semilla de roles. Un rol por "familia" de posición; se amplía al afinar.
ROLES: dict[str, RoleWeights] = {
    "adv_forward": RoleWeights(  # ST — pace + definición + agilidad
        key_stats={
            "acceleration": 0.18,
            "sprint_speed": 0.15,
            "finishing": 0.18,
            "agility": 0.12,
            "balance": 0.10,
            "dribbling": 0.09,
            "ball_control": 0.08,
            "positioning": 0.06,
            "shot_power": 0.04,
        },
        playstyles_plus=[34, 37, 22, 17, 0],
        best_accelerate="EXPLOSIVE",
    ),
    "winger": RoleWeights(  # LW/RW/LM/RM — velocidad + regate + pase
        key_stats={
            "acceleration": 0.20,
            "sprint_speed": 0.16,
            "agility": 0.14,
            "dribbling": 0.14,
            "ball_control": 0.10,
            "balance": 0.08,
            "crossing": 0.08,
            "finishing": 0.06,
            "short_passing": 0.04,
        },
        playstyles_plus=[34, 37, 22, 17, 0],
        best_accelerate="EXPLOSIVE",
    ),
    "playmaker": RoleWeights(  # CAM/CM — pase + regate + visión
        key_stats={
            "short_passing": 0.16,
            "vision": 0.14,
            "ball_control": 0.14,
            "dribbling": 0.12,
            "agility": 0.10,
            "long_passing": 0.10,
            "composure": 0.08,
            "acceleration": 0.08,
            "balance": 0.08,
        },
        playstyles_plus=[34, 5, 37, 0, 6],
    ),
    "box_crasher": RoleWeights(  # CDM — físico + recuperación + pase
        key_stats={
            "interceptions": 0.16,
            "def_awareness": 0.14,
            "standing_tackle": 0.12,
            "short_passing": 0.12,
            "strength": 0.12,
            "stamina": 0.10,
            "ball_control": 0.08,
            "aggression": 0.08,
            "reactions": 0.08,
        },
        playstyles_plus=[6, 10, 13, 22, 5],
    ),
    "falseback": RoleWeights(  # LB/RB/LWB/RWB — velocidad + defensa + pase
        key_stats={
            "acceleration": 0.16,
            "sprint_speed": 0.14,
            "def_awareness": 0.12,
            "standing_tackle": 0.12,
            "interceptions": 0.10,
            "stamina": 0.10,
            "short_passing": 0.10,
            "crossing": 0.08,
            "balance": 0.08,
        },
        playstyles_plus=[10, 22, 13, 12, 15],
        best_accelerate="EXPLOSIVE",
    ),
    "defender": RoleWeights(  # CB — defensa + físico + remate
        key_stats={
            "def_awareness": 0.18,
            "standing_tackle": 0.16,
            "interceptions": 0.14,
            "heading": 0.12,
            "strength": 0.12,
            "jumping": 0.10,
            "reactions": 0.08,
            "composure": 0.06,
            "sprint_speed": 0.04,
        },
        playstyles_plus=[10, 13, 22, 12, 15],
    ),
    "goalkeeper": RoleWeights(  # GK — placeholder: sin stats de portero propios aún
        key_stats={"reactions": 0.5, "composure": 0.3, "jumping": 0.2},
        playstyles_plus=[31, 32, 29, 30, 33],
    ),
}

# CM: mismos stats que el creador, pero su propia lista de PlayStyles (pase + recuperación).
ROLES["central_mid"] = replace(
    ROLES["playmaker"], playstyles_plus=[6, 5, 10, 22, 37], best_accelerate=None
)

# Posición → rol por defecto.
_POSITION_ROLE: dict[str, str] = {
    "ST": "adv_forward",
    "CF": "adv_forward",
    "LW": "winger",
    "RW": "winger",
    "LM": "winger",
    "RM": "winger",
    "CAM": "playmaker",
    "CM": "central_mid",
    "CDM": "box_crasher",
    "LB": "falseback",
    "RB": "falseback",
    "LWB": "falseback",
    "RWB": "falseback",
    "CB": "defender",
    "GK": "goalkeeper",
}


def role_for(position: str) -> str:
    """Rol por defecto de una posición (adv_forward si no se conoce)."""
    return _POSITION_ROLE.get(position, "adv_forward")


def get_role(role: str) -> RoleWeights:
    """Pesos del rol; `KeyError` claro si no existe."""
    try:
        return ROLES[role]
    except KeyError as exc:
        raise KeyError(f"rol desconocido: {role!r}") from exc
