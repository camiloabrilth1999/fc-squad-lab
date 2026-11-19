"""Cartas desde el listado público de jugadores de FUT.GG."""

import logging
from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import Any

from fcsl_api.ingest.http import PoliteClient

logger = logging.getLogger(__name__)

BASE_URL = "https://www.fut.gg"
PLAYERS_PATH = "/api/fut/players/v2/27/"
API_CAP = 10_000  # tope de resultados que la API entrega por consulta

# Filtros de rango de media para particionar cuando `total` llega al tope.
# Verificado contra la API real (2026-11-17): overall__gte=40&overall__lte=54 devuelve
# total=828 con overall 53-54 en la página 1 (sin filtro: total=10000 topado).
RATING_FILTER_PARAMS = ("overall__gte", "overall__lte")
RATING_MIN = 40
RATING_MAX = 99
CACHE_TTL_S = 6 * 3600  # los listados se reutilizan 6 h
MAX_REQUESTS = 1500  # tope duro de peticiones reales por sincronización


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
    accelerate_type: str | None = None
    play_styles: list[int] = field(default_factory=list)
    play_styles_plus: list[int] = field(default_factory=list)
    skill_moves: int | None = None
    weak_foot: int | None = None


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
        rare=rarity_ea_id is not None and rarity_ea_id != 0,  # Validar contra el juego
        rarity_ea_id=rarity_ea_id,
        rarity_name=rarity_name,
        rarity_tags=tags,
        is_icon=bool(p.get("isIcon")),
        is_hero=bool(p.get("isHero")),
        accelerate_type=p.get("accelerateType"),
        play_styles=list(p.get("playStyleEaIds") or []),
        play_styles_plus=list(p.get("playStylePlusEaIds") or []),
        skill_moves=p.get("skillMoves"),
        weak_foot=p.get("weakFoot"),
    )


class _FilterIgnored(Exception):
    """La API no aplica los filtros de rango: particionar no sirve."""


class _Pager:
    """Contadores compartidos entre particiones y razones de cobertura incompleta."""

    def __init__(
        self,
        client: PoliteClient,
        max_pages: int | None,
        max_requests: int,
        coverage: list[str],
    ) -> None:
        self.client = client
        self.max_pages = max_pages
        self.max_requests = max_requests
        self.coverage = coverage
        self.pages = 0
        self.discarded = 0
        self.asset_fallbacks = 0

    def note(self, reason: str) -> None:
        logger.warning("cobertura parcial: %s", reason)
        if reason not in self.coverage:
            self.coverage.append(reason)

    @property
    def exhausted(self) -> bool:
        if self.max_pages is not None and self.pages >= self.max_pages:
            self.note(f"--max-pages {self.max_pages}: quedan páginas sin recorrer")
            return True
        if self.pages >= self.max_requests:
            self.note(f"tope de peticiones ({self.max_requests})")
            return True
        return False

    def fetch(self, page: int, filters: dict[str, int]) -> dict[str, Any]:
        self.pages += 1
        return self.client.get_json(
            PLAYERS_PATH, params={**filters, "page": page}, cache_ttl_s=CACHE_TTL_S
        )

    def rows(self, payload: dict[str, Any]) -> Iterator[CardRow]:
        for p in payload.get("data") or []:
            row = parse_futgg_player(p)
            if row is None:
                self.discarded += 1
                continue
            if p.get("basePlayerEaId") is None:
                self.asset_fallbacks += 1
            yield row


def _filter_ignored(payload: dict[str, Any], lo: int, hi: int, parent_total: int | None) -> bool:
    """Un total topado igual al del padre y filas fuera del rango piden: filtro ignorado."""
    if parent_total is None or (payload.get("total") or 0) != parent_total:
        return False
    return any(not lo <= (p.get("overall") or lo) <= hi for p in payload.get("data") or [])


def _paginate(
    pager: _Pager,
    payload: dict[str, Any],
    filters: dict[str, int],
    seen: set[int],
    capped: bool,
) -> Iterator[CardRow]:
    """Recorre las páginas de una consulta; si está topada, solo hasta el tope de la API."""
    page_size = len(payload.get("data") or [])
    limit = API_CAP // page_size if capped and page_size else None
    walked = 1
    while True:
        for row in pager.rows(payload):
            if row.resource_id not in seen:
                seen.add(row.resource_id)
                yield row
        nxt = payload.get("next")
        if not nxt or pager.exhausted or (limit is not None and walked >= limit):
            return
        payload = pager.fetch(nxt, filters)
        walked += 1


def _walk(
    pager: _Pager, lo: int | None, hi: int | None, seen: set[int], parent_total: int | None
) -> Iterator[CardRow]:
    """Recorre un rango de media (None = sin filtro), dividiéndolo si llega al tope."""
    gte, lte = RATING_FILTER_PARAMS
    filters = {} if lo is None else {gte: lo, lte: hi}
    if pager.exhausted:
        return
    payload = pager.fetch(1, filters)
    lo_, hi_ = (RATING_MIN, RATING_MAX) if lo is None else (lo, hi)
    capped = (payload.get("total") or 0) >= API_CAP
    if capped and lo is not None and _filter_ignored(payload, lo, hi, parent_total):
        raise _FilterIgnored
    if capped:
        if lo_ >= hi_:
            pager.note(f"rango {lo_}-{hi_} supera el tope de {API_CAP}")
        else:
            mid = (lo_ + hi_) // 2
            total = payload["total"]
            yield from _walk(pager, lo_, mid, seen, total)
            yield from _walk(pager, mid + 1, hi_, seen, total)
            return
    yield from _paginate(pager, payload, filters, seen, capped)


def iter_futgg_cards(
    client: PoliteClient,
    max_pages: int | None = None,
    max_requests: int = MAX_REQUESTS,
    coverage: list[str] | None = None,
) -> Iterator[CardRow]:
    """Itera las cartas. `coverage` recibe las razones por las que la descarga quedó incompleta."""
    coverage = coverage if coverage is not None else []
    pager = _Pager(client, max_pages, max_requests, coverage)
    seen: set[int] = set()
    try:
        yield from _walk(pager, None, None, seen, None)
    except _FilterIgnored:
        pager.note("filtro de media ignorado por la API: solo se recorre la consulta topada")
        if not pager.exhausted:
            first = pager.fetch(1, {})
            yield from _paginate(pager, first, {}, seen, capped=True)
    if pager.discarded:
        logger.warning("%s jugadores descartados por datos incompletos", pager.discarded)
    if pager.asset_fallbacks:
        logger.warning("%s jugadores sin basePlayerEaId: asset_id = eaId", pager.asset_fallbacks)
