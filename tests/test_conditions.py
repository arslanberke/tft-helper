import pytest
from tft_advisor.comps import (
    Comp,
    CompConditions,
    SourceRating,
    entry_signals,
    pivot_candidates,
)
from tft_advisor.sources.base import RawComp
from tft_advisor.sources.merge import merge_sources
from tft_advisor.state import GameState, Opponent, Unit


def _comp(slug: str, **kw) -> Comp:
    return Comp(slug=slug, name=slug.title(), **kw)


def test_entry_scores_all_matched_conditions():
    comp = _comp(
        "a",
        conditions=CompConditions(
            openers=["ahri"], items=["blue buff"], augments=["mana surge"]
        ),
    )
    state = GameState(
        board=[Unit(name="Ahri", items=["Blue Buff"])],
        offered_augments=["Mana Surge", "Other"],
    )
    sig = entry_signals(state, comp)
    assert sig.score == pytest.approx(1.0)
    assert sig.matched == ["ahri", "blue buff", "mana surge"]
    assert sig.missing == []


def test_entry_reports_missing_conditions():
    comp = _comp("a", conditions=CompConditions(openers=["ahri"], items=["blue buff"]))
    sig = entry_signals(GameState(board=[Unit(name="Ahri")]), comp)
    assert sig.matched == ["ahri"]
    assert sig.missing == ["blue buff"]
    assert 0.0 < sig.score < 1.0


def test_entry_without_conditions_is_neutral():
    sig = entry_signals(GameState(), _comp("a"))
    assert sig.score == pytest.approx(0.5)
    assert sig.matched == [] and sig.missing == []


def test_pivot_prefers_shared_units_and_tier():
    cur = _comp("cur", units=["ahri", "braum"])
    shares = _comp(
        "shares", units=["ahri", "braum", "x"], sources=[SourceRating(site="s", tier="S")]
    )
    other = _comp("other", units=["zed"], sources=[SourceRating(site="s", tier="D")])
    options = pivot_candidates(GameState(), cur, [cur, shares, other])
    assert options[0].slug == "shares"
    assert options[0].shared == 2
    assert all(o.slug != "cur" for o in options)


def test_pivot_penalizes_contested_candidates():
    cur = _comp("cur", units=["ahri", "braum"])
    contested = _comp("hot", units=["ahri", "zed"], sources=[SourceRating(site="s", tier="S")])
    clean = _comp("clean", units=["ahri", "yas"], sources=[SourceRating(site="s", tier="S")])
    state = GameState(
        opponents=[Opponent(name="r", units=[Unit(name="ahri"), Unit(name="zed")])]
    )
    options = pivot_candidates(state, cur, [cur, contested, clean])
    assert options[0].slug == "clean"
    assert options[1].slug == "hot"
    assert options[1].contested == 1


def test_merge_unions_conditions_from_sites():
    raws = [
        [
            RawComp(
                site="a",
                slug="x",
                name="X",
                conditions={"openers": ["u1"], "econ": "fast8", "strategy": "hit 8 fast"},
            ),
            RawComp(
                site="b",
                slug="x",
                name="X",
                conditions={"openers": ["u2"], "augments": ["aug1"], "pivot_slugs": ["y"]},
            ),
        ]
    ]
    merged = merge_sources(raws)
    assert len(merged) == 1
    comp = merged[0]
    assert comp.conditions.openers == ["u1", "u2"]
    assert comp.conditions.augments == ["aug1"]
    assert comp.conditions.econ == "fast8"
    assert comp.strategy == "hit 8 fast"
    assert comp.pivot_slugs == ["y"]
