import httpx
import pytest
from sqlalchemy import select

from fcsl_api.ingest.http import PoliteClient
from fcsl_api.ingest.sync import sync_cards
from fcsl_api.models_db import Card
from tests.test_futgg import player

pytestmark = pytest.mark.db


def client_for(handler) -> PoliteClient:
    return PoliteClient(
        "https://fut.test",
        min_interval_s=0,
        user_agent="test-agent",
        transport=httpx.MockTransport(handler),
        sleep=lambda _s: None,
    )


def test_sync_ok(clean_db):
    def handler(request):
        page = int(request.url.params["page"])
        nxt = 2 if page == 1 else None
        data = [player(page * 10), player(page * 10 + 1)]
        return httpx.Response(
            200, json={"data": data, "next": nxt, "currentPage": page, "total": 4}
        )

    run = sync_cards(clean_db, client_for(handler))
    assert (run.kind, run.status, run.items, run.error) == ("cards", "ok", 4, None)
    assert len(clean_db.scalars(select(Card)).all()) == 4


def test_sync_partial_when_blocked_on_page_2(clean_db):
    def handler(request):
        if request.url.params["page"] == "1":
            return httpx.Response(
                200,
                json={"data": [player(1), player(2)], "next": 2, "currentPage": 1, "total": 4},
            )
        return httpx.Response(429)

    run = sync_cards(clean_db, client_for(handler))
    assert run.status == "partial"
    assert run.items == 2
    assert "429" in run.error
    assert {c.resource_id for c in clean_db.scalars(select(Card))} == {1, 2}


def test_sync_failed_when_nothing_saved(clean_db):
    run = sync_cards(clean_db, client_for(lambda r: httpx.Response(403)))
    assert run.status == "failed"
    assert run.items == 0
    assert "403" in run.error
    assert clean_db.scalars(select(Card)).all() == []


def test_sync_respects_max_pages(clean_db):
    def handler(request):
        page = int(request.url.params["page"])
        return httpx.Response(
            200,
            json={"data": [player(page)], "next": page + 1, "currentPage": page, "total": 99},
        )

    run = sync_cards(clean_db, client_for(handler), max_pages=2)
    assert (run.status, run.items) == ("partial", 2)
    assert "--max-pages" in run.error


def test_sync_max_pages_not_partial_when_source_fits(clean_db):
    def handler(request):
        return httpx.Response(
            200, json={"data": [player(1)], "next": None, "currentPage": 1, "total": 1}
        )

    run = sync_cards(clean_db, client_for(handler), max_pages=5)
    assert (run.status, run.items, run.error) == ("ok", 1, None)


def test_sync_max_pages_1_on_capped_source_is_not_ok(clean_db):
    """Con total topado la 1ª página solo decide particionar: no se guarda nada."""

    def handler(request):
        page = int(request.url.params["page"])
        return httpx.Response(
            200,
            json={"data": [player(page)], "next": page + 1, "currentPage": page, "total": 10000},
        )

    run = sync_cards(clean_db, client_for(handler), max_pages=1)
    assert run.items == 0
    assert run.status == "failed"
    assert "--max-pages" in run.error


def test_sync_partial_when_coverage_incomplete(clean_db):
    def handler(request):
        page = int(request.url.params["page"])
        return httpx.Response(
            200,
            json={
                "data": [player(page * 100 + i, 90) for i in range(30)],
                "next": page + 1,
                "currentPage": page,
                "total": 10000,
            },
        )

    run = sync_cards(clean_db, client_for(handler))
    assert run.status == "partial"
    assert "cobertura parcial" in run.error
    assert "ignorado" in run.error
    assert run.items == (10000 // 30) * 30


def test_sync_cards_second_run_within_ttl_uses_cache(clean_db, tmp_path):
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(
            200, json={"data": [player(1)], "next": None, "currentPage": 1, "total": 1}
        )

    def cached():
        c = client_for(handler)
        c._cache_dir = tmp_path
        return c

    assert sync_cards(clean_db, cached()).status == "ok"
    assert sync_cards(clean_db, cached()).status == "ok"
    assert len(calls) == 1
