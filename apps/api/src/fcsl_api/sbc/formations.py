"""Formaciones FUT → las 11 posiciones de sus huecos, en el orden de la plantilla.

Las posiciones alimentan directamente `solver.models.SolveRequest.slots` (la química
del solver depende de ellas). Claves sin prefijo "f" (EA usa "f442"): se normaliza.
"""

FORMATIONS: dict[str, list[str]] = {
    "442": ["GK", "LB", "CB", "CB", "RB", "LM", "CM", "CM", "RM", "ST", "ST"],
    "4411": ["GK", "LB", "CB", "CB", "RB", "LM", "CM", "CM", "RM", "CF", "ST"],
    "433": ["GK", "LB", "CB", "CB", "RB", "CM", "CM", "CM", "LW", "ST", "RW"],
    "4231": ["GK", "LB", "CB", "CB", "RB", "CDM", "CDM", "CAM", "LM", "RM", "ST"],
    "41212": ["GK", "LB", "CB", "CB", "RB", "CDM", "LM", "CM", "RM", "CF", "ST"],
    "352": ["GK", "CB", "CB", "CB", "LWB", "CM", "CDM", "CM", "RWB", "ST", "ST"],
    "3421": ["GK", "CB", "CB", "CB", "LM", "CM", "CM", "RM", "CAM", "ST", "ST"],
    "532": ["GK", "LWB", "CB", "CB", "CB", "RWB", "CM", "CDM", "CM", "ST", "ST"],
    "4321": ["GK", "LB", "CB", "CB", "RB", "CM", "CM", "CM", "CF", "CF", "ST"],
    "4141": ["GK", "LB", "CB", "CB", "RB", "CDM", "LM", "CM", "CM", "RM", "ST"],
    "4222": ["GK", "LB", "CB", "CB", "RB", "CDM", "CDM", "CAM", "CAM", "ST", "ST"],
    "424": ["GK", "LB", "CB", "CB", "RB", "CM", "CM", "LW", "RW", "ST", "ST"],
    "343": ["GK", "CB", "CB", "CB", "LM", "CM", "CM", "RM", "LW", "ST", "RW"],
    "3142": ["GK", "CB", "CB", "CB", "CDM", "LM", "CM", "CM", "RM", "ST", "ST"],
    "5212": ["GK", "LWB", "CB", "CB", "CB", "RWB", "CM", "CM", "CAM", "ST", "ST"],
    "451": ["GK", "LB", "CB", "CB", "RB", "LM", "CM", "CM", "CM", "RM", "ST"],
}

DEFAULT_FORMATION = "442"


def normalize(formation: str) -> str:
    """ "f442"/"442" → "442"; desconocida → DEFAULT_FORMATION."""
    key = formation.lower().removeprefix("f")
    return key if key in FORMATIONS else DEFAULT_FORMATION


def slots_for(formation: str) -> list[str]:
    """Las 11 posiciones de la formación (la por defecto si no se reconoce)."""
    return list(FORMATIONS[normalize(formation)])
