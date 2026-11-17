from datetime import UTC, datetime, timedelta

import pytest

from fcsl_api.ingest.easysbc import PriceRow
from fcsl_api.ingest.store import upsert_prices
from fcsl_api.prices import effective_prices

pytestmark = pytest.mark.db

NOW = datetime(2026, 11, 17, 12, 0, tzinfo=UTC)


def put(session, resource_id, source, price, age_h=0):
    upsert_prices(
        session, [PriceRow(resource_id, "PC", price, source)], NOW - timedelta(hours=age_h)
    )


def test_effective_price_rules(clean_db):
    put(clean_db, 1, "ea-session", 900, age_h=2)
    put(clean_db, 1, "easysbc:market", 1000)
    put(clean_db, 2, "ea-session", 900, age_h=30)
    put(clean_db, 2, "easysbc:market", 1000)
    put(clean_db, 2, "easysbc:sbc", 500)
    put(clean_db, 3, "easysbc:sbc", 500)
    put(clean_db, 4, "ea-session", 900, age_h=30)  # vieja y sin otra fuente: ausente
    result = effective_prices(clean_db, [1, 2, 3, 4, 5], now=NOW)
    assert result == {1: (900, "ea-session"), 2: (1000, "easysbc:market"), 3: (500, "easysbc:sbc")}


def test_effective_price_ignores_other_platform_and_empty_input(clean_db):
    upsert_prices(clean_db, [PriceRow(1, "XBOX", 5, "easysbc:market")], NOW)
    assert effective_prices(clean_db, [1], now=NOW) == {}
    assert effective_prices(clean_db, [], now=NOW) == {}


def test_upsert_prices_updates_same_key(clean_db):
    put(clean_db, 1, "easysbc:market", 1000)
    put(clean_db, 1, "easysbc:market", 1200)
    assert effective_prices(clean_db, [1], now=NOW) == {1: (1200, "easysbc:market")}


def test_ea_session_boundary_exactly_24h_falls_back_and_future_is_fresh(clean_db):
    put(clean_db, 1, "ea-session", 900, age_h=24)
    put(clean_db, 1, "easysbc:market", 1000)
    put(clean_db, 2, "ea-session", 900, age_h=-3)  # captured_at en el futuro
    put(clean_db, 2, "easysbc:market", 1000)
    assert effective_prices(clean_db, [1, 2], now=NOW) == {
        1: (1000, "easysbc:market"),
        2: (900, "ea-session"),
    }
