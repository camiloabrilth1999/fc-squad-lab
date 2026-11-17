import pytest
from sqlalchemy import select

from fcsl_api import db
from fcsl_api.models_db import SyncRun

pytestmark = [pytest.mark.db, pytest.mark.skipif(not db.ping(), reason="Postgres no disponible")]


def test_clean_db_truncates_between_tests(clean_db):
    from datetime import UTC, datetime

    clean_db.add(SyncRun(kind="k", started_at=datetime.now(UTC), status="ok"))
    clean_db.commit()
    assert len(clean_db.scalars(select(SyncRun)).all()) == 1


def test_clean_db_starts_empty(clean_db):
    assert clean_db.scalars(select(SyncRun)).all() == []
