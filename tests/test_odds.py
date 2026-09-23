import pytest
from tft_advisor.comps import Comp
from tft_advisor.odds import (
    Pool,
    best_roll_level,
    hit_chance,
    pool_from_state,
    roll_window,
    shop_odds,
)
from tft_advisor.state import GameState, Opponent, Unit


def test_hit_chance_zero_without_level_or_costs():
    assert hit_chance(0, [4]) == 0.0
    assert hit_chance(8, []) == 0.0


def test_hit_chance_peaks_at_matching_tier_level():
    # 3-cost odds peak around level 7 in the default table
    assert hit_chance(7, [3]) > hit_chance(5, [3])


def test_hit_chance_scales_with_wanted_units():
    one = hit_chance(8, [4])
    three = hit_chance(8, [4, 4, 4])
    assert three > one


def test_best_roll_level_for_1_cost_is_low():
    assert best_roll_level([1]) in (2, 3, 4)


def test_best_roll_level_for_4_cost_is_high():
    assert best_roll_level([4]) in (8, 9, 10, 11)


def test_roll_window_reports_now_best_next():
    w = roll_window(7, [4])
    assert set(w) == {"hit_now", "best_level", "hit_best", "hit_next"}
    assert w["hit_best"] >= w["hit_now"]
    assert w["hit_next"] == pytest.approx(hit_chance(8, [4]))


def test_shop_odds_table_covers_levels():
    table = shop_odds()
    assert all(len(v) == 5 for v in table.values())


def test_carry_costs_prefers_carries_then_all():
    comp = Comp(
        slug="x",
        name="X",
        carry_items={"carry a": ["item"]},
        unit_costs={"carry a": 4, "filler b": 2},
    )
    assert comp.carry_costs() == [4]
    assert Comp(slug="y", name="Y", unit_costs={"u": 3}).carry_costs() == [3]
    assert Comp(slug="z", name="Z").carry_costs() == []


def _pool(**kwargs) -> Pool:
    return pool_from_state(GameState(**kwargs), {"ashe": 4, "tank": 1})


def test_pool_from_state_counts_star_copies():
    pool = _pool(board=[Unit(name="Ashe", star=3)])
    assert pool.taken["ashe"] == 9
    assert pool.unit_left("ashe") == 1  # 10 in a 4-cost bag, 9 out


def test_pool_counts_shop_and_scouted_rivals():
    pool = _pool(
        shop=["Ashe", "Tank"],
        opponents=[Opponent(name="r", units=[Unit(name="Ashe", star=2)])],
    )
    assert pool.taken["ashe"] == 4  # 1 in shop + 3 from rival's 2*
    assert pool.taken["tank"] == 1


def test_pool_depletion_lowers_hit_chance():
    full = hit_chance(8, [4], pool=_pool(), units=["Ashe"])
    thin = hit_chance(
        8,
        [4],
        pool=_pool(opponents=[Opponent(name="r", units=[Unit(name="Ashe", star=3)])]),
        units=["Ashe"],
    )
    assert thin < full
    assert full == hit_chance(8, [4])  # untouched pool = full-bag assumption


def test_unit_without_cost_falls_back_to_full_bag():
    pool = _pool(board=[Unit(name="Mystery", star=3)])  # unknown unit: not counted
    assert "mystery" not in pool.taken
    assert pool.unit_left("Mystery") is None


def test_roll_window_reports_copies():
    w = roll_window(
        8, [4], pool=_pool(board=[Unit(name="Ashe", star=2)]), units=["Ashe"]
    )
    assert w["copies"] == {"Ashe": "7/10"}
