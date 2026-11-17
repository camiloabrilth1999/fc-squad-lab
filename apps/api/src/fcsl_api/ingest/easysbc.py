"""Precios PC desde la API pública de EasySBC."""

import logging
from collections.abc import Iterator
from dataclasses import dataclass

from fcsl_api.ingest.http import PoliteClient

logger = logging.getLogger(__name__)

BASE_URL = "https://api-fc27.easysbc.io"
PLAYERS_PATH = "/players"
PLATFORM = "PC"
HEADERS = {"Platform": PLATFORM, "Origin": "https://www.easysbc.io"}
MAX_REQUESTS = 1000  # tope duro de peticiones reales por sincronización

_SOURCES = {"market": "easysbc:market", "sbc": "easysbc:sbc"}


@dataclass(frozen=True)
class PriceRow:
    resource_id: int
    platform: str
    price: int
    source: str


def parse_easysbc_price(p: dict) -> PriceRow | None:
    """PriceRow de un jugador de EasySBC; None si falta id, la fuente no es market/sbc o precio <= 0."""
    info = p.get("priceInfo") or {}
    source = _SOURCES.get(info.get("source"))
    price = info.get("displayPrice")
    resource_id = p.get("resourceId")
    if source is None or resource_id is None or not isinstance(price, int) or price <= 0:
        return None
    return PriceRow(resource_id, PLATFORM, price, source)


def iter_easysbc_prices(
    client: PoliteClient,
    max_pages: int | None = None,
    max_requests: int = MAX_REQUESTS,
    coverage: list[str] | None = None,
) -> Iterator[PriceRow]:
    """Itera los precios páginas 1..totalPages. `coverage` recibe razones de cobertura incompleta."""
    limit = max_requests if max_pages is None else min(max_pages, max_requests)
    page, total, discarded = 1, 1, 0
    while page <= min(total, limit):
        payload = client.get_json(PLAYERS_PATH, params={"v2": "", "page": page})
        total = payload.get("totalPages") or 1
        for p in payload.get("players") or []:
            row = parse_easysbc_price(p)
            if row is None:
                discarded += 1
            else:
                yield row
        page += 1
    if max_pages is None and total > max_requests and coverage is not None:
        coverage.append(f"tope de peticiones ({max_requests}) de {total} páginas")
    if discarded:
        logger.info("%s jugadores sin precio utilizable (0 o fuente distinta)", discarded)
