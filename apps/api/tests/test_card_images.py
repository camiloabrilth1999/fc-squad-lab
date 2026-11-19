import httpx
import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from fcsl_api.ingest.futgg import parse_futgg_player
from fcsl_api.ingest.store import upsert_catalog
from fcsl_api.ingest.sync import sync_cards
from fcsl_api.models_db import Card, Catalog
from tests.test_futgg import PAGE, player
from tests.test_sync import client_for


def _with_images(p: dict) -> dict:
    p = dict(p)
    p.update(
        cardImagePath="2027/futgg-player-item-card/27-1.abc.webp",
        imagePath="2027/player-item/27-1.def.webp",
        league={"eaId": 53, "name": "LaLiga", "imagePath": "2027/league/53.l.png"},
        nation={"eaId": 18, "name": "France", "imagePath": "2027/nation/18.n.png"},
        club={"eaId": 243, "name": "Real Madrid", "imagePath": "2027/club/243.c.png"},
    )
    return p


def test_parser_reads_card_portrait_and_badge_paths():
    row = parse_futgg_player(_with_images(PAGE["data"][0]))
    assert row.image_path == "2027/futgg-player-item-card/27-1.abc.webp"
    assert row.portrait_path == "2027/player-item/27-1.def.webp"
    assert (row.league_image, row.nation_image, row.club_image) == (
        "2027/league/53.l.png",
        "2027/nation/18.n.png",
        "2027/club/243.c.png",
    )


def test_parser_image_fields_default_to_none():
    p = dict(PAGE["data"][0])
    for k in ("cardImagePath", "imagePath"):
        p.pop(k, None)
    row = parse_futgg_player(p)
    assert row.image_path is None and row.portrait_path is None


@pytest.mark.db
def test_sync_cards_stores_card_images_and_badges(clean_db: Session) -> None:
    def handler(request):
        p = _with_images(player(1))
        return httpx.Response(200, json={"data": [p], "next": None, "currentPage": 1, "total": 1})

    run = sync_cards(clean_db, client_for(handler))
    assert run.status == "ok"
    card = clean_db.get(Card, 1)
    assert card.image_path == "2027/futgg-player-item-card/27-1.abc.webp"
    assert card.portrait_path == "2027/player-item/27-1.def.webp"
    images = {(c.kind, c.ea_id): c.image_path for c in clean_db.scalars(select(Catalog))}
    assert images == {
        ("league", 53): "2027/league/53.l.png",
        ("nation", 18): "2027/nation/18.n.png",
        ("club", 243): "2027/club/243.c.png",
    }


@pytest.mark.db
def test_upsert_catalog_keeps_the_image_when_a_later_update_has_none(clean_db: Session) -> None:
    upsert_catalog(clean_db, [("club", 1, "Club", "2027/club/1.png")])
    upsert_catalog(clean_db, [("club", 1, "Club renombrado")])  # sin imagen: no la borra
    row = clean_db.get(Catalog, ("club", 1))
    assert row.name == "Club renombrado" and row.image_path == "2027/club/1.png"
