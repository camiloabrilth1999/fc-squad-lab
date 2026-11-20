"""Definición de los sets de Galería (sembrada) y qué cartas entran en cada uno."""

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from sqlalchemy import ColumnElement, false

from ..models_db import Card

_SETS_FILE = Path(__file__).with_name("sets.json")

# Sets sin `badge` en los datos sembrados: su pool se define por rareza o por tipo de carta.
_CUSTOM_BADGE: dict[str, tuple[str, int | str]] = {
    "ultimate-scream": ("rarity", 151),
    "holographics": ("rarity_name", "holograph"),
    "icons": ("icon", 0),
}


@dataclass(frozen=True)
class Grade:
    name: str  # D | C | B | A | S
    threshold: int  # puntos que hay que sumar
    tokens: int  # fichas que da (acumulativas por grado)


@dataclass(frozen=True)
class GallerySet:
    id: int
    group: str
    group_name: str
    name: str
    slug: str
    required: int  # nº de cartas que cuentan (las N de más puntos)
    tokens: int
    badge_type: str | None  # club | league | rarity | rarity_name | icon
    badge_id: int | str | None
    grades: tuple[Grade, ...]

    @property
    def key(self) -> str:
        return f"{self.group}/{self.slug}"


@lru_cache(maxsize=1)
def load_sets() -> tuple[GallerySet, ...]:
    out: list[GallerySet] = []
    for raw in json.loads(_SETS_FILE.read_text(encoding="utf-8")):
        badge = raw.get("badge")
        if badge:
            btype, bid = badge["type"], badge["id"]
        else:
            btype, bid = _CUSTOM_BADGE.get(raw["slug"], (None, None))
        out.append(
            GallerySet(
                id=raw["id"],
                group=raw["group"],
                group_name=raw["group_name"],
                name=raw["name"],
                slug=raw["slug"],
                required=raw["required"],
                tokens=raw["tokens"],
                badge_type=btype,
                badge_id=bid,
                grades=tuple(Grade(g["name"], g["threshold"], g["tokens"]) for g in raw["grades"]),
            )
        )
    return tuple(out)


def get_set(set_id: int) -> GallerySet | None:
    return next((s for s in load_sets() if s.id == set_id), None)


def pool_condition(s: GallerySet) -> ColumnElement[bool]:
    """Condición SQL de las cartas que entran en el set."""
    if s.badge_type == "club":
        return Card.club_id == s.badge_id
    if s.badge_type == "league":
        return Card.league_id == s.badge_id
    if s.badge_type == "rarity":
        return Card.rarity_ea_id == s.badge_id
    if s.badge_type == "rarity_name":
        return Card.rarity_name.ilike(f"%{s.badge_id}%")
    if s.badge_type == "icon":
        return Card.is_icon.is_(True)
    return false()


def in_pool(card: Card, s: GallerySet) -> bool:
    """Misma regla que `pool_condition`, para una carta ya cargada."""
    if s.badge_type == "club":
        return card.club_id == s.badge_id
    if s.badge_type == "league":
        return card.league_id == s.badge_id
    if s.badge_type == "rarity":
        return card.rarity_ea_id == s.badge_id
    if s.badge_type == "rarity_name":
        return str(s.badge_id).lower() in (card.rarity_name or "").lower()
    if s.badge_type == "icon":
        return bool(card.is_icon)
    return False
