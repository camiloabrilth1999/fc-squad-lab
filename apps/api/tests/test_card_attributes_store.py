import pytest
from sqlalchemy.orm import Session

from fcsl_api.ingest.store import upsert_card_attributes
from fcsl_api.models_db import CardAttributes

pytestmark = pytest.mark.db


def test_upsert_inserts_then_updates(clean_db: Session):
    upsert_card_attributes(clean_db, 100, {"finishing": 90, "acceleration": 88})
    row = clean_db.get(CardAttributes, 100)
    assert row is not None and row.stats["finishing"] == 90 and row.updated_at is not None

    upsert_card_attributes(clean_db, 100, {"finishing": 95})  # reemplaza
    clean_db.expire_all()
    assert clean_db.get(CardAttributes, 100).stats == {"finishing": 95}
