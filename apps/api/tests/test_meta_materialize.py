import pytest
from sqlalchemy.orm import Session

from fcsl_api.meta.materialize import materialize_meta
from fcsl_api.models_db import Card, CardAttributes, CardMeta

pytestmark = pytest.mark.db

FACE = {
    "pace": 85,
    "shooting": 85,
    "passing": 70,
    "dribbling": 82,
    "defending": 40,
    "physicality": 75,
    "strength": 70,
}


def _card(rid: int, rating: int, pos: str, face: dict | None) -> Card:
    return Card(
        resource_id=rid,
        asset_id=rid,
        name=f"J{rid}",
        rating=rating,
        positions=[pos],
        league_id=1,
        nation_id=1,
        club_id=1,
        face_stats=face,
    )


def test_materialize_stores_meta_role_source_and_tier(clean_db: Session) -> None:
    clean_db.add_all(
        [
            _card(1, 88, "ST", FACE),
            _card(2, 80, "ST", {**FACE, "pace": 60, "shooting": 60}),
            _card(3, 78, "CB", None),  # sin cara ni stats: se omite
        ]
    )
    clean_db.add(
        CardAttributes(
            resource_id=1,
            stats={
                n: 85
                for n in (
                    "finishing",
                    "acceleration",
                    "sprint_speed",
                    "agility",
                    "dribbling",
                    "ball_control",
                    "shot_power",
                    "balance",
                    "positioning",
                    "strength",
                )
            },
        )
    )
    clean_db.commit()

    n = materialize_meta(clean_db)
    assert n == 2
    rows = {r.resource_id: r for r in clean_db.query(CardMeta)}
    assert set(rows) == {1, 2}
    assert rows[1].source == "stats" and rows[2].source == "face"
    assert rows[1].role == "adv_forward" and rows[2].role == "adv_forward"
    assert rows[1].meta > 0 and rows[2].meta > 0
    assert rows[1].tier in ("S", "A+", "A", "B+", "B")


def test_materialize_is_idempotent_and_replaces(clean_db: Session) -> None:
    clean_db.add(_card(1, 88, "ST", FACE))
    clean_db.commit()
    materialize_meta(clean_db)
    clean_db.get(Card, 1).face_stats = {**FACE, "pace": 50, "shooting": 50}
    clean_db.commit()
    first = clean_db.get(CardMeta, 1).meta
    materialize_meta(clean_db)
    clean_db.expire_all()
    assert clean_db.query(CardMeta).count() == 1
    assert clean_db.get(CardMeta, 1).meta < first
