"""Persistencia de la ingesta: upsert de cartas y registro de sincronizaciones."""

from collections.abc import Iterable
from dataclasses import asdict
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import delete, func
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from fcsl_api.ingest.easysbc import PriceRow
from fcsl_api.ingest.futgg import CardRow
from fcsl_api.models_db import Card, CardAttributes, Catalog, Price, SyncRun

_NAME_FIELDS = (
    "league_name",
    "nation_name",
    "club_name",
    "league_image",
    "nation_image",
    "club_image",
)


def _card_columns(r: CardRow) -> dict:
    """Campos de CardRow que son columnas de `cards` (sin los nombres del catálogo)."""
    return {k: v for k, v in asdict(r).items() if k not in _NAME_FIELDS}


def catalog_entries(rows: Iterable[CardRow]) -> dict[tuple[str, int], tuple[str, str | None]]:
    """(tipo, ea_id) → (nombre, imagen) de las ligas, naciones y clubes de las cartas dadas."""
    out: dict[tuple[str, int], tuple[str, str | None]] = {}
    for r in rows:
        for kind, ea_id, name, image in (
            ("league", r.league_id, r.league_name, r.league_image),
            ("nation", r.nation_id, r.nation_name, r.nation_image),
            ("club", r.club_id, r.club_name, r.club_image),
        ):
            if ea_id is not None and name:
                out[kind, ea_id] = (name, image)
    return out


def upsert_catalog(session: Session, entries: Iterable[tuple[Any, ...]]) -> int:
    """Inserta o actualiza el catálogo: (tipo, id, nombre) o (tipo, id, nombre, imagen).

    Una actualización sin imagen no borra la que ya había.
    """
    unique: dict[tuple[str, int], tuple[str, str | None]] = {}
    for e in entries:
        unique[e[0], e[1]] = (e[2], e[3] if len(e) > 3 else None)
    if not unique:
        return 0
    values = [
        {"kind": k, "ea_id": i, "name": n, "image_path": img} for (k, i), (n, img) in unique.items()
    ]
    stmt = insert(Catalog).values(values)
    session.execute(
        stmt.on_conflict_do_update(
            index_elements=[Catalog.kind, Catalog.ea_id],
            set_={
                "name": stmt.excluded.name,
                "image_path": func.coalesce(stmt.excluded.image_path, Catalog.image_path),
            },
        )
    )
    session.commit()
    return len(unique)


def upsert_cards(session: Session, rows: Iterable[CardRow], source: str) -> int:
    """Inserta o actualiza cartas por resource_id; devuelve cuántas filas distintas escribió."""
    unique = {r.resource_id: r for r in rows}
    if not unique:
        return 0
    stamp = func.clock_timestamp()
    values = [{**_card_columns(r), "source": source, "updated_at": stamp} for r in unique.values()]
    stmt = insert(Card).values(values)
    update = {c: stmt.excluded[c] for c in values[0] if c != "resource_id"}
    session.execute(stmt.on_conflict_do_update(index_elements=[Card.resource_id], set_=update))
    session.commit()
    return len(unique)


def upsert_card_attributes(session: Session, resource_id: int, stats: dict[str, int]) -> None:
    """Inserta o actualiza los stats detallados de una carta por resource_id."""
    stmt = insert(CardAttributes).values(
        resource_id=resource_id, stats=stats, updated_at=func.clock_timestamp()
    )
    session.execute(
        stmt.on_conflict_do_update(
            index_elements=[CardAttributes.resource_id],
            set_={"stats": stmt.excluded.stats, "updated_at": stmt.excluded.updated_at},
        )
    )
    session.commit()


def upsert_prices(
    session: Session,
    rows: Iterable[PriceRow],
    captured_at: datetime,
    unusable_ids: Iterable[int] = (),
    platform: str = "PC",
    prune_stale: bool = False,
) -> int:
    """Inserta o actualiza precios por (resource_id, platform, source); devuelve las filas escritas.

    Con `prune_stale`, las filas `easysbc:*` de un recurso que no vienen en este lote se borran en la misma
    transacción, igual que todas las de `unusable_ids` (vistos sin precio utilizable): así una
    fuente vieja no gana a datos frescos.
    """
    unique = {(r.resource_id, r.platform, r.source): r for r in rows}
    gone = set(unusable_ids)
    for rid, plat, source in unique if prune_stale else ():
        session.execute(
            delete(Price).where(
                Price.resource_id == rid,
                Price.platform == plat,
                Price.source.like("easysbc:%"),
                Price.source != source,
            )
        )
    if prune_stale and gone:
        session.execute(
            delete(Price).where(
                Price.resource_id.in_(gone),
                Price.platform == platform,
                Price.source.like("easysbc:%"),
            )
        )
    if not unique:
        session.commit()
        return 0
    values = [{**asdict(r), "captured_at": captured_at} for r in unique.values()]
    stmt = insert(Price).values(values)
    stmt = stmt.on_conflict_do_update(
        index_elements=[Price.resource_id, Price.platform, Price.source],
        set_={"price": stmt.excluded.price, "captured_at": stmt.excluded.captured_at},
    )
    session.execute(stmt)
    session.commit()
    return len(unique)


def record_sync_run(
    session: Session,
    kind: str,
    status: str,
    items: int,
    error: str | None = None,
    started_at: datetime | None = None,
) -> int:
    now = datetime.now(UTC)
    run = SyncRun(
        kind=kind,
        started_at=started_at or now,
        finished_at=now,
        status=status,
        items=items,
        error=error,
    )
    session.add(run)
    session.commit()
    return run.id
