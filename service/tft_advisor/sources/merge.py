from __future__ import annotations

from ..comps import Comp, SourceRating
from .base import RawComp


def merge_sources(raw_groups: list[list[RawComp]], manual: list[Comp] | None = None) -> list[Comp]:
    """Merge per-site RawComp lists into one Comp per slug.

    Every site contributes a SourceRating (its tier/rank); units, traits and
    items are unioned across sites. Manual comps always merge in too so
    hand-maintained entries survive regeneration.
    """
    by_slug: dict[str, Comp] = {}

    def ensure(slug: str, name: str) -> Comp:
        comp = by_slug.get(slug)
        if comp is None:
            comp = by_slug[slug] = Comp(slug=slug, name=name)
        return comp

    def merge_conditions(target: Comp, cond: dict) -> None:
        for field in ("openers", "augments", "items"):
            terms = cond.get(field) or []
            existing = getattr(target.conditions, field)
            merged = sorted(set(existing) | {t for t in terms if t})
            setattr(target.conditions, field, merged)
        if cond.get("econ") and not target.conditions.econ:
            target.conditions.econ = str(cond["econ"])
        if cond.get("strategy") and not target.strategy:
            target.strategy = str(cond["strategy"])
        if cond.get("reroll_level") and target.reroll_level is None:
            target.reroll_level = int(cond["reroll_level"])
        pivots = cond.get("pivot_slugs") or []
        target.pivot_slugs = sorted(set(target.pivot_slugs) | set(pivots))

    for comp in manual or []:
        target = ensure(comp.slug, comp.name)
        target.units = sorted(set(target.units) | set(comp.units))
        target.traits = sorted(set(target.traits) | set(comp.traits))
        target.carry_items.update(comp.carry_items)
        target.augment_priority = sorted(set(target.augment_priority) | set(comp.augment_priority))
        merge_conditions(
            target,
            {
                **comp.conditions.model_dump(),
                "strategy": comp.strategy,
                "reroll_level": comp.reroll_level,
                "pivot_slugs": comp.pivot_slugs,
            },
        )
        target.sources.extend(comp.sources)

    for group in raw_groups:
        for raw in group:
            comp = ensure(raw.slug, raw.name)
            comp.units = sorted(set(comp.units) | set(raw.units))
            comp.traits = sorted(set(comp.traits) | set(raw.traits))
            for carry, items in raw.carry_items.items():
                comp.carry_items[carry] = sorted(set(comp.carry_items.get(carry, [])) | set(items))
            comp.augment_priority = sorted(
                set(comp.augment_priority) | set(raw.augment_priority)
            )
            merge_conditions(comp, raw.conditions)
            for unit, cost in raw.unit_costs.items():
                comp.unit_costs.setdefault(unit, cost)
            for stat in ("avg_place", "top4", "pick_rate"):
                value = getattr(raw, stat)
                if value is not None and getattr(comp, stat) is None:
                    setattr(comp, stat, value)
            comp.sources.append(SourceRating(site=raw.site, tier=raw.tier, rank=raw.rank))

    return sorted(by_slug.values(), key=lambda c: c.slug)
