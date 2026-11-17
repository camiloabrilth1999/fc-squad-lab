"""Cartas desde el listado público de jugadores de FUT.GG."""

import logging
from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any

from fcsl_api.ingest.http import PoliteClient

logger = logging.getLogger(__name__)

BASE_URL = "https://www.fut.gg"
PLAYERS_PATH = "/api/fut/players/v2/27/"
API_CAP = 10_000  # tope de resultados que la API entrega por consulta

# Filtros de rango de media para particionar cuando `total` llega al tope.
# PENDIENTE: no verificados contra la API real; la primera ejecución real (Task 3)
# debe confirmar los nombres (y RATING_MIN/MAX) y corregirlos aquí si difieren.
RATING_FILTER_PARAMS = ("overall__gte", "overall__lte")
RATING_MIN = 40
RATING_MAX = 99


@dataclass(frozen=True)
class CardRow:
    resource_id: int
    asset_id: int
    name: str
    card_name: str | None
    rating: int
    positions: list[str]
    league_id: int | None
    nation_id: int | None
    club_id: int | None
    rare: bool
    rarity_ea_id: int | None
    rarity_name: str | None
    rarity_tags: list[str]
    is_icon: bool
    is_hero: bool


def _ea_id(p: dict, key: str) -> int | None:
    return (p.get(key) or {}).get("eaId")


def parse_futgg_player(p: dict) -> CardRow | None:
    """Convierte un jugador de FUT.GG en CardRow; None si falta eaId, overall o position."""
    if p.get("eaId") is None or p.get("overall") is None or not p.get("position"):
        return None
    positions = list(dict.fromkeys([p["position"], *(p.get("alternativePositions") or [])]))
    name = p.get("commonName") or f"{p.get('firstName') or ''} {p.get('lastName') or ''}".strip()
    rarity_ea_id = p.get("rarityEaId")
    rarity_name = p.get("rarityName")
    tags = [rarity_name] if rarity_name else []
    if p.get("isSpecial"):
        tags.append("SPECIAL")
    return CardRow(
        resource_id=p["eaId"],
        asset_id=p.get("basePlayerEaId") or p["eaId"],
        name=name,
        card_name=p.get("cardName"),
        rating=p["overall"],
        positions=positions,
        league_id=_ea_id(p, "league"),
        nation_id=_ea_id(p, "nation"),
        club_id=_ea_id(p, "club"),
        rare=rarity_ea_id is not None and rarity_ea_id != 0,
        rarity_ea_id=rarity_ea_id,
        rarity_name=rarity_name,
        rarity_tags=tags,
        is_icon=bool(p.get("isIcon")),
        is_hero=bool(p.get("isHero")),
    )


class _Pager:
    """Contador de páginas pedidas y de jugadores descartados, compartido entre particiones."""

    def __init__(self, client: PoliteClient, max_pages: int | None) -> None:
        self.client = client
        self.max_pages = max_pages
        self.pages = 0
        self.discarded = 0

    @property
    def exhausted(self) -> bool:
        return self.max_pages is not None and self.pages >= self.max_pages

    def fetch(self, page: int, filters: dict[str, int]) -> dict[str, Any]:
        self.pages += 1
        return self.client.get_json(PLAYERS_PATH, params={**filters, "page": page})

    def rows(self, payload: dict[str, Any]) -> Iterator[CardRow]:
        for p in payload.get("data") or []:
            row = parse_futgg_player(p)
            if row is None:
                self.discarded += 1
            else:
                yield row


def _walk(pager: _Pager, lo: int | None, hi: int | None, seen: set[int]) -> Iterator[CardRow]:
    """Recorre un rango de media (None = sin filtro), dividiéndolo si llega al tope."""
    gte, lte = RATING_FILTER_PARAMS
    filters = {} if lo is None else {gte: lo, lte: hi}
    if pager.exhausted:
        return
    payload = pager.fetch(1, filters)
    lo_, hi_ = (RATING_MIN, RATING_MAX) if lo is None else (lo, hi)
    if (payload.get("total") or 0) >= API_CAP:
        if lo_ >= hi_:
            logger.warning("rango %s-%s supera el tope de %s: cobertura parcial", lo_, hi_, API_CAP)
        else:
            mid = (lo_ + hi_) // 2
            yield from _walk(pager, lo_, mid, seen)
            yield from _walk(pager, mid + 1, hi_, seen)
            return
    while True:
        for row in pager.rows(payload):
            if row.resource_id not in seen:
                seen.add(row.resource_id)
                yield row
        nxt = payload.get("next")
        if not nxt or pager.exhausted:
            return
        payload = pager.fetch(nxt, filters)


def iter_futgg_cards(client: PoliteClient, max_pages: int | None = None) -> Iterator[CardRow]:
    pager = _Pager(client, max_pages)
    yield from _walk(pager, None, None, set())
    if pager.discarded:
        logger.warning("%s jugadores descartados por datos incompletos", pager.discarded)
