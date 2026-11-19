from types import SimpleNamespace

import pytest

from fcsl_api.ingest.futgg import parse_futgg_player
from fcsl_api.meta import fitted
from fcsl_api.meta.attributes import PlayerAttributes
from fcsl_api.meta.compute import compute_meta
from fcsl_api.meta.rating import meta_rating
from fcsl_api.meta.roles import ROLES, role_for
from tests.test_futgg import PAGE

STATS = {"finishing": 80, "acceleration": 80, "sprint_speed": 80}


def test_parser_reads_bonus_fields():
    p = dict(PAGE["data"][0])
    p.update(
        accelerateType="EXPLOSIVE",
        playStyleEaIds=[16, 19],
        playStylePlusEaIds=[22],
        skillMoves=5,
        weakFoot=4,
    )
    row = parse_futgg_player(p)
    assert row.accelerate_type == "EXPLOSIVE"
    assert row.play_styles == [16, 19]
    assert row.play_styles_plus == [22]
    assert (row.skill_moves, row.weak_foot) == (5, 4)


def test_parser_bonus_fields_default_when_missing():
    p = dict(PAGE["data"][0])
    for k in ("accelerateType", "playStyleEaIds", "playStylePlusEaIds", "skillMoves", "weakFoot"):
        p.pop(k, None)
    row = parse_futgg_player(p)
    assert row.accelerate_type is None and row.play_styles == [] and row.play_styles_plus == []
    assert row.skill_moves is None and row.weak_foot is None


def test_real_playstyle_ids_in_roles():
    assert 22 in ROLES["adv_forward"].playstyles_plus  # Quick Step
    assert 10 in ROLES["defender"].playstyles_plus  # Jockey
    assert role_for("CM") != role_for("CAM")


def test_plain_playstyle_counts_less_than_plus(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(fitted, "load_fitted", dict)  # fórmula semilla, sin ajuste
    base = meta_rating(PlayerAttributes(**STATS), "adv_forward")
    plain = meta_rating(PlayerAttributes(**STATS, play_styles=[22]), "adv_forward")
    plus = meta_rating(PlayerAttributes(**STATS, play_styles_plus=[22]), "adv_forward")
    assert base < plain < plus


def _card(**kw):
    base = {
        "positions": ["ST"],
        "accelerate_type": "EXPLOSIVE",
        "play_styles": [],
        "play_styles_plus": [22, 34],
        "skill_moves": 5,
        "weak_foot": 5,
    }
    base.update(kw)
    return SimpleNamespace(**base)


def test_compute_meta_uses_card_bonus_fields(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(fitted, "load_fitted", dict)  # fórmula semilla, sin ajuste
    with_bonus = compute_meta(STATS, _card())
    without = compute_meta(
        STATS, _card(accelerate_type=None, play_styles_plus=[], skill_moves=3, weak_foot=3)
    )
    assert with_bonus.role == "adv_forward" and with_bonus.source == "stats"
    assert with_bonus.value > without.value
    assert compute_meta(None, _card(), fallback_rating=80).source == "rating"


def test_fitted_weights_drive_the_meta(monkeypatch: pytest.MonkeyPatch):
    fit = {"adv_forward": {"intercept": 10.0, "coef": {"finishing": 0.5, "ps_plus": 2.0}}}
    monkeypatch.setattr(fitted, "load_fitted", lambda: fit)
    base = meta_rating(PlayerAttributes(finishing=80), "adv_forward")
    assert base == 50.0  # 10 + 0.5 * 80
    with_ps = meta_rating(PlayerAttributes(finishing=80, play_styles_plus=[22]), "adv_forward")
    assert with_ps == 52.0
    assert meta_rating(PlayerAttributes(finishing=80), "winger") != 50.0  # rol sin ajuste: semilla


def test_parser_reads_face_stats_and_strength():
    p = dict(PAGE["data"][0])
    p.update(
        faceStatsV2={
            "facePace": 90,
            "faceShooting": 80,
            "facePassing": 70,
            "faceDribbling": 85,
            "faceDefending": 40,
            "facePhysicality": 75,
            "gkFaceDiving": 0,
        },
        attributeStrength=77,
    )
    row = parse_futgg_player(p)
    assert row.face_stats["pace"] == 90 and row.face_stats["physicality"] == 75
    assert row.face_stats["strength"] == 77 and row.face_stats["gk_diving"] == 0


def test_parser_face_stats_empty_when_missing():
    p = dict(PAGE["data"][0])
    p.pop("faceStatsV2", None)
    p.pop("attributeStrength", None)
    assert parse_futgg_player(p).face_stats == {}
