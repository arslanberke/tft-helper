import pytest
from tft_advisor.comps import Comp
from tft_advisor.odds import best_roll_level, hit_chance, roll_window, shop_odds


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
