"""Precio efectivo de una carta: ea-session reciente > EasySBC market > EasySBC sbc."""

from collections.abc import Collection
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from fcsl_api.models_db import Price

EA_SESSION = "ea-session"
EA_SESSION_MAX_AGE = timedelta(hours=24)
FALLBACK_SOURCES = ("easysbc:market", "easysbc:sbc")


def effective_prices(
    session: Session, resource_ids: Collection[int], now: datetime, platform: str = "PC"
) -> dict[int, tuple[int, str]]:
    """{resource_id: (precio, fuente)}; las cartas sin precio utilizable no aparecen.

    `ea-session` vale si `now - captured_at < 24 h`: con exactamente 24 h ya cae a EasySBC, y un
    `captured_at` futuro (reloj desajustado) cuenta como reciente.
    """
    if not resource_ids:
        return {}
    rows = session.scalars(
        select(Price).where(Price.resource_id.in_(resource_ids), Price.platform == platform)
    )
    by_card: dict[int, dict[str, Price]] = {}
    for row in rows:
        if row.price is not None and row.price > 0:
            by_card.setdefault(row.resource_id, {})[row.source] = row
    result: dict[int, tuple[int, str]] = {}
    for resource_id, sources in by_card.items():
        session_row = sources.get(EA_SESSION)
        if (
            session_row is not None
            and session_row.captured_at is not None
            and now - session_row.captured_at < EA_SESSION_MAX_AGE
        ):
            result[resource_id] = (session_row.price, EA_SESSION)
            continue
        for source in FALLBACK_SOURCES:
            if source in sources:
                result[resource_id] = (sources[source].price, source)
                break
    return result
