from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel, Field

TIER_VALUE = {"S": 5.0, "A": 4.0, "B": 3.0, "C": 2.0, "D": 1.0}


class SourceRating(BaseModel):
    """How one meta site ranks this comp."""

    site: str
    tier: str = ""
    rank: int | None = None


class Comp(BaseModel):
    slug: str
    name: str
    units: list[str] = Field(default_factory=list)
    traits: list[str] = Field(default_factory=list)
    carry_items: dict[str, list[str]] = Field(default_factory=dict)
    augment_priority: list[str] = Field(default_factory=list)
    sources: list[SourceRating] = Field(default_factory=list)

    def consensus_tier(self) -> str:
        """Blend per-site tiers into one letter. Missing sources don't vote."""
        tiers = [TIER_VALUE[s.tier.upper()] for s in self.sources if s.tier.upper() in TIER_VALUE]
        if not tiers:
            return "?"
        avg = sum(tiers) / len(tiers)
        for letter, value in TIER_VALUE.items():
            if avg >= value:
                return letter
        return "D"

    def describe(self) -> str:
        """Criteria text shown to the decision model for this comp."""
        parts = [self.name]
        if self.units:
            parts.append(f"core units: {', '.join(self.units)}")
        if self.traits:
            parts.append(f"traits: {', '.join(self.traits)}")
        if self.carry_items:
            items = "; ".join(f"{c} -> {', '.join(i)}" for c, i in self.carry_items.items())
            parts.append(f"carry items: {items}")
        tier = self.consensus_tier()
        if tier != "?":
            parts.append(f"meta tier {tier} ({len(self.sources)} sources)")
        return ". ".join(parts)


def load_library(path: str | Path) -> list[Comp]:
    data = json.loads(Path(path).read_text())
    return [Comp.model_validate(c) for c in data["comps"]]


def contested_count(
    comp_units: list[str], opponent_units: list[list[str]], min_overlap: int = 2
) -> int:
    """How many opponents share at least `min_overlap` core units with the comp."""
    core = {u.lower() for u in comp_units}
    return sum(
        1 for units in opponent_units if len(core & {u.lower() for u in units}) >= min_overlap
    )
