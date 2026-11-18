"""Atributos detallados de una carta desde su ficha de FUT.GG.

Los 34 `attribute<Nombre>:<n>` de la carta principal vienen en un bloque contiguo
embebido en el HTML (SSR); más adelante aparecen `attributeStrength` sueltos de las
cartas relacionadas del listado. Se toma el primer bloque (hasta el primer stat que
se repite) y se mapean los stats de campo a nuestros nombres (los de portero se
ignoran: el meta rating de portero es aparte). `accelerateType`, PlayStyles, SM y WF
se obtienen del listado (sync-cards), inequívocos por carta, no de esta página.
"""

import re
from typing import Protocol

# La ficha de carta: /players/<slug-del-jugador-base>/27-<eaId>/
DETAIL_PATH = "/players/{slug}/27-{ea_id}/"
DETAIL_CACHE_TTL_S = 7 * 24 * 3600  # los stats de una carta no cambian: caché larga


class _TextClient(Protocol):
    def get_text(self, path: str, params: dict | None = ..., cache_ttl_s: int = ...) -> str: ...


# Nombre de FUT.GG (CamelCase, sin el prefijo `attribute`) → nuestro nombre de stat.
_STAT_MAP: dict[str, str] = {
    "Acceleration": "acceleration",
    "SprintSpeed": "sprint_speed",
    "Positioning": "positioning",
    "Finishing": "finishing",
    "ShotPower": "shot_power",
    "LongShots": "long_shots",
    "Volleys": "volleys",
    "Penalties": "penalties",
    "Vision": "vision",
    "Crossing": "crossing",
    "FkAccuracy": "fk_accuracy",
    "ShortPassing": "short_passing",
    "LongPassing": "long_passing",
    "Curve": "curve",
    "Agility": "agility",
    "Balance": "balance",
    "Reactions": "reactions",
    "BallControl": "ball_control",
    "Dribbling": "dribbling",
    "Composure": "composure",
    "Interceptions": "interceptions",
    "HeadingAccuracy": "heading",
    "DefensiveAwareness": "def_awareness",
    "StandingTackle": "standing_tackle",
    "SlidingTackle": "sliding_tackle",
    "Jumping": "jumping",
    "Stamina": "stamina",
    "Strength": "strength",
    "Aggression": "aggression",
}

_PAIR_RE = re.compile(r"attribute([A-Z][a-zA-Z]+):(\d+)")


def parse_card_attributes(html: str, ea_id: int) -> dict[str, int] | None:
    """Stats de campo de la carta `ea_id` desde el HTML de su ficha; None si el HTML
    no es de esa carta o no trae el bloque de atributos."""
    if f"eaId:{ea_id}" not in html:
        return None
    block: dict[str, str] = {}
    for name, value in _PAIR_RE.findall(html):
        if name in block:
            break  # fin del bloque principal (empiezan los sueltos de otras cartas)
        block[name] = value
    out = {_STAT_MAP[name]: int(value) for name, value in block.items() if name in _STAT_MAP}
    return out or None


def fetch_card_attributes(
    client: _TextClient, base_player_slug: str, ea_id: int
) -> dict[str, int] | None:
    """Baja la ficha de la carta de FUT.GG y devuelve sus stats de campo."""
    path = DETAIL_PATH.format(slug=base_player_slug, ea_id=ea_id)
    html = client.get_text(path, cache_ttl_s=DETAIL_CACHE_TTL_S)
    return parse_card_attributes(html, ea_id)
