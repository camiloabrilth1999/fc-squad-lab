"""Interpreta la descripción de un objetivo de EA en una tarea planificable.

EA no entrega las condiciones estructuradas (solo `description` en texto), así que se leen con
patrones. Lo que no se reconoce se marca como no planificable con su motivo, nunca se inventa.
"""

import re
from dataclasses import dataclass, field


@dataclass(frozen=True)
class GroupMin:
    kind: str  # league | nation | club
    name: str  # tal como lo escribe EA (en español)
    k: int  # mínimo de futbolistas en el once inicial


@dataclass(frozen=True)
class Task:
    kind: str  # play | win | goals | assists | goal_matches | multi_goal | other
    amount: int  # partidos / goles / asistencias que hay que sumar
    per_match: int = 1  # para multi_goal: goles que hay que marcar en un mismo partido
    scope: str = (
        "any"  # any | online | squad_battles | rivals | champions | draft | rush | live | event:…
    )
    groups: tuple[GroupMin, ...] = ()
    plannable: bool = True
    reason: str | None = None  # por qué no se puede planificar
    notes: tuple[str, ...] = field(default_factory=tuple)


_NUM = r"(\d+(?:\s?\d{3})*)"

_NOT_MATCH = (
    (
        r"desaf[ií]o de creaci[oó]n|grupos de desaf[ií]o|completa \d+ dcp|\bdcp\b",
        "se hace con SBC, no jugando",
    ),
    (r"mercado|compra \d+|compras r[aá]pidas|pon a \d+", "se hace en el Mercado de transferibles"),
    (
        r"evaluaci[oó]n [dcbas] en el conjunto de .*galer[ií]a|conjunto de galer[ií]a",
        "se hace en la Galería",
    ),
    (r"nivel \d+ de galer", "se hace en la Galería"),
    (r"gana (?:\d+ veces )?el torneo|gana el torneo .* \d+ veces", "depende de ganar un torneo"),
    (r"^mira |retransmisi[oó]n", "es ver una retransmisión"),
    (r"bonificaciones de rush|puntos al completar", "son puntos de Rush"),
    (r"^completa (el )?(objetivo|completista)", "depende de otros objetivos"),
    (r"estrellas|momentos", "son desafíos de Momentos"),
)
_TECHNIQUE = r"con centros|de cabeza|tiro libre|de tiro|de volea|de falta|de penalti"
_COSMETIC = r"equipaci[oó]n .*equipad[ao]|tifo .*equipado|equipad[ao]"
_FIRST_OWNER = r"primera adquisici[oó]n"

_MODE_WORDS = (
    ("squad battles", "squad_battles"),
    ("rivals", "rivals"),
    ("champions", "champions"),
    ("draft", "draft"),
    ("rush", "rush"),
    ("cooperativ", "coop"),
    ("eventos en directo", "live"),
    ("evento en directo", "live"),
)


def _n(text: str) -> int:
    return int(re.sub(r"\D", "", text))


def _scope(t: str) -> str:
    if "cualquier modo" in t:
        return "any"
    online = re.search(r"squad battles \(o ", t)
    if online:
        return "online"
    m = re.search(
        r"en (?:el|la) ((?:evento|torneo|liga|circuito)[^.,]*?)(?: con | en tu | y |\.|,|$)", t
    )
    if m and "once inicial" not in m.group(1):
        return f"event:{m.group(1).strip()}"
    for word, scope in _MODE_WORDS:
        if word in t:
            return scope
    return "any"


def _groups(raw: str) -> tuple[GroupMin, ...]:
    out: list[GroupMin] = []
    raw = raw.replace("EE. UU.", "EEUU")  # el punto de la sigla corta el nombre
    # «con mín. 3 futbolistas de la Premier League en tu once inicial»
    for m in re.finditer(
        r"(?:con|llevando)\s+(?:al menos |m[ií]n\.? )?(\d+)\s+(?:futbolistas?|art[ií]culos? de futbolista)\s+"
        r"(?:de|del)\s+(.+?)(?=\s+en tu once|\s+en (?:el|la)\s|\s+en squad|\s+en cualquier|\.|,|$)",
        raw,
        flags=re.IGNORECASE,
    ):
        k, name = int(m.group(1)), m.group(2).strip().replace("EEUU", "EE. UU.")
        name = re.sub(r"^(?:la|el|los|las)\s+", "", name, flags=re.IGNORECASE)
        out.append(GroupMin(_group_kind(name), name, k))
    return tuple(out)


