from fcsl_api.meta.rating import TIERS, tier_for


def test_tiers_by_percentile():
    population = [float(x) for x in range(0, 100, 10)]  # 0,10,…,90
    assert tier_for(90.0, population) == "S"  # el máximo, tier más alto
    assert tier_for(0.0, population) == "B"  # el mínimo, tier más bajo
    assert tier_for(90.0, population) in TIERS


def test_tiers_tiny_population():
    assert tier_for(50.0, [50.0]) in TIERS  # 1 carta: no rompe
    assert tier_for(10.0, [10.0, 90.0]) in TIERS  # 2 cartas
    assert tier_for(50.0, []) in TIERS  # población vacía: tier válido
