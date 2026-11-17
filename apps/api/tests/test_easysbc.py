import json
from pathlib import Path

import httpx
import pytest
from sqlalchemy import select

from fcsl_api.ingest.easysbc import PriceRow, iter_easysbc_prices, parse_easysbc_price
from fcsl_api.ingest.http import PoliteClient
from fcsl_api.ingest.sync import sync_prices
from fcsl_api.models_db import Price

PAGE = json.loads((Path(__file__).parent / "data" / "easysbc_page.json").read_text())


def client_for(handler) -> PoliteClient:
    return PoliteClient(
        "https://easysbc.test",
        min_interval_s=0,
        user_agent="test-agent",
        transport=httpx.MockTransport(handler),
        sleep=lambda _s: None,
    )


def entry(resource_id: int, source: str = "market", price: int = 1000) -> dict:
    return {"resourceId": resource_id, "priceInfo": {"displayPrice": price, "source": source}}


def test_parse_market_price():
    blaszczykowski = next(p for p in PAGE["players"] if p["resourceId"] == 50496642)
    assert parse_easysbc_price(blaszczykowski) == PriceRow(50496642, "PC", 40250, "easysbc:market")


def test_parse_sbc_price():
    sbc = next(p for p in PAGE["players"] if p["priceInfo"]["source"] == "sbc")
    row = parse_easysbc_price(sbc)
    assert row is not None
    assert (row.platform, row.source, row.price) == ("PC", "easysbc:sbc", 7200)


@pytest.mark.parametrize(
    "p",
    [
        entry(1, "market", 0),
        entry(1, "sbc", 0),
        entry(1, "other", 500),
        {"resourceId": 1},
        {"resourceId": 1, "priceInfo": None},
        {"priceInfo": {"displayPrice": 5, "source": "market"}},
    ],
)
def test_parse_zero_or_other_source_none(p):
    assert parse_easysbc_price(p) is None


def test_iter_walks_all_pages_and_respects_max_pages():
    def handler(request):
        page = int(request.url.params["page"])
        return httpx.Response(200, json={"players": [entry(page)], "totalPages": 3})

    assert [r.resource_id for r in iter_easysbc_prices(client_for(handler))] == [1, 2, 3]
    assert [r.resource_id for r in iter_easysbc_prices(client_for(handler), max_pages=2)] == [1, 2]


@pytest.mark.db
def test_sync_partial_on_block(clean_db):
    def handler(request):
        if request.url.params["page"] == "1":
            return httpx.Response(200, json={"players": [entry(1), entry(2)], "totalPages": 3})
        return httpx.Response(429)

    run = sync_prices(clean_db, client_for(handler))
    assert (run.kind, run.status, run.items) == ("prices", "partial", 2)
    assert "429" in run.error
    assert {p.resource_id for p in clean_db.scalars(select(Price))} == {1, 2}


@pytest.mark.db
def test_sync_prices_ok_and_failed(clean_db):
    ok = sync_prices(
        clean_db,
        client_for(lambda r: httpx.Response(200, json={"players": [entry(7)], "totalPages": 1})),
    )
    assert (ok.status, ok.items, ok.error) == ("ok", 1, None)
    failed = sync_prices(clean_db, client_for(lambda r: httpx.Response(403)))
    assert (failed.status, failed.items) == ("failed", 0)
