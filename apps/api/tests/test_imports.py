import json
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from fcsl_api.main import app
from fcsl_api.models_db import ClubItem, Price, SyncRun
from fcsl_api.routes import imports

DATA = Path(__file__).parent / "data"
TOKEN = "secreto-de-prueba"
H = {"X-FCSL-Token": TOKEN}


@pytest.fixture
def client(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, test_db_session: Session
) -> Iterator[TestClient]:
    monkeypatch.setenv("FCSL_IMPORT_TOKEN", TOKEN)
    monkeypatch.setattr(imports, "SAMPLES_DIR", tmp_path / "samples")

    def _session() -> Iterator[Session]:
        yield test_db_session

    app.dependency_overrides[imports.get_db] = _session
    yield TestClient(app)
    app.dependency_overrides.clear()


def _club_body() -> dict:
    raw = json.loads((DATA / "ea_club.json").read_text())
    return {
        "location": "club",
        "items": raw["itemData"],
        "duplicate_item_ids": [d["itemId"] for d in raw["duplicateItemIdList"]],
    }


def _market_body() -> dict:
    raw = json.loads((DATA / "ea_transfermarket.json").read_text())
    seen = datetime(2026, 11, 17, 12, 0, tzinfo=UTC)
    obs = [
        {
            "resourceId": a["itemData"]["resourceId"],
            "buyNowPrice": a["buyNowPrice"],
            "seenAt": (seen + timedelta(minutes=i)).isoformat(),
        }
        for i, a in enumerate(raw["auctionInfo"])
    ]
    return {"observations": obs}


