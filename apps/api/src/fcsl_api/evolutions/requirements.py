"""Requisitos de elegibilidad de las Evoluciones: decodificar, describir y comprobar.

EA los manda como filas planas agrupadas por `eligibilitySlot` (verificado contra los textos
que muestra la propia web app): una fila `PLAYER_ATTRIBUTE` con el id de atributo, una `SCOPE`
(0 mín., 1 máx., 2 exacto, 3 entre), una `ACADEMY_PLAYER_SLOTTING` con el valor y filas
`ADDITIONAL_TARGET_VALUE` con valores extra (p. ej. «Posición: MCO O MC» = 18 y 14).
"""

from collections import defaultdict
from dataclasses import dataclass
from typing import Any

MIN, MAX, EXACT, BETWEEN = 0, 1, 2, 3

# Posiciones como las numera EA (las de nuestra tabla `cards` son texto).
POSITION_IDS: dict[str, int] = {
    "GK": 0, "RWB": 2, "RB": 3, "CB": 5, "LB": 7, "LWB": 8, "CDM": 10, "RM": 12,
    "CM": 14, "LM": 16, "CAM": 18, "CF": 21, "RW": 23, "ST": 25, "LW": 27,
}  # fmt: skip
POSITION_LABELS: dict[int, str] = {
    0: "PO", 2: "CAD", 3: "LD", 5: "DFC", 7: "LI", 8: "CAI", 10: "MCD", 12: "MD",
    14: "MC", 16: "MI", 18: "MCO", 21: "MP", 23: "ED", 25: "DC", 27: "EI",
}  # fmt: skip

# id de atributo de elegibilidad → (etiqueta, género del «máximo/mínimo»: m, f o c = abreviado)
_LABELS: dict[int, tuple[str, str]] = {
    1: ("GRL", "m"), 2: ("Ritmo", "m"), 3: ("Tiro", "m"), 4: ("Pase", "m"), 5: ("Regate", "m"),
    6: ("Defensa", "f"), 7: ("Físico", "m"), 8: ("Aceleración", "f"), 9: ("Velocidad", "f"),
    10: ("Agilidad", "f"), 11: ("Equilibrio", "m"), 12: ("Salto", "m"), 13: ("Resistencia", "f"),
    14: ("Fuerza", "f"), 15: ("Reacciones", "f"), 16: ("Agresividad", "f"), 17: ("Compostura", "f"),
    18: ("Intercepciones", "f"), 19: ("Pos. ataque", "c"), 20: ("Visión", "f"),
    21: ("Control balón", "m"), 22: ("Centros", "m"), 23: ("Regates", "m"), 24: ("Definición", "f"),
    25: ("Prec. de tiros libres", "f"), 26: ("Cabezazo", "m"), 27: ("Pase largo", "m"),
    28: ("Pase corto", "m"), 29: ("Anticipación", "f"), 30: ("Pot. de tiro", "f"),
    31: ("Tiro lejano", "m"), 32: ("Entrada de pie", "f"), 33: ("Entrada en plancha", "f"),
    34: ("Voleas", "f"), 35: ("Efecto", "m"), 36: ("Penaltis", "m"), 37: ("Pierna mala", "f"),
    38: ("Filigranas", "f"), 42: ("Nación", "c"), 43: ("Club", "c"), 44: ("Liga", "c"),
    45: ("Rareza", "c"), 47: ("Posición", "c"), 49: ("Posiciones totales", "c"),
    50: ("N.º de Estilo de juego", "c"), 51: ("N.º de Estilo de juego+", "c"),
    52: ("N.º total de Estilo de juego", "c"), 55: ("Intransferible", "c"),
}  # fmt: skip
_NEGATED = {46: 45, 48: 47, 61: 41, 63: 62}  # atributo negado → atributo base

# atributo de elegibilidad (8..36) → nombre de nuestro stat detallado
_DETAIL = {
    8: "acceleration", 9: "sprint_speed", 10: "agility", 11: "balance", 12: "jumping",
    13: "stamina", 14: "strength", 15: "reactions", 16: "aggression", 17: "composure",
    18: "interceptions", 19: "positioning", 20: "vision", 21: "ball_control", 22: "crossing",
    23: "dribbling", 24: "finishing", 25: "fk_accuracy", 26: "heading", 27: "long_passing",
    28: "short_passing", 29: "def_awareness", 30: "shot_power", 31: "long_shots",
    32: "standing_tackle", 33: "sliding_tackle", 34: "volleys", 35: "curve", 36: "penalties",
}  # fmt: skip
_FACE = {2: "pace", 3: "shooting", 4: "passing", 5: "dribbling", 6: "defending", 7: "physicality"}


