import os
import subprocess
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, inspect
from sqlalchemy.engine import make_url

from fcsl_api import db
from fcsl_api.main import app
from fcsl_api.settings import Settings

pytestmark = [
    pytest.mark.db,
    pytest.mark.skipif(not db.ping(), reason="Postgres no disponible"),
]

API_DIR = Path(__file__).resolve().parents[1]


def test_health_reports_db_ok():
    response = TestClient(app).get("/health")
    assert response.status_code == 200
    assert response.json()["db"] == "ok"


def test_migration_creates_tables():
    """Migra una base desechable (fcsl_test); nunca toca los datos de fcsl."""
    base = make_url(Settings().database_url)
    test_url = base.set(database="fcsl_test")
    admin = create_engine(base.set(database="postgres"), isolation_level="AUTOCOMMIT")
    with admin.connect() as conn:
        conn.exec_driver_sql("DROP DATABASE IF EXISTS fcsl_test")
        conn.exec_driver_sql("CREATE DATABASE fcsl_test")
    try:
        env = {**os.environ, "DATABASE_URL": test_url.render_as_string(hide_password=False)}
        subprocess.run(
            ["uv", "run", "alembic", "upgrade", "head"],
            cwd=API_DIR,
            env=env,
            check=True,
            capture_output=True,
        )
        engine = create_engine(test_url)
        try:
            tables = set(inspect(engine).get_table_names())
        finally:
            engine.dispose()
        assert {"cards", "prices", "club_items"} <= tables
    finally:
        with admin.connect() as conn:
            conn.exec_driver_sql("DROP DATABASE IF EXISTS fcsl_test WITH (FORCE)")
        admin.dispose()


def test_migration_0002_upgrade_and_downgrade():
    base = make_url(Settings().database_url)
    test_url = base.set(database="fcsl_test")
    admin = create_engine(base.set(database="postgres"), isolation_level="AUTOCOMMIT")
    with admin.connect() as conn:
        conn.exec_driver_sql("DROP DATABASE IF EXISTS fcsl_test")
        conn.exec_driver_sql("CREATE DATABASE fcsl_test")
    env = {**os.environ, "DATABASE_URL": test_url.render_as_string(hide_password=False)}

    def alembic(*args: str) -> None:
        subprocess.run(
            ["uv", "run", "alembic", *args],
            cwd=API_DIR,
            env=env,
            check=True,
            capture_output=True,
        )

    try:
        alembic("upgrade", "head")
        engine = create_engine(test_url)
        try:
            insp = inspect(engine)
            assert "sync_runs" in insp.get_table_names()
            cards = {c["name"] for c in insp.get_columns("cards")}
            assert {"card_name", "rarity_ea_id", "rarity_name", "source"} <= cards
            club = {c["name"] for c in insp.get_columns("club_items")}
            assert {
                "asset_id",
                "rating",
                "market_min",
                "market_max",
                "first_owner",
                "seen_at",
            } <= club
            pk = insp.get_pk_constraint("prices")["constrained_columns"]
            assert set(pk) == {"resource_id", "platform", "source"}
        finally:
            engine.dispose()
        alembic("downgrade", "0001")
        engine = create_engine(test_url)
        try:
            insp = inspect(engine)
            assert "sync_runs" not in insp.get_table_names()
            assert "card_name" not in {c["name"] for c in insp.get_columns("cards")}
            assert "asset_id" not in {c["name"] for c in insp.get_columns("club_items")}
            assert set(insp.get_pk_constraint("prices")["constrained_columns"]) == {
                "resource_id",
                "platform",
            }
        finally:
            engine.dispose()
    finally:
        with admin.connect() as conn:
            conn.exec_driver_sql("DROP DATABASE IF EXISTS fcsl_test WITH (FORCE)")
        admin.dispose()