_LEAGUE_WORDS = (
    "premier league",
    "laliga",
    "liga f",
    "serie a",
    "bundesliga",
    "ligue 1",
    "mls",
    "nwsl",
    "roshn",
    "eredivisie",
    "liga portugal",
)


def _group_kind(name: str) -> str:
    low = name.lower()
    if re.search(
        r"\((?:laliga|premier league|serie a|bundesliga|ligue 1|mls|roshn|liga)[^)]*\)", low
    ):
        return "club"  # «Real Madrid (LALIGA)»: club con su liga entre paréntesis
    if any(low == w or low.startswith(w) for w in _LEAGUE_WORDS):
        return "league"
    return "nation"  # Francia, Italia, EE. UU., …; los clubes sin paréntesis se resuelven aparte


def parse_objective(description: str | None) -> Task:
    """Tarea planificable (o la razón de que no lo sea) a partir del texto de EA."""
    raw = (description or "").replace("\xa0", " ").strip()
    t = raw.lower()
    for pattern, reason in _NOT_MATCH:
        if re.search(pattern, t):
            return Task("other", 0, plannable=False, reason=reason)

    notes: list[str] = []
    if re.search(_COSMETIC, t):
        notes.append("necesita el objeto cosmético equipado")
    if re.search(_FIRST_OWNER, t):
        return Task(
            "win",
            0,
            plannable=False,
            reason="exige una plantilla de jugadores de primera adquisición",
        )
    if re.search(_TECHNIQUE, t):
        return Task(
            "other",
            0,
            plannable=False,
            reason="exige una jugada concreta (centro, cabeza, tiro libre)",
        )

    scope = _scope(t)
    groups = _groups(raw)

    m = re.search(r"marca al menos (\d+) gol(?:es)? en (\d+) partidos?(?: distintos)?", t)
    if m:
        goals, matches = int(m.group(1)), int(m.group(2))
        if goals == 1:
            return Task("goal_matches", matches, scope=scope, groups=groups, notes=tuple(notes))
        return Task(
            "multi_goal", matches, per_match=goals, scope=scope, groups=groups, notes=tuple(notes)
        )
    m = re.search(
        r"(?:asiste|da)\s+(?:en\s+)?al menos (\d+) (?:gol(?:es)?|asistencias?)(?: en (\d+) partidos?)?",
        t,
    )
    if m:
        return Task("assists", int(m.group(1)), scope=scope, groups=groups, notes=tuple(notes))
    m = re.search(r"asiste en al menos (\d+) gol(?:es)? en (\d+) partidos?", t)
    if m:
        return Task("goal_matches", int(m.group(2)), scope=scope, groups=groups, notes=tuple(notes))
    m = re.search(r"^marca en (\d+) partidos? distintos?", t)
    if m:
        return Task("goal_matches", int(m.group(1)), scope=scope, groups=groups, notes=tuple(notes))
    m = re.search(rf"^marca {_NUM} gol(?:es)?", t)
    if m:
        return Task("goals", _n(m.group(1)), scope=scope, groups=groups, notes=tuple(notes))
    m = re.search(rf"^(?:asiste|da) {_NUM} (?:veces|asistencias?)", t) or re.search(
        rf"^asiste en {_NUM}", t
    )
    if m:
        return Task("assists", _n(m.group(1)), scope=scope, groups=groups, notes=tuple(notes))
    m = re.search(rf"^gana {_NUM} partidos?", t)
    if m:
        return Task("win", _n(m.group(1)), scope=scope, groups=groups, notes=tuple(notes))
    m = re.search(rf"^juega {_NUM} partidos?", t)
    if m:
        return Task("play", _n(m.group(1)), scope=scope, groups=groups, notes=tuple(notes))
    m = re.search(rf"^marcad {_NUM} goles", t)  # Rush: en equipo
    if m:
        return Task("goals", _n(m.group(1)), scope="rush", groups=groups, notes=tuple(notes))
    return Task("other", 0, plannable=False, reason="no se reconoce lo que pide")
