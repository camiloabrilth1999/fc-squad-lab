"""Catálogo de ligas, naciones y clubes (id + nombre) para filtros."""

from typing import Annotated, Literal

from fastapi import APIRouter, Query
from pydantic import BaseModel
from sqlalchemy import select

from ..models_db import Catalog
from .imports import DbSession

router = APIRouter(prefix="/catalog", tags=["catalog"])


class CatalogEntry(BaseModel):
    id: int
    name: str


@router.get("", response_model=list[CatalogEntry])
def list_catalog(
    session: DbSession,
    kind: Literal["league", "nation", "club"],
    q: str | None = None,
    limit: Annotated[int, Query(ge=1, le=1000)] = 1000,
) -> list[CatalogEntry]:
    stmt = select(Catalog).where(Catalog.kind == kind)
    if q:
        stmt = stmt.where(Catalog.name.ilike(f"%{q.strip()}%"))
    rows = session.scalars(stmt.order_by(Catalog.name, Catalog.ea_id).limit(limit))
    return [CatalogEntry(id=r.ea_id, name=r.name) for r in rows]