def test_import_requires_token(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    assert client.post("/import/club", json=_club_body()).status_code == 401
    assert (
        client.post("/import/club", json=_club_body(), headers={"X-FCSL-Token": "x"}).status_code
        == 401
    )
    monkeypatch.delenv("FCSL_IMPORT_TOKEN")
    r = client.post("/import/club", json=_club_body(), headers=H)
    assert r.status_code == 503
    assert r.json()["detail"] == "Importación desactivada: falta FCSL_IMPORT_TOKEN"


def test_import_club_upserts_and_is_idempotent(client: TestClient, clean_db: Session) -> None:
    for _ in range(2):
        r = client.post("/import/club", json=_club_body(), headers=H)
        assert r.status_code == 200
        assert r.json() == {"upserted": 3}
    clean_db.expire_all()
    rows = {c.item_id: c for c in clean_db.scalars(select(ClubItem))}
    assert len(rows) == 3
    a, b, c = rows[111000001], rows[111000002], rows[111000003]
    assert (a.first_owner, a.loan, a.duplicate, a.location) == (True, False, False, "club")
    assert (b.untradeable, b.loan, b.first_owner) == (True, True, False)
    assert c.duplicate is True
    assert a.market_min == 12000 and a.market_max == 90000 and a.last_sale_price == 15000
    assert a.resource_id == 50000001 and a.asset_id == 1001 and a.rating == 88
    assert a.seen_at is not None


def test_import_club_unknown_resource_ok(client: TestClient, clean_db: Session) -> None:
    body = {
        "location": "storage",
        "items": [{"id": 5, "resourceId": 999999999, "assetId": 1, "rating": 70}],
    }
    assert client.post("/import/club", json=body, headers=H).json() == {"upserted": 1}
    assert clean_db.get(ClubItem, 5).resource_id == 999999999


def test_import_club_skips_non_players(client: TestClient, clean_db: Session) -> None:
    body = {
        "location": "club",
        "items": [
            {"id": 7, "resourceId": 1, "assetId": 1, "rating": 80, "itemType": "stadium"},
            {"id": 8, "resourceId": 2, "assetId": 2, "rating": 80, "itemType": "player"},
        ],
    }
    assert client.post("/import/club", json=body, headers=H).json() == {"upserted": 1}


def test_import_market_keeps_min_per_resource(client: TestClient, clean_db: Session) -> None:
    r = client.post("/import/market", json=_market_body(), headers=H)
    assert r.status_code == 200
    assert r.json() == {"upserted": 2}
    clean_db.expire_all()
    p1 = clean_db.get(Price, (50000001, "PC", "ea-session"))
    p2 = clean_db.get(Price, (50000002, "PC", "ea-session"))
    assert p1.price == 12000 and p2.price == 900
    assert p1.captured_at == datetime(2026, 11, 17, 12, 1, tzinfo=UTC)  # max(seenAt) del recurso
    # una importación posterior sobrescribe
    body = {
        "observations": [
            {"resourceId": 50000001, "buyNowPrice": 14000, "seenAt": "2026-11-18T10:00:00+00:00"}
        ]
    }
    client.post("/import/market", json=body, headers=H)
    clean_db.expire_all()
    assert clean_db.get(Price, (50000001, "PC", "ea-session")).price == 14000


def test_import_market_rejects_nonpositive_price(client: TestClient) -> None:
    body = {
        "observations": [{"resourceId": 1, "buyNowPrice": 0, "seenAt": "2026-11-17T10:00:00+00:00"}]
    }
    assert client.post("/import/market", json=body, headers=H).status_code == 422


def test_import_raw_rotates_after_50(client: TestClient, tmp_path: Path) -> None:
    for i in range(55):
        r = client.post("/import/raw", json={"url": f"https://x/{i}", "body": {"n": i}}, headers=H)
        assert r.status_code == 200
    files = sorted((tmp_path / "samples").glob("*.json"))
    assert len(files) == 50
    assert json.loads(files[-1].read_text())["body"] == {"n": 54}
    assert json.loads(files[0].read_text())["body"] == {"n": 5}


def test_import_raw_slug_is_sanitized_and_contained(client: TestClient, tmp_path: Path) -> None:
    url = "https://x/../../etc/pa ss?wd=1"
    assert client.post("/import/raw", json={"url": url, "body": 1}, headers=H).status_code == 200
    (f,) = list((tmp_path / "samples").glob("*.json"))
    assert f.resolve().parent == (tmp_path / "samples").resolve()
    assert "/" not in f.name and " " not in f.name


def test_import_raw_too_large(client: TestClient) -> None:
    big = {"url": "https://x/y", "body": "a" * (3 * 1024 * 1024)}
    assert client.post("/import/raw", json=big, headers=H).status_code == 413


def _runs(session: Session, kind: str) -> list[SyncRun]:
    session.expire_all()
    return list(session.scalars(select(SyncRun).where(SyncRun.kind == kind).order_by(SyncRun.id)))


def test_import_club_records_sync_run(client: TestClient, clean_db: Session) -> None:
    assert client.post("/import/club", json=_club_body(), headers=H).status_code == 200
    (run,) = _runs(clean_db, "club")
    assert (run.status, run.items, run.error) == ("ok", 3, None)
    assert run.finished_at is not None
    status = client.get("/data/status").json()
    assert status["last_sync"]["club"]["items"] == 3


def test_import_market_records_sync_run(client: TestClient, clean_db: Session) -> None:
    assert client.post("/import/market", json=_market_body(), headers=H).status_code == 200
    (run,) = _runs(clean_db, "market")
    assert (run.status, run.items, run.error) == ("ok", 2, None)
    assert set(client.get("/data/status").json()["last_sync"]) == {"market"}


def test_rejected_import_records_no_sync_run(client: TestClient, clean_db: Session) -> None:
    assert client.post("/import/club", json=_club_body()).status_code == 401
    assert _runs(clean_db, "club") == []


@pytest.mark.parametrize("path", ["/import/club", "/import/market"])
def test_import_body_too_large_by_content_length(client: TestClient, path: str) -> None:
    big = b'{"x": "' + b"a" * (2 * 1024 * 1024) + b'"}'
    r = client.post(path, content=big, headers={**H, "Content-Type": "application/json"})
    assert r.status_code == 413
    assert r.json() == {"detail": "Cuerpo demasiado grande"}


@pytest.mark.parametrize("path", ["/import/club", "/import/market"])
def test_import_body_too_large_streamed(client: TestClient, path: str) -> None:
    """Sin Content-Length (chunked) también se corta al pasar el tope."""

    def chunks() -> Iterator[bytes]:
        yield b'{"x": "'
        for _ in range(3):
            yield b"a" * (1024 * 1024)
        yield b'"}'

    r = client.post(path, content=chunks(), headers={**H, "Content-Type": "application/json"})
    assert r.status_code == 413


def test_import_body_under_cap_still_parsed(client: TestClient) -> None:
    headers = {**H, "Content-Type": "application/json"}
    r = client.post("/import/club", content=json.dumps(_club_body()), headers=headers)
    assert r.status_code == 200
