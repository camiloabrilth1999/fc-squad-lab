"""Sincronización de cartas: FUT.GG -> tabla cards, con registro en sync_runs."""

import logging
from datetime import UTC, datetime

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from fcsl_api.ingest.futgg import CardRow, iter_futgg_cards
from fcsl_api.ingest.http import PoliteClient
from fcsl_api.ingest.store import record_sync_run, upsert_cards
from fcsl_api.models_db import SyncRun

logger = logging.getLogger(__name__)

BATCH_SIZE = 500
SOURCE = "futgg"


def sync_cards(session: Session, client: PoliteClient, max_pages: int | None = None) -> SyncRun:
    """Descarga las cartas y las guarda por lotes. ok | partial | failed según lo guardado."""
    started = datetime.now(UTC)
    saved = 0
    error: str | None = None
    coverage: list[str] = []
    batch: list[CardRow] = []
    try:
        try:
            for row in iter_futgg_cards(client, max_pages=max_pages, coverage=coverage):
                batch.append(row)
                if len(batch) >= BATCH_SIZE:
                    saved += upsert_cards(session, batch, SOURCE)
                    batch = []
        except SQLAlchemyError:
            raise
        except Exception as exc:  # noqa: BLE001 - SourceBlocked, red, JSON inválido
            error = f"{type(exc).__name__}: {exc}"
            logger.warning("sync de cartas interrumpida: %s", error)
        saved += upsert_cards(session, batch, SOURCE)  # lo ya descargado se conserva
    except SQLAlchemyError as exc:
        session.rollback()
        error = f"{type(exc).__name__}: {exc}"
    if error is None and coverage:
        error = "cobertura parcial: " + "; ".join(coverage)
    status = "ok" if error is None else ("partial" if saved else "failed")
    run_id = record_sync_run(session, "cards", status, saved, error, started_at=started)
    return session.get_one(SyncRun, run_id)
