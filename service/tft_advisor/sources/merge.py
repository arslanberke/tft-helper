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

    for comp in manual or []:
        target = ensure(comp.slug, comp.name)
        target.units = sorted(set(target.units) | set(comp.units))
        target.traits = sorted(set(target.traits) | set(comp.traits))
        target.carry_items.update(comp.carry_items)
        target.augment_priority = sorted(set(target.augment_priority) | set(comp.augment_priority))
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
            comp.sources.append(SourceRating(site=raw.site, tier=raw.tier, rank=raw.rank))

    return sorted(by_slug.values(), key=lambda c: c.slug)
