"""Nombres de los PlayStyles por id de EA (tabla pública de FUT.GG, 2026-11-19)."""

PLAYSTYLE_NAMES: dict[int, str] = {
    0: "Finesse Shot",
    1: "Chip Shot",
    2: "Power Shot",
    3: "Dead Ball",
    5: "Incisive Pass",
    6: "Pinged Pass",
    7: "Long Ball Pass",
    8: "Tiki Taka",
    9: "Whipped Pass",
    10: "Jockey",
    11: "Block",
    12: "Intercept",
    13: "Anticipate",
    14: "Slide Tackle",
    15: "Bruiser",
    16: "Technical",
    17: "Rapid",
    19: "First Touch",
    20: "Trickster",
    21: "Press Proven",
    22: "Quick Step",
    23: "Relentless",
    25: "Acrobatic",
    26: "Long Throw",
    28: "Far Throw",
    29: "Footwork",
    30: "Cross Claimer",
    31: "1v1 Close Down",
    32: "Far Reach",
    33: "Deflector",
    34: "Low Driven Shot",
    35: "Aerial Fortress",
    36: "Enforcer",
    37: "Gamechanger",
    38: "Inventive",
    39: "Precision Header",
}


def playstyle_names(ids: list[int] | None) -> list[str]:
    """Nombres de los ids dados (los desconocidos salen como `#id`)."""
    return [PLAYSTYLE_NAMES.get(i, f"#{i}") for i in ids or []]
