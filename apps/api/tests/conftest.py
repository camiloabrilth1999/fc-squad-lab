import os
import subprocess
from collections.abc import Iterator
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from fcsl_api.models_db import Base
from fcsl_api.settings import Settings

API_DIR = Path(__file__).resolve().parents[1]
FIXTURE_DB = "fcsl_test_fixture"

# Los tests no leen el apps/api/.env real (token, DATABASE_URL…): solo el entorno.
Settings.model_config["env_file"] = None


@pytest.fixture(scope="session")
def test_db_session() -> Iterator[Session]:
    """Sesión sobre una BD desechable migrada a head; nunca toca `fcsl`."""
    base = make_url(Settings().database_url)
    admin = create_engine(base.set(database="postgres"), isolation_level="AUTOCOMMIT")
    try:
        with admin.connect() as conn:
            conn.exec_driver_sql(f"DROP DATABASE IF EXISTS {FIXTURE_DB} WITH (FORCE)")
            conn.exec_driver_sql(f"CREATE DATABASE {FIXTURE_DB}")
    except SQLAlchemyError:
        admin.dispose()
        pytest.skip("Postgres no disponible")
    test_url = base.set(database=FIXTURE_DB)
    engine = create_engine(test_url)
    try:
        env = {**os.environ, "DATABASE_URL": test_url.render_as_string(hide_password=False)}
        result = subprocess.run(
            ["uv", "run", "alembic", "upgrade", "head"],
            cwd=API_DIR,
            env=env,
            check=False,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            pytest.fail(f"alembic upgrade head falló:\n{result.stderr}")
        with Session(engine) as session:
            yield session
    finally:
        engine.dispose()
        with admin.connect() as conn:
            conn.exec_driver_sql(f"DROP DATABASE IF EXISTS {FIXTURE_DB} WITH (FORCE)")
        admin.dispose()


@pytest.fixture
def clean_db(test_db_session: Session) -> Session:
    """Vacía todas las tablas de la app antes del test."""
    test_db_session.rollback()
    tables = ", ".join(t.name for t in Base.metadata.sorted_tables)
    test_db_session.execute(text(f"TRUNCATE {tables} RESTART IDENTITY CASCADE"))
    test_db_session.commit()
    return test_db_session
