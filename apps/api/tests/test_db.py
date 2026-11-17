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
            cwd=API_DIR, env=env, check=True, capture_output=True,
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
