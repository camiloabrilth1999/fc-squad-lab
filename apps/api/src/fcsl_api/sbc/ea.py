"""Adaptador: formato crudo de los DCP (SBC) de EA → `SbcChallenge` del dominio.

EA entrega cada requisito de elegibilidad como
`{scope, count, kv: {attrId: [valores]}, text}`:

- `attrId` es un código de atributo de elegibilidad (ver `_ATTR`). Los de conteo
  por jugador (naciones, ligas, clubes, calidad) llevan en `count` cuántos
  jugadores deben cumplirlo; los agregados del equipo (valoración, química,
  distintos, comparten) usan `count = -1` y el valor va en `kv`.
- `text` es la etiqueta ya localizada por EA; de ella se lee el operador
  («Mín.» → min, «Máx.» → max, «Exactamente» → exact), que el formato numérico no
  expone por separado.

Se captura con la sesión de EA / la extensión (ver `ea_capture.json`). Un reto con
algún código que aún no sabemos traducir se omite (se registra), en vez de romper
todo el catálogo.
"""

import json
import logging
from pathlib import Path

from ..solver.models import Requirement, RequirementKind
from .formations import normalize
from .models import SbcChallenge

log = logging.getLogger(__name__)

CAPTURE_PATH = Path(__file__).resolve().parent / "ea_capture.json"
# Captura aparte de los DCP de un clic (misma forma, requisitos de atributo 40/41/42).
ONECLICK_PATH = Path(__file__).resolve().parent / "ea_capture_oneclick.json"

# Código de atributo de EA → cómo construir el `Requirement`.
TEAM_RATING = 19
TEAM_CHEMISTRY = 35
QUALITY_FLOOR = 3  # calidad mínima/exacta de TODA la plantilla
QUALITY_COUNT = 17  # nº de jugadores de una calidad (bronce/plata/oro)
RATING_COUNT_MIN = 26  # nº de jugadores con GRL ≥ X
RATING_COUNT_MAX = 28  # nº de jugadores con GRL ≤ X
_TIER = {1: "bronze", 2: "silver", 3: "gold"}
_TIERS_ORDER = ["bronze", "silver", "gold"]

# Distintos en la plantilla (scope de equipo, valor en kv).
_DISTINCT = {
    7: RequirementKind.DISTINCT_NATIONS,
    8: RequirementKind.DISTINCT_LEAGUES,
    9: RequirementKind.DISTINCT_CLUBS,
}
# Máximo/mínimo que comparten un grupo (valor en kv).
_SAME = {
    4: RequirementKind.SAME_NATION,
    5: RequirementKind.SAME_LEAGUE,
    6: RequirementKind.SAME_CLUB,
}
# Jugadores de ids concretos (ids en kv, nº en count).
_BY_ID = {
    10: RequirementKind.NATION_PLAYERS,
    11: RequirementKind.LEAGUE_PLAYERS,
    12: RequirementKind.CLUB_PLAYERS,
}

# Forma de atributo combinada (DCP de un clic): el requisito es un tope sobre un
# atributo, con el scope como dirección (0 = mín, 1 = máx, 3 = banda [40, 42]).
ATTR_VALUE = "40"  # valor (mínimo, o el valor del tope)
ATTR_SELECTOR = "41"  # qué atributo: 1 = GRL (valoración), 44 = liga
ATTR_UPPER = "42"  # tope superior en bandas
ATTR_RATING = 1
ATTR_LEAGUE = 44
_SCOPE_BAND = 3
_SCOPE_MAX = 1


class UnsupportedRequirement(Exception):
    """Un código de requisito de EA que el adaptador todavía no sabe traducir."""


def _op(text: str | None) -> str:
    t = text or ""
    if "Máx" in t:
        return "max"
    if "Exact" in t:
        return "exact"
    return "min"


def _tiers_at_least(tier: int) -> list[str]:
    """Calidades ≥ `tier` (p. ej. plata → [plata, oro])."""
    return _TIERS_ORDER[tier - 1 :]


def _attribute_requirement(raw: dict, slots: int) -> list[Requirement]:
    """Forma de atributo (40/41/42): tope sobre GRL o liga. La banda da dos reqs."""
    kv: dict[str, list[int]] = raw["kv"]
    attr = kv[ATTR_SELECTOR][0]
    scope = raw.get("scope")
    if attr == ATTR_RATING:
        value = kv[ATTR_VALUE][0]
        if scope == _SCOPE_BAND:  # GRL entre value y kv[42]
            return [
                Requirement(kind=RequirementKind.TEAM_RATING, op="min", value=value),
                Requirement(kind=RequirementKind.TEAM_RATING, op="max", value=kv[ATTR_UPPER][0]),
            ]
        op = "max" if scope == _SCOPE_MAX else "min"
        return [Requirement(kind=RequirementKind.TEAM_RATING, op=op, value=value)]
    if attr == ATTR_LEAGUE:
        # «toda la plantilla de esta liga»: N = nº de huecos, id de liga en kv.
        return [
            Requirement(
                kind=RequirementKind.LEAGUE_PLAYERS, op="min", value=slots, ids=[kv[ATTR_VALUE][0]]
            )
        ]
    raise UnsupportedRequirement(f"atributo {attr} ({raw.get('text')!r})")


