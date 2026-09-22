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


class CompConditions(BaseModel):
    """"When to play" triggers merged from meta-site guides.

    Each list holds free-text terms (unit/trait/augment/item names) matched
    loosely against the live game state; `econ` describes the comp's game plan.
    """

    openers: list[str] = Field(default_factory=list)  # good early units/traits
    augments: list[str] = Field(default_factory=list)  # augments that unlock it
    items: list[str] = Field(default_factory=list)  # needed components/items
    econ: str = ""  # reroll | fast8 | fast9 | ...


class Positioning(BaseModel):
    """Board placement guide: which units hold the front vs the back line."""

    frontline: list[str] = Field(default_factory=list)  # tanks / melee up front
    backline: list[str] = Field(default_factory=list)  # carries / squishies behind
    notes: str = ""  # e.g. "corner-stack carries vs hook units"


class Comp(BaseModel):
    slug: str
    name: str
    units: list[str] = Field(default_factory=list)
    traits: list[str] = Field(default_factory=list)
    carry_items: dict[str, list[str]] = Field(default_factory=dict)
    augment_priority: list[str] = Field(default_factory=list)
    conditions: CompConditions = Field(default_factory=CompConditions)
    strategy: str = ""  # e.g. "Fast 8 tempo", "Slow roll at 7"
    reroll_level: int | None = None
    pivot_slugs: list[str] = Field(default_factory=list)  # suggested fallbacks
    positioning: Positioning = Field(default_factory=Positioning)
    substitutes: dict[str, list[str]] = Field(default_factory=dict)  # unit -> fallback units
    endgame: str = ""  # late-game upgrade plan (e.g. "at 9 add legendary X")
    unit_costs: dict[str, int] = Field(default_factory=dict)  # unit name -> shop cost
    avg_place: float | None = None  # meta-site placement stats
    top4: float | None = None  # top-4 rate, 0..1
    pick_rate: float | None = None
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
        when = _condition_terms(self.conditions)
        if when:
            parts.append(f"play when: {when}")
        if self.strategy:
            parts.append(f"strategy: {self.strategy}")
        pos = _positioning_terms(self.positioning)
        if pos:
            parts.append(f"positioning: {pos}")
        if self.substitutes:
            subs = "; ".join(f"{u} -> {', '.join(s)}" for u, s in self.substitutes.items())
            parts.append(f"substitutes: {subs}")
        if self.endgame:
            parts.append(f"endgame: {self.endgame}")
        stats = []
        if self.avg_place is not None:
            stats.append(f"avg place {self.avg_place}")
        if self.top4 is not None:
            stats.append(f"top4 {self.top4:.0%}")
        if stats:
            parts.append("meta stats: " + ", ".join(stats))
        return ". ".join(parts)

    def carry_costs(self) -> list[int]:
        """Shop costs of the comp's key units (carries first, then the rest)."""
        carries = [
            self.unit_costs[c] for c in self.carry_items if c in self.unit_costs
        ]
        if carries:
            return carries
        return list(self.unit_costs.values())


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


def _condition_terms(conditions: CompConditions) -> str:
    bits = conditions.openers + conditions.augments + conditions.items
    if conditions.econ:
        bits.append(f"{conditions.econ} game plan")
    return ", ".join(bits)


def _positioning_terms(pos: Positioning) -> str:
    bits: list[str] = []
    if pos.frontline:
        bits.append(f"front: {', '.join(pos.frontline)}")
    if pos.backline:
        bits.append(f"back: {', '.join(pos.backline)}")
    if pos.notes:
        bits.append(pos.notes)
    return " · ".join(bits)


_COND_WEIGHTS = {"openers": 0.45, "items": 0.30, "augments": 0.25}


class EntrySignal(BaseModel):
    """How strongly the live game state matches a comp's "when to play" terms."""

    score: float  # 0..1; 0.5 means "no conditions known"
    matched: list[str] = Field(default_factory=list)
    missing: list[str] = Field(default_factory=list)


def _haystack(state) -> str:
    units = state.board + state.bench
    parts = [u.name for u in units]
    parts += state.shop + state.items + state.offered_augments + state.picked_augments
    parts += [i for u in units for i in u.items]
    return " ".join(p.lower() for p in parts if p)


def _match(haystack: str, terms: list[str]) -> tuple[list[str], list[str]]:
    matched = [t for t in terms if t.lower() in haystack]
    return matched, [t for t in terms if t.lower() not in haystack]


def entry_signals(state, comp: Comp) -> EntrySignal:
    """Score how many of the comp's play conditions the current state satisfies."""
    haystack = _haystack(state)
    matched: list[str] = []
    missing: list[str] = []
    score = 0.0
    weight_sum = 0.0
    for field, weight in _COND_WEIGHTS.items():
        terms = getattr(comp.conditions, field)
        if not terms:
            continue
        weight_sum += weight
        hit, miss = _match(haystack, terms)
        matched += hit
        missing += miss
        score += weight * (len(hit) / len(terms))
    if weight_sum == 0:
        return EntrySignal(score=0.5)
    return EntrySignal(score=round(score / weight_sum, 3), matched=matched, missing=missing)


class PivotOption(BaseModel):
    slug: str
    name: str
    shared: int  # core units shared with the current comp
    entry: float  # the candidate's own entry score
    contested: int
    score: float  # blended rank


def pivot_candidates(state, comp: Comp, library: list[Comp], top_n: int = 2) -> list[PivotOption]:
    """Rank fallback comps by shared core units, meta tier, entry fit and
    how contested they are — mirrors the "pivot suggestions" meta sites give."""
    opponent_units = [[u.name for u in o.units] for o in state.opponents]
    core = {u.lower() for u in comp.units}
    options: list[PivotOption] = []
    for other in library:
        if other.slug == comp.slug:
            continue
        shared = len(core & {u.lower() for u in other.units})
        entry = entry_signals(state, other)
        contested = contested_count(other.units, opponent_units)
        tier = TIER_VALUE.get(other.consensus_tier(), 0.0) / 5.0
        score = (
            0.45 * (shared / max(len(core), 1))
            + 0.30 * entry.score
            + 0.25 * tier
            - 0.10 * contested
            + (0.15 if other.slug in comp.pivot_slugs else 0.0)
        )
        options.append(
            PivotOption(
                slug=other.slug,
                name=other.name,
                shared=shared,
                entry=entry.score,
                contested=contested,
                score=round(score, 3),
            )
        )
    options.sort(key=lambda o: o.score, reverse=True)
    return options[:top_n]
