"""Importación de lo que la extensión de Chrome observa en la sesión web de EA."""

import hmac
import json
import re
from collections import defaultdict
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated, Any, Literal
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator
from sqlalchemy import delete
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from .. import db
from ..ingest.store import record_sync_run
from ..models_db import ClubItem, Price
from ..settings import get_settings

API_DIR = Path(__file__).resolve().parents[3]
SAMPLES_DIR = API_DIR / "var" / "samples"
MAX_SAMPLES = 50
MAX_BODY_BYTES = 2 * 1024 * 1024
PRICE_SOURCE = "ea-session"
PRICE_PLATFORM = "PC"
CAPPED_PATHS = frozenset(
    {
        "/import/club",
        "/import/market",
        "/import/evolutions",
        "/import/objectives",
        "/import/packs",
    }
)
TOO_LARGE = "Cuerpo demasiado grande"


class ImportBodyLimit:
    """Corta con 413 los cuerpos de /import/club y /import/market > MAX_BODY_BYTES antes de parsear.

    Rechaza por Content-Length declarado; si no lo hay (chunked), acumula hasta el tope y
    reenvía el cuerpo ya leído a la app.
    """

    def __init__(self, app: ASGIApp, max_bytes: int = MAX_BODY_BYTES) -> None:
        self.app = app
        self.max_bytes = max_bytes

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or scope["path"] not in CAPPED_PATHS:
            await self.app(scope, receive, send)
            return
        declared = dict(scope["headers"]).get(b"content-length", b"")
        if declared.isdigit() and int(declared) > self.max_bytes:
            await self._reject(scope, receive, send)
            return
        chunks: list[bytes] = []
        size = 0
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                return
            chunk = message.get("body", b"")
            size += len(chunk)
            if size > self.max_bytes:
                await self._reject(scope, receive, send)
                return
            chunks.append(chunk)
            if not message.get("more_body", False):
                break
        replayed = False

        async def replay() -> Message:
            nonlocal replayed
            if replayed:
                return await receive()
            replayed = True
            return {"type": "http.request", "body": b"".join(chunks), "more_body": False}

        await self.app(scope, replay, send)

    @staticmethod
    async def _reject(scope: Scope, receive: Receive, send: Send) -> None:
        await JSONResponse({"detail": TOO_LARGE}, status_code=413)(scope, receive, send)


def get_db() -> Iterator[Session]:
    with db.get_session() as session:
        yield session


def require_token(x_fcsl_token: str | None = Header(default=None)) -> None:
    expected = get_settings().import_token
    if not expected:
        raise HTTPException(503, "Importación desactivada: falta FCSL_IMPORT_TOKEN")
    if x_fcsl_token is None or not hmac.compare_digest(x_fcsl_token.encode(), expected.encode()):
        raise HTTPException(401, "Token de importación inválido")


DbSession = Annotated[Session, Depends(get_db)]

router = APIRouter(prefix="/import", tags=["import"], dependencies=[Depends(require_token)])