@dataclass(frozen=True)
class Requirement:
    attribute: int
    scope: int
    values: list[int]


def decode(rows: list[dict[str, Any]]) -> list[Requirement]:
    """Filas crudas de EA → requisitos (los grupos incompletos se ignoran)."""
    by_slot: dict[int, dict[str, list[int]]] = defaultdict(lambda: defaultdict(list))
    for r in rows:
        by_slot[r.get("slot", 0)][str(r.get("type"))].append(int(r.get("value", 0)))
    out: list[Requirement] = []
    for slot in sorted(by_slot):
        g = by_slot[slot]
        attr, scope, target = (
            g.get("PLAYER_ATTRIBUTE"),
            g.get("SCOPE"),
            g.get("ACADEMY_PLAYER_SLOTTING"),
        )
        if not (attr and scope and target):
            continue
        out.append(Requirement(attr[0], scope[0], target + g.get("ADDITIONAL_TARGET_VALUE", [])))
    return out


def _value_label(attribute: int, value: int, names: dict[tuple[str, int], str] | None) -> str:
    base = _NEGATED.get(attribute, attribute)
    if base == 47:
        return POSITION_LABELS.get(value, f"#{value}")
    kind = {42: "nation", 43: "club", 44: "league"}.get(base)
    if kind and names and (kind, value) in names:
        return names[kind, value]
    return str(value)


def describe(req: Requirement, names: dict[tuple[str, int], str] | None = None) -> str:
    """Texto como lo escribe el juego: «GRL máximo: 80», «Posición: MCO O MC»."""
    values = [_value_label(req.attribute, v, names) for v in req.values]
    if req.attribute in _NEGATED:
        return f"No debe ser: {' O '.join(values)}"
    label, gender = _LABELS.get(req.attribute, (f"Atributo {req.attribute}", "c"))
    if req.scope == EXACT:
        return f"{label}: {' O '.join(values)}"
    if req.scope == BETWEEN and len(values) >= 2:
        return f"{label} entre {values[0]} y {values[1]}"
    mx = {"m": "máximo", "f": "máxima", "c": "máx."}[gender]
    mn = {"m": "mínimo", "f": "mínima", "c": "mín."}[gender]
    return f"{label} {mx if req.scope == MAX else mn}: {values[0]}"


def facts_for(
    card: Any, stats: dict[str, int] | None, *, untradeable: bool | None = None
) -> dict[int, int | None]:
    """Datos de la carta indexados por id de atributo de elegibilidad (None = no sabemos)."""
    face = getattr(card, "face_stats", None) or {}
    positions = getattr(card, "positions", None) or []
    styles = getattr(card, "play_styles", None) or []
    plus = getattr(card, "play_styles_plus", None) or []
    facts: dict[int, int | None] = {
        1: getattr(card, "rating", None),
        37: getattr(card, "weak_foot", None),
        38: getattr(card, "skill_moves", None),
        42: getattr(card, "nation_id", None),
        43: getattr(card, "club_id", None),
        44: getattr(card, "league_id", None),
        45: getattr(card, "rarity_ea_id", None),
        47: POSITION_IDS.get(positions[0]) if positions else None,
        49: len(positions),
        50: len(styles),
        51: len(plus),
        52: len(styles) + len(plus),
        55: None if untradeable is None else int(untradeable),
    }
    for attr, key in _FACE.items():
        facts[attr] = face.get(key)
    for attr, key in _DETAIL.items():
        value = (stats or {}).get(key)
        facts[attr] = value if value is not None else (face.get(key) if key == "strength" else None)
    return facts


def check(req: Requirement, facts: dict[int, int | None]) -> bool | None:
    """True si la carta cumple, False si no, None si falta el dato para saberlo."""
    negated = req.attribute in _NEGATED
    value = facts.get(_NEGATED.get(req.attribute, req.attribute))
    if value is None:
        return None
    if req.scope == EXACT:
        hit = value in req.values
        return not hit if negated else hit
    if req.scope == BETWEEN and len(req.values) >= 2:
        return req.values[0] <= value <= req.values[1]
    if req.scope == MAX:
        return value <= req.values[0]
    return value >= req.values[0]
