import json
from pathlib import Path

import httpx
import pytest

from fcsl_api.ingest import futgg
from fcsl_api.ingest.futgg import iter_futgg_cards, parse_futgg_player
from fcsl_api.ingest.http import PoliteClient, SourceBlocked

PAGE = json.loads((Path(__file__).parent / "data" / "futgg_page.json").read_text())


def make_client(handler) -> PoliteClient:
    return PoliteClient(
        "https://fut.test",
        min_interval_s=0,
        user_agent="test-agent",
        transport=httpx.MockTransport(handler),
        sleep=lambda _s: None,
    )


def player(ea_id: int, overall: int = 80) -> dict:
    p = json.loads(json.dumps(PAGE["data"][0]))
    p.update(eaId=ea_id, overall=overall)
    return p


def test_parse_futgg_player_fields():
    row = parse_futgg_player(PAGE["data"][0])
    assert row is not None
    assert row.resource_id == 84117827
    assert row.asset_id == 231747
    assert row.name == "Kylian Mbappé"
    assert row.card_name == "Mbappé"
    assert row.rating == 92
    assert row.positions == ["ST", "LW"]
    assert row.league_id == 53
    assert row.nation_id == 18
    assert row.club_id == 243
    assert row.rare is True
    assert row.rarity_ea_id == 3
    assert row.rarity_name == "Team of the week"
    assert row.rarity_tags == ["Team of the week", "SPECIAL"]
    assert row.is_icon is False
    assert row.is_hero is False


def test_parse_name_falls_back_to_first_last():
    p = player(1)
    p.update(commonName=None, firstName="Ada", lastName="Lovelace")
    assert parse_futgg_player(p).name == "Ada Lovelace"


def test_parse_positions_deduplicated_preferred_first():
    p = player(1)
    p.update(position="CAM", alternativePositions=["CM", "CAM", "CM"])
    assert parse_futgg_player(p).positions == ["CAM", "CM"]


def test_parse_icon_and_non_special():
    icon = parse_futgg_player(PAGE["data"][1])
    assert icon.is_icon is True
    p = player(1)
    p.update(isSpecial=False, rarityEaId=0, rarityName="Common")
    row = parse_futgg_player(p)
    assert row.rare is False
    assert row.rarity_tags == ["Common"]


@pytest.mark.parametrize("missing", ["eaId", "overall", "position"])
def test_parse_missing_fields_returns_none(missing):
    p = player(1)
    del p[missing]
    assert parse_futgg_player(p) is None
    p[missing] = None
    assert parse_futgg_player(p) is None


def test_iter_paginates_until_next_null():
    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        page = int(request.url.params["page"])
        seen.append(request.url.path)
        data = [player(100 + page * 10 + i) for i in range(2)]
        nxt = page + 1 if page < 2 else None
        return httpx.Response(
            200, json={"data": data, "next": nxt, "currentPage": page, "total": 4}
        )

    rows = list(iter_futgg_cards(make_client(handler)))
    assert [r.resource_id for r in rows] == [110, 111, 120, 121]
    assert seen == [futgg.PLAYERS_PATH] * 2


def test_iter_skips_invalid_players_and_counts_them():
    page = {"data": [player(1), {"eaId": 2}], "next": None, "currentPage": 1, "total": 2}
    it = iter_futgg_cards(make_client(lambda r: httpx.Response(200, json=page)))
    assert [r.resource_id for r in it] == [1]


def test_iter_respects_max_pages():
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        page = int(request.url.params["page"])
        calls.append(page)
        return httpx.Response(
            200,
            json={"data": [player(page)], "next": page + 1, "currentPage": page, "total": 99},
        )

    rows = list(iter_futgg_cards(make_client(handler), max_pages=3))
    assert len(rows) == 3
    assert calls == [1, 2, 3]


def test_iter_stops_on_blocked():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.params["page"] == "1":
            return httpx.Response(
                200, json={"data": [player(1)], "next": 2, "currentPage": 1, "total": 60}
            )
        return httpx.Response(429)

    it = iter_futgg_cards(make_client(handler))
    assert next(it).resource_id == 1
    with pytest.raises(SourceBlocked):
        next(it)


def test_iter_partitions_by_rating_when_total_hits_cap(monkeypatch):
    monkeypatch.setattr(futgg, "RATING_MIN", 40)
    monkeypatch.setattr(futgg, "RATING_MAX", 43)
    gte, lte = futgg.RATING_FILTER_PARAMS
    queries: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        q = dict(request.url.params)
        queries.append(q)
        lo, hi = int(q.get(gte, 40)), int(q.get(lte, 43))
        if gte not in q or hi - lo >= 2:
            return httpx.Response(
                200, json={"data": [player(999)], "next": 2, "currentPage": 1, "total": 10000}
            )
        data = [player(1000 + r, r) for r in range(lo, hi + 1)]
        return httpx.Response(
            200, json={"data": data, "next": None, "currentPage": 1, "total": len(data)}
        )

    rows = list(iter_futgg_cards(make_client(handler)))
    assert sorted(r.resource_id for r in rows) == [1040, 1041, 1042, 1043]
    assert all("page" in q for q in queries)
    assert any(gte in q for q in queries)
