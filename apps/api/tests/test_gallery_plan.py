from fcsl_api.gallery.plan import Built, Option, SetOptions, _option, make_plan, plan
from fcsl_api.gallery.service import PoolCard
from fcsl_api.gallery.sets import GallerySet, Grade


def _set(sid: int, name: str = "S") -> GallerySet:
    grades = (Grade("D", 10, 0), Grade("C", 20, 5), Grade("B", 30, 10))
    return GallerySet(sid, "g", "G", f"{name}{sid}", f"s{sid}", 15, 15, "club", sid, grades)


def _opt(grade: str, tokens: int, tax: int, buys: int = 5, coins: int = 500) -> Option:
    return Option(grade, tokens, 100, tax * 20, tax, buys, coins)


def _so(sid: int, *options: Option) -> SetOptions:
    return SetOptions(set=_set(sid), current=None, options=list(options))


SETS = [
    _so(1, _opt("C", 5, 100), _opt("B", 15, 600)),
    _so(2, _opt("C", 5, 50, coins=3000), _opt("B", 15, 900, coins=3000)),
    _so(3, _opt("C", 5, 400)),
]


def test_target_picks_the_cheapest_combination_in_tax() -> None:
    res = plan(SETS, target_tokens=10)
    assert res.status == "optimal"
    # C del set 1 (100) + C del set 2 (50) = 10 fichas por 150 de impuesto
    assert {(it.set.id, it.option.grade) for it in res.items} == {(1, "C"), (2, "C")}
    assert (res.tokens, res.tax) == (10, 150)


def test_without_target_maximises_tokens_within_the_tax_limit() -> None:
    res = plan(SETS, max_tax=700)
    assert (res.tokens, res.tax) == (20, 650)  # B del set 1 (600) + C del set 2 (50)
    res = plan(SETS, max_tax=1000)
    assert res.tokens == 20  # 15+5+5 costaría 1050
    res = plan(SETS, max_tax=1100)
    assert (res.tokens, res.tax) == (25, 1050)


def test_one_option_per_set_and_limits_on_sets_and_transfers() -> None:
    res = plan(SETS, max_sets=1)
    assert len(res.items) == 1 and res.tokens == 15
    res = plan(SETS, max_transfers=5)
    assert res.transfers <= 5 and len(res.items) == 1


def test_coin_balance_filters_out_expensive_floats() -> None:
    res = plan(SETS, target_tokens=10, max_coins=1000)
    assert {it.set.id for it in res.items} == {1, 3}
    assert res.coins_needed <= 1000


def test_unreachable_target_reports_the_maximum() -> None:
    res = plan(SETS, target_tokens=999)
    assert res.status == "infeasible"
    assert res.max_tokens == 35  # 15 + 15 + 5 sin límites
    res = plan(SETS, target_tokens=40, max_sets=1)
    assert res.status == "infeasible" and res.max_tokens == 15


def _card(rid: int, points: int, price: int) -> PoolCard:
    return PoolCard(rid, f"C{rid}", 70, ["CM"], "Rare", None, points, True, price, False)


def _built(pools: dict[int, list[PoolCard]]) -> Built:
    options: list[SetOptions] = []
    gains: dict[tuple[int, str], int] = {}
    for sid, pool in pools.items():
        s = GallerySet(
            sid, "g", "G", f"S{sid}", f"s{sid}", 2, 5, "club", sid, (Grade("C", 105, 5),)
        )
        gains[sid, "C"] = 5
        opt = _option(s, pool, "C", 105, 5, True)
        options.append(SetOptions(set=s, current=None, options=[opt] if opt else []))
    return Built(
        complete=True,
        options=options,
        pools=pools,
        pool_ids={sid: frozenset(c.resource_id for c in p) for sid, p in pools.items()},
        gains=gains,
    )


def test_a_card_shared_by_two_sets_is_bought_once() -> None:
    shared = _card(1, 100, 1000)
    built = _built(
        {
            1: [shared, _card(2, 10, 100)],
            2: [shared, _card(3, 10, 200)],
        }
    )
    res = make_plan(built, target_tokens=10)
    assert res.status == "optimal" and res.tokens == 10
    # independiente: 55 + 60 de impuestos; compartiendo la carta de 1000 solo se compra una vez
    assert res.independent_tax == 115
    assert res.tax == 65
    assert res.cost == 1100 + 200
    bought = [it.option.bought for it in res.items]
    assert bought[0] & bought[1] == frozenset()  # ninguna carta se compra dos veces


def test_without_overlap_the_plan_is_the_independent_one() -> None:
    built = _built(
        {
            1: [_card(1, 100, 1000), _card(2, 10, 100)],
            2: [_card(3, 100, 900), _card(4, 10, 100)],
        }
    )
    res = make_plan(built, target_tokens=10)
    assert res.tax == res.independent_tax