class EaItem(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: int
    resourceId: int
    assetId: int
    rating: int
    untradeable: bool = False
    lastSalePrice: int | None = None
    marketDataMinPrice: int | None = None
    marketDataMaxPrice: int | None = None
    owners: int | None = None
    loans: int | None = None
    itemType: str | None = None


class ImportClubBody(BaseModel):
    location: Literal["club", "storage", "tradepile", "watchlist"]
    items: list[EaItem]
    duplicate_item_ids: list[int] = []
    # Lista completa de la ubicación según EA: lo que haya en ella y no esté aquí se borra.
    keep_item_ids: list[int] | None = None

    @model_validator(mode="after")
    def _never_wipe_club(self) -> "ImportClubBody":
        if self.location == "club" and self.keep_item_ids == []:
            raise ValueError("keep_item_ids vacío no puede vaciar el club")
        return self


class MarketObservation(BaseModel):
    resourceId: int
    buyNowPrice: int = Field(gt=0)
    seenAt: datetime


class ImportMarketBody(BaseModel):
    observations: list[MarketObservation]


class ImportRawBody(BaseModel):
    url: str
    body: Any = None


@router.post("/club")
def import_club(body: ImportClubBody, session: DbSession) -> dict[str, int]:
    now = datetime.now(UTC)
    dups = set(body.duplicate_item_ids)
    rows: dict[int, dict[str, Any]] = {}
    for it in body.items:
        if it.itemType is not None and it.itemType.lower() != "player":
            continue
        rows[it.id] = {
            "item_id": it.id,
            "resource_id": it.resourceId,
            "asset_id": it.assetId,
            "rating": it.rating,
            "untradeable": it.untradeable,
            "location": body.location,
            "duplicate": it.id in dups,
            "loan": it.loans not in (None, 0),
            "last_sale_price": it.lastSalePrice,
            "market_min": it.marketDataMinPrice,
            "market_max": it.marketDataMaxPrice,
            "first_owner": it.owners == 1,
            "imported_at": now,
            "seen_at": now,
        }
    if rows:
        stmt = insert(ClubItem).values(list(rows.values()))
        update = {c: stmt.excluded[c] for c in next(iter(rows.values())) if c != "item_id"}
        session.execute(stmt.on_conflict_do_update(index_elements=["item_id"], set_=update))
    removed = 0
    if body.keep_item_ids is not None:
        keep = set(body.keep_item_ids) | set(rows)
        gone = delete(ClubItem).where(ClubItem.location == body.location)
        if keep:
            gone = gone.where(ClubItem.item_id.not_in(keep))
        removed = session.execute(gone).rowcount or 0
    record_sync_run(session, "club", "ok", len(rows), started_at=now)  # hace commit
    return {"upserted": len(rows), "removed": removed}


@router.post("/market")
def import_market(body: ImportMarketBody, session: DbSession) -> dict[str, int]:
    started = datetime.now(UTC)
    best: dict[int, int] = {}
    seen_max: dict[int, datetime] = defaultdict(lambda: datetime.min.replace(tzinfo=UTC))
    for o in body.observations:
        seen = o.seenAt if o.seenAt.tzinfo else o.seenAt.replace(tzinfo=UTC)
        seen_max[o.resourceId] = max(seen_max[o.resourceId], seen)
        if o.resourceId not in best or o.buyNowPrice < best[o.resourceId]:
            best[o.resourceId] = o.buyNowPrice
    rows = [
        {
            "resource_id": rid,
            "platform": PRICE_PLATFORM,
            "source": PRICE_SOURCE,
            "price": price,
            "captured_at": seen_max[rid],
        }
        for rid, price in best.items()
    ]
    if rows:
        stmt = insert(Price).values(rows)
        session.execute(
            stmt.on_conflict_do_update(
                index_elements=["resource_id", "platform", "source"],
                set_={"price": stmt.excluded.price, "captured_at": stmt.excluded.captured_at},
            )
        )
    record_sync_run(session, "market", "ok", len(rows), started_at=started)  # hace commit
    return {"upserted": len(rows)}


def _slug(url: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", urlparse(url).path.lower()).strip("-")[:60].strip("-")
    return slug or "root"


@router.post("/raw")
async def import_raw(request: Request) -> dict[str, str]:
    declared = request.headers.get("content-length")
    if declared and declared.isdigit() and int(declared) > MAX_BODY_BYTES:
        raise HTTPException(413, TOO_LARGE)
    raw = b""
    async for chunk in request.stream():
        raw += chunk
        if len(raw) > MAX_BODY_BYTES:
            raise HTTPException(413, TOO_LARGE)
    try:
        body = ImportRawBody.model_validate_json(raw)
    except ValidationError as e:
        raise HTTPException(422, json.loads(e.json())) from e
    SAMPLES_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
    path = SAMPLES_DIR / f"{stamp}-{_slug(body.url)}.json"
    path.write_text(json.dumps({"url": body.url, "body": body.body}, ensure_ascii=False))
    for old in sorted(SAMPLES_DIR.glob("*.json"))[:-MAX_SAMPLES]:
        old.unlink()
    return {"saved": path.name}
