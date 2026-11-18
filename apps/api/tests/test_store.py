import pytest
from sqlalchemy import select

from fcsl_api.ingest.futgg import CardRow
from fcsl_api.ingest.store import record_sync_run, upsert_cards
from fcsl_api.models_db import Card, SyncRun

pytestmark = pytest.mark.db


def row(resource_id: int = 1, rating: int = 90) -> CardRow:
    return CardRow(
        resource_id=resource_id,
        asset_id=10,
        name="A B",
        card_name="B",
        rating=rating,
        positions=["ST", "LW"],
        league_id=53,
        nation_id=18,
        club_id=243,
        rare=True,
        rarity_ea_id=3,
        rarity_name="Team of the week",
        rarity_tags=["Team of the week", "SPECIAL"],
        is_icon=False,
        is_hero=False,
    )


def test_upsert_cards_idempotent(clean_db):
    assert upsert_cards(clean_db, [row(1), row(2)], source="futgg") == 2
    first = {c.resource_id: c.updated_at for c in clean_db.scalars(select(Card))}
    assert upsert_cards(clean_db, [row(1), row(2)], source="futgg") == 2
    clean_db.expire_all()
    cards = {c.resource_id: c for c in clean_db.scalars(select(Card))}
    assert set(cards) == {1, 2}
    assert all(cards[k].updated_at > first[k] for k in cards)
    assert cards[1].positions == ["ST", "LW"]
    assert cards[1].source == "futgg"


def test_upsert_updates_changed_fields_and_dedupes_batch(clean_db):
    upsert_cards(clean_db, [row(1, 90)], source="futgg")
    upsert_cards(clean_db, [row(1, 93), row(1, 94)], source="futgg")
    clean_db.expire_all()
    assert clean_db.get(Card, 1).rating == 94


def test_record_sync_run(clean_db):
    run_id = record_sync_run(clean_db, "cards", "partial", 30, error="429")
    run = clean_db.get(SyncRun, run_id)
    assert (run.kind, run.status, run.items, run.error) == ("cards", "partial", 30, "429")
    assert run.finished_at is not None
