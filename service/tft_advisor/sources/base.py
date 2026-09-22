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
