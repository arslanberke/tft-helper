import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "service"))

from tft_advisor.comps import Comp, SourceRating  # noqa: E402
from tft_advisor.sources.base import RawComp  # noqa: E402
from tft_advisor.sources.merge import merge_sources  # noqa: E402


def test_same_comp_across_sites_merges_sources() -> None:
    a = [RawComp(site="tactics.tools", slug="x", name="X", tier="S", units=["u1"])]
    b = [RawComp(site="metatft", slug="x", name="X", tier="A", units=["u2"])]
    merged = merge_sources([a, b])

    assert len(merged) == 1
    comp = merged[0]
    assert {s.site for s in comp.sources} == {"tactics.tools", "metatft"}
    assert set(comp.units) == {"u1", "u2"}
    assert comp.consensus_tier() == "A"  # (5+4)/2 -> A


def test_manual_comps_survive() -> None:
    manual = [Comp(slug="mine", name="Mine", sources=[SourceRating(site="me", tier="B")])]
    merged = merge_sources([[]], manual)
    assert [c.slug for c in merged] == ["mine"]


def test_unknown_tiers_dont_crash_consensus() -> None:
    comp = Comp(slug="c", name="C", sources=[SourceRating(site="s", tier="?")])
    assert comp.consensus_tier() == "?"
