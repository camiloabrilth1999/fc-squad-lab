from fcsl_api.meta.attributes import PlayerAttributes
from fcsl_api.meta.rating import meta_rating
from fcsl_api.meta.roles import ROLES, RoleWeights


def _fast_finisher(**over) -> PlayerAttributes:
    base = {
        "acceleration": 90,
        "sprint_speed": 88,
        "finishing": 90,
        "agility": 88,
        "balance": 85,
        "dribbling": 85,
        "ball_control": 85,
        "positioning": 85,
        "shot_power": 84,
    }
    return PlayerAttributes(**{**base, **over})


def test_higher_key_stats_score_higher():
    fast = _fast_finisher()
    slow = _fast_finisher(acceleration=40, sprint_speed=40, finishing=40)
    assert meta_rating(fast, "adv_forward") > meta_rating(slow, "adv_forward")


def test_playstyle_plus_raises_score():
    ps = ROLES["adv_forward"].playstyles_plus[0]
    without = _fast_finisher()
    with_ps = _fast_finisher(play_styles_plus=[ps])
    assert meta_rating(with_ps, "adv_forward") > meta_rating(without, "adv_forward")


def test_missing_stat_counts_zero_no_crash():
    full = _fast_finisher()
    sparse = PlayerAttributes(acceleration=90, finishing=90)  # el resto en 0
    assert meta_rating(sparse, "adv_forward") < meta_rating(full, "adv_forward")


def test_bounds_and_weights_not_summing_one(monkeypatch):
    monkeypatch.setitem(
        ROLES, "weird", RoleWeights(key_stats={"finishing": 2.0, "acceleration": 1.0})
    )
    maxed = PlayerAttributes(
        **{s: 99 for s in ("finishing", "acceleration")},
        skill_moves=5,
        weak_foot=5,
        play_styles_plus=[22, 17],
        accelerate="EXPLOSIVE",
    )
    score = meta_rating(maxed, "weird")
    assert 0.0 <= score <= 99.9


def test_accelerate_none_no_penalty():
    none = _fast_finisher(accelerate=None)
    non_preferred = _fast_finisher(accelerate="CONTROLLED")  # adv_forward prefiere EXPLOSIVE
    assert meta_rating(none, "adv_forward") == meta_rating(non_preferred, "adv_forward")
