from types import SimpleNamespace

from fcsl_api.evolutions.projection import apply_upgrades, project_meta
from fcsl_api.meta.attributes import STATS

LEVELS = [
    {"level": 0, "awards": [{"stat": 2, "count": 65535, "max_value": None}]},  # rareza: se ignora
    {
        "level": 1,
        "awards": [
            {"stat": 11, "count": 3, "max_value": 83},  # GRL
            {"stat": 21, "count": 6, "max_value": 80},  # aceleración
            {"stat": 23, "count": 18, "max_value": 85},  # agilidad
            {"stat": 82, "count": 1, "max_value": 3},  # filigranas
        ],
    },
    {
        "level": 2,
        "awards": [
            {"stat": 21, "count": 6, "max_value": 82},  # aceleración otra vez, con otro tope
            {"stat": 310, "count": 1, "max_value": 3},  # PlayStyle: Pinged Pass
            {"stat": 151, "count": 1, "max_value": 1},  # rol: no lo modelamos
        ],
    },
]


def _card(**kw):
    base = {
        "rating": 78,
        "positions": ["CAM"],
        "play_styles": [5],
        "play_styles_plus": [],
        "skill_moves": 2,
        "weak_foot": 3,
        "accelerate_type": None,
        "height": 180,
    }
    base.update(kw)
    return SimpleNamespace(**base)


def test_upgrades_are_capped_level_by_level():
    out = apply_upgrades(LEVELS, _card(), {"acceleration": 70, "agility": 60})
    # nivel 1: 70 + 6 = 76 (tope 80); nivel 2: 76 + 6 = 82 (tope 82)
    assert out.stats["acceleration"] == 82
    assert out.stats["agility"] == 78  # 60 + 18, por debajo del tope 85
    capped = apply_upgrades(LEVELS, _card(), {"agility": 70})
    assert capped.stats["agility"] == 85  # 70 + 18 = 88, recortado al tope


def test_cap_never_lowers_a_stat_already_above_it():
    out = apply_upgrades(LEVELS, _card(), {"acceleration": 90})
    assert out.stats["acceleration"] == 90  # ya supera el tope: no baja


def test_rating_skill_moves_and_playstyles():
    out = apply_upgrades(LEVELS, _card(rating=80), {})
    assert out.rating == 83  # 80 + 3, tope 83
    assert out.skill_moves == 3  # 2 + 1, tope 3
    assert out.play_styles == [5, 6]  # Pinged Pass (310) = id 6 de FUT.GG
    assert out.weak_foot == 3


def test_up_to_level_stops_early():
    out = apply_upgrades(LEVELS, _card(), {"acceleration": 70}, up_to_level=1)
    assert out.stats["acceleration"] == 76 and 6 not in out.play_styles


def test_project_meta_improves_with_better_stats(monkeypatch):
    from fcsl_api.meta import fitted

    fit = {"playmaker": {"intercept": 0.0, "coef": {"acceleration": 0.5, "agility": 0.5}}}
    monkeypatch.setattr(fitted, "load_fitted", lambda: fit)
    stats = {s: 70 for s in STATS}
    before, after = project_meta(_card(), stats, LEVELS)
    assert before == 70.0  # 0.5*70 + 0.5*70
    # aceleración 70 → 82 y agilidad 70 → 85 (88 recortado al tope)
    assert after > before and after == round(0.5 * 82 + 0.5 * 85, 1)


def test_project_meta_without_detailed_stats_is_unknown():
    assert project_meta(_card(), None, LEVELS) == (None, None)
