import httpx
import pytest

from fcsl_api.ingest.sync import sync_club_attributes
from fcsl_api.models_db import Card, CardAttributes, ClubItem
from tests.test_futgg_detail import FIXTURE
from tests.test_sync import client_for

pytestmark = pytest.mark.db


def _seed(db):
    db.add(Card(resource_id=84117827, asset_id=555, name="X", rating=90, positions=["ST"]))
    db.add(Card(resource_id=2, asset_id=556, name="Y", rating=80, positions=["CB"]))  # no en club
    db.add(ClubItem(item_id=1, resource_id=84117827))
    db.commit()


def test_sync_stores_attributes_for_club_cards_only(clean_db):
    _seed(clean_db)
    paths = []

    def handler(request):
        paths.append(request.url.path)
        return httpx.Response(200, text=FIXTURE)

    run = sync_club_attributes(clean_db, client_for(handler))
    assert (run.kind, run.status, run.items) == ("club_attributes", "ok", 1)
    assert paths == ["/players/555/27-84117827/"]
    assert clean_db.get(CardAttributes, 84117827).stats["finishing"] == 96
    assert clean_db.get(CardAttributes, 2) is None


def test_sync_skips_already_stored(clean_db):
    _seed(clean_db)
    sync_club_attributes(clean_db, client_for(lambda r: httpx.Response(200, text=FIXTURE)))
    run = sync_club_attributes(clean_db, client_for(lambda r: httpx.Response(500)))
    assert run.items == 0 and run.status == "ok"


def test_sync_blocked_is_failed(clean_db):
    _seed(clean_db)
    run = sync_club_attributes(clean_db, client_for(lambda r: httpx.Response(403)))
    assert run.status == "failed" and "403" in run.error
