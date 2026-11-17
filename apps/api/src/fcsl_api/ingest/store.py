"""Persistencia de la ingesta: upsert de cartas y registro de sincronizaciones."""

from collections.abc import Iterable
from dataclasses import asdict
from datetime import UTC, datetime

from sqlalchemy import func
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from fcsl_api.ingest.futgg import CardRow
from fcsl_api.models_db import Card, SyncRun


def upsert_cards(session: Session, rows: Iterable[CardRow], source: str) -> int:
    """Inserta o actualiza cartas por resource_id; devuelve cuántas filas distintas escribió."""
    unique = {r.resource_id: r for r in rows}
    if not unique:
        return 0
    stamp = func.clock_timestamp()
    values = [{**asdict(r), "source": source, "updated_at": stamp} for r in unique.values()]
    stmt = insert(Card).values(values)
    update = {c: stmt.excluded[c] for c in values[0] if c != "resource_id"}
    session.execute(stmt.on_conflict_do_update(index_elements=[Card.resource_id], set_=update))
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
