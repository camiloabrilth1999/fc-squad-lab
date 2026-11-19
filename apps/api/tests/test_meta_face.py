from types import SimpleNamespace

import pytest

from fcsl_api.meta import face
from fcsl_api.meta.compute import compute_meta

FIT = {
    "adv_forward": {"intercept": 10.0, "coef": {"shooting": 0.5, "pace": 0.4}},
    "goalkeeper": {"intercept": 0.0, "coef": {"gk_reflexes": 1.0}},
}


def _card(**kw):
    base = {
        "positions": ["ST"],
        "face_stats": {"pace": 90, "shooting": 80},
        "accelerate_type": None,
        "play_styles": [],
        "play_styles_plus": [],
        "skill_moves": 3,
        "weak_foot": 3,
        "height": 180,
        "rating": 84,
    }
    base.update(kw)
    return SimpleNamespace(**base)


def test_face_meta_applies_fitted_weights(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(face, "load_face_fitted", lambda: FIT)
    assert face.face_meta(_card(), "adv_forward") == 10.0 + 0.5 * 80 + 0.4 * 90


def test_face_meta_none_without_fit_or_stats(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(face, "load_face_fitted", lambda: FIT)
    assert face.face_meta(_card(face_stats={}), "adv_forward") is None
    assert face.face_meta(_card(), "winger") is None  # rol sin ajuste


def test_goalkeeper_uses_gk_face_stats(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(face, "load_face_fitted", lambda: FIT)
    gk = _card(positions=["GK"], face_stats={"gk_reflexes": 88})
    assert face.face_meta(gk, "goalkeeper") == 88.0


def test_compute_meta_falls_back_detailed_then_face_then_rating(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(face, "load_face_fitted", lambda: FIT)
    estimated = compute_meta(None, _card())
    assert (estimated.source, estimated.value) == ("face", 10.0 + 40.0 + 36.0)
    nothing = compute_meta(None, _card(face_stats=None), fallback_rating=84)
    assert (nothing.source, nothing.value) == ("rating", 84.0)
