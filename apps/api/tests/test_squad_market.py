from fcsl_api.squad.market import pareto_layers


def test_first_layer_is_the_non_dominated_frontier():
    # (id, rating, precio)
    items = [(1, 90, 5000), (2, 90, 3000), (3, 85, 1000), (4, 85, 2000), (5, 80, 500), (6, 80, 900)]
    # 2 domina a 1 (mismo rating, más barata); 4 está dominada por 3 y 2; la frontera es 2, 3, 5
    assert pareto_layers(items, 3) == [2, 3, 5]


def test_more_layers_until_enough():
    items = [(1, 90, 5000), (2, 90, 3000), (3, 85, 1000), (4, 85, 2000), (5, 80, 500), (6, 80, 900)]
    assert pareto_layers(items, 5) == [2, 3, 5, 1, 4]  # capa 2: 1 (90/5000), 4 (85/2000)
    assert set(pareto_layers(items, 99)) == {1, 2, 3, 4, 5, 6}


def test_empty_and_zero():
    assert pareto_layers([], 5) == []
    assert pareto_layers([(1, 80, 100)], 0) == []
