"""Sincronización de cartas: FUT.GG -> tabla cards, con registro en sync_runs."""

import logging
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from fcsl_api.ingest.easysbc import PriceRow, iter_easysbc_prices
from fcsl_api.ingest.futgg import CardRow, iter_futgg_cards
from fcsl_api.ingest.futgg_detail import fetch_card_attributes
from fcsl_api.ingest.http import PoliteClient
from fcsl_api.ingest.store import (
    catalog_entries,
    record_sync_run,
    upsert_card_attributes,
    upsert_cards,
    upsert_catalog,
    upsert_prices,
)
from fcsl_api.models_db import Card, CardAttributes, ClubItem, SyncRun

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
    names: dict[tuple[str, int], tuple[str, str | None]] = {}
    try:
        try:
            for row in iter_futgg_cards(client, max_pages=max_pages, coverage=coverage):
                batch.append(row)
                if len(batch) >= BATCH_SIZE:
                    names.update(catalog_entries(batch))
                    saved += upsert_cards(session, batch, SOURCE)
                    batch = []
        except SQLAlchemyError:
            raise
        except Exception as exc:  # noqa: BLE001 - SourceBlocked, red, JSON inválido
            error = f"{type(exc).__name__}: {exc}"
            logger.warning("sync de cartas interrumpida: %s", error)
        names.update(catalog_entries(batch))
        saved += upsert_cards(session, batch, SOURCE)  # lo ya descargado se conserva
        upsert_catalog(session, [(k, i, n, img) for (k, i), (n, img) in names.items()])
    except SQLAlchemyError as exc:
        session.rollback()
        error = f"{type(exc).__name__}: {exc}"
    if error is None and coverage:
        error = "cobertura parcial: " + "; ".join(coverage)
    status = "ok" if error is None else ("partial" if saved else "failed")
    run_id = record_sync_run(session, "cards", status, saved, error, started_at=started)
    return session.get_one(SyncRun, run_id)


def sync_prices(session: Session, client: PoliteClient, max_pages: int | None = None) -> SyncRun:
    """Descarga los precios PC de EasySBC y los guarda por lotes. ok | partial | failed."""
    started = datetime.now(UTC)
    saved = 0
    error: str | None = None
    coverage: list[str] = []
    batch: list[PriceRow] = []
    unusable: set[int] = set()
    try:
        try:
            for row in iter_easysbc_prices(
                client, max_pages=max_pages, coverage=coverage, unusable=unusable
            ):
                batch.append(row)
                if len(batch) >= BATCH_SIZE:
                    saved += upsert_prices(session, batch, started, unusable, prune_stale=True)
                    batch = []
                    unusable.clear()  # el generador conserva este mismo set
        except SQLAlchemyError:
            raise
        except Exception as exc:  # noqa: BLE001 - SourceBlocked, red, JSON inválido
            error = f"{type(exc).__name__}: {exc}"
            logger.warning("sync de precios interrumpida: %s", error)
        saved += upsert_prices(
            session, batch, started, unusable, prune_stale=True
        )  # lo ya descargado se conserva
    except SQLAlchemyError as exc:
        session.rollback()
        error = f"{type(exc).__name__}: {exc}"
    if error is None and coverage:
        error = "cobertura parcial: " + "; ".join(coverage)
    status = "ok" if error is None else ("partial" if saved else "failed")
    run_id = record_sync_run(session, "prices", status, saved, error, started_at=started)
    return session.get_one(SyncRun, run_id)


def sync_club_attributes(
    session: Session, client: PoliteClient, limit: int | None = None
) -> SyncRun:
    """Baja los stats detallados de las cartas del club que aún no los tienen."""
    started = datetime.now(UTC)
    rows = session.execute(
        select(Card.resource_id, Card.asset_id)
        .join(ClubItem, ClubItem.resource_id == Card.resource_id)
        .outerjoin(CardAttributes, CardAttributes.resource_id == Card.resource_id)
        .where(CardAttributes.resource_id.is_(None))
        .distinct()
        .order_by(Card.resource_id)
    ).all()
    saved = 0
    error: str | None = None
    try:
        for resource_id, asset_id in rows[:limit] if limit else rows:
            attrs = fetch_card_attributes(client, str(asset_id), resource_id)
            if attrs:
                upsert_card_attributes(session, resource_id, attrs)
                saved += 1
    except SQLAlchemyError as exc:
        session.rollback()
        error = f"{type(exc).__name__}: {exc}"
    except Exception as exc:  # noqa: BLE001 - SourceBlocked, red
        error = f"{type(exc).__name__}: {exc}"
        logger.warning("sync de atributos interrumpida: %s", error)
    status = "ok" if error is None else ("partial" if saved else "failed")
    run_id = record_sync_run(session, "club_attributes", status, saved, error, started_at=started)
    return session.get_one(SyncRun, run_id)
