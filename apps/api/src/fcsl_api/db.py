from sqlalchemy import Engine, create_engine, text
from sqlalchemy.exc import SQLAlchemyError

from .settings import get_settings

_engines: dict[str, Engine] = {}


def get_engine() -> Engine:
    url = get_settings().database_url
    if url not in _engines:
        _engines[url] = create_engine(
            url, pool_pre_ping=True, connect_args={"connect_timeout": 2}
        )
    return _engines[url]


def ping() -> bool:
    try:
        with get_engine().connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except SQLAlchemyError:
        return False