def _requirement(raw: dict, slots: int) -> list[Requirement]:
    """Traduce un requisito crudo de EA; lanza `UnsupportedRequirement` si no mapea."""
    kv: dict[str, list[int]] = raw["kv"]
    if ATTR_SELECTOR in kv:  # forma de atributo combinada (DCP de un clic)
        return _attribute_requirement(raw, slots)
    code = int(next(iter(kv)))
    values = kv[str(code)]
    count = raw.get("count", -1)
    op = _op(raw.get("text"))

    if code == TEAM_RATING:
        return [Requirement(kind=RequirementKind.TEAM_RATING, op=op, value=values[0])]
    if code == TEAM_CHEMISTRY:
        return [Requirement(kind=RequirementKind.TEAM_CHEMISTRY, op=op, value=values[0])]
    if code in _DISTINCT:
        return [Requirement(kind=_DISTINCT[code], op=op, value=values[0])]
    if code in _SAME:
        return [Requirement(kind=_SAME[code], op=op, value=values[0])]
    if code in _BY_ID:
        # «N jugadores de estas naciones/ligas/clubes»: ids en kv, N en count.
        return [Requirement(kind=_BY_ID[code], op="min", value=count, ids=list(values))]
    if code == QUALITY_COUNT:
        # «N jugadores de calidad X»: X en kv (1/2/3), N en count.
        return [
            Requirement(
                kind=RequirementKind.LEVEL_PLAYERS, op="min", value=count, tags=[_TIER[values[0]]]
            )
        ]
    if code == RATING_COUNT_MIN:
        # «N jugadores con GRL ≥ X»: X en kv, N en count; op (Mín./Máx.) acota N.
        return [
            Requirement(
                kind=RequirementKind.RATING_PLAYERS, op=op, value=count, min_rating=values[0]
            )
        ]
    if code == RATING_COUNT_MAX:
        # «N jugadores con GRL ≤ X»: X en kv, N en count; op (Mín./Máx.) acota N.
        return [
            Requirement(
                kind=RequirementKind.RATING_PLAYERS, op=op, value=count, max_rating=values[0]
            )
        ]
    if code == QUALITY_FLOOR:
        # Calidad de TODA la plantilla: exact → solo esa; min → esa o mejor.
        tier = values[0]
        tags = [_TIER[tier]] if op == "exact" else _tiers_at_least(tier)
        return [Requirement(kind=RequirementKind.LEVEL_PLAYERS, op="min", value=slots, tags=tags)]

    raise UnsupportedRequirement(f"código {code} ({raw.get('text')!r})")


def _challenge(raw: dict) -> SbcChallenge:
    # Los DCP de un clic no traen formación; la posición no importa (solo topes de
    # valoración/liga), así que se usa 442 por defecto para tener 11 huecos.
    formation = normalize(raw.get("formation") or "442")
    slots = 11
    reqs = [req for r in raw.get("requirements", []) for req in _requirement(r, slots)]
    return SbcChallenge(
        id=f"ea-{raw['id']}",
        set_id=f"ea-set-{raw['setId']}",
        set_name=raw["setName"],
        name=raw["name"],
        formation=formation,
        requirements=reqs,
        repeatable=bool(raw.get("repeatable", False)),
        source="ea",
    )


def parse(data: dict) -> list[SbcChallenge]:
    """Retos capturados de EA → `SbcChallenge`; omite los que tengan requisitos no soportados."""
    out: list[SbcChallenge] = []
    for raw in data.get("challenges", []):
        try:
            out.append(_challenge(raw))
        except UnsupportedRequirement as exc:
            log.warning("SBC %s (%s) omitido: %s", raw.get("id"), raw.get("name"), exc)
    return out


def _load_file(path: Path) -> list[SbcChallenge]:
    if not path.exists():
        return []
    return parse(json.loads(path.read_text(encoding="utf-8")))


def load() -> list[SbcChallenge]:
    """Todos los DCP capturados: construcción (OPEN) + de un clic."""
    return _load_file(CAPTURE_PATH) + _load_file(ONECLICK_PATH)
