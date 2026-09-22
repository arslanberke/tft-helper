from __future__ import annotations

import re
from dataclasses import dataclass, field


def slugify(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


@dataclass
class RawComp:
    """One site's view of a comp, before cross-site merge."""

    site: str
    slug: str
    name: str
    tier: str = ""
    rank: int | None = None
    units: list[str] = field(default_factory=list)
    traits: list[str] = field(default_factory=list)
    carry_items: dict[str, list[str]] = field(default_factory=dict)
    augment_priority: list[str] = field(default_factory=list)
    # "when to play" data: {openers, augments, items, econ, strategy, reroll_level, pivot_slugs}
    conditions: dict = field(default_factory=dict)
    # board placement data: {frontline, backline, notes}
    positioning: dict = field(default_factory=dict)
    substitutes: dict[str, list[str]] = field(default_factory=dict)  # unit -> fallbacks
    endgame: str = ""  # late-game upgrade plan
    tank_items: dict[str, list[str]] = field(default_factory=dict)
    item_priority: list[str] = field(default_factory=list)
    item_holders: dict[str, list[str]] = field(default_factory=dict)
    item_plan: str = ""
    unit_costs: dict[str, int] = field(default_factory=dict)
    avg_place: float | None = None
    top4: float | None = None
    pick_rate: float | None = None
