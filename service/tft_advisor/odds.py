"""Deterministic roll-odds + shared-pool helpers.

TFT shops roll 5 independent slots; each slot picks a cost tier by level, then a
champion of that tier from the shared pool. The pool is finite: every unit
bought, scouted on a rival's board, or seen in your shop is a copy out of the
bag until it's sold or its owner is eliminated. `Pool` tracks the copies we can
see (own board/bench/shop + scouted opponents) so `hit_chance` reflects pool
depletion — contested units get genuinely harder to hit.

Units granted by augments/orbs/drops also come from the pool, but Riot lets
those sources force a copy when the bag is empty (e.g. Neeko's Help) — that
extra copy never returns to the bag, so taken-counts are a lower bound, not a
cap.

Odds and pool sizes are per-set tables; patches shift them slightly, so they
live here in one place — override via TFT_SHOP_ODDS / TFT_POOL (paths to JSON
files) when a set changes them.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

# level -> [1-cost, 2-cost, 3-cost, 4-cost, 5-cost] slot probabilities
_DEFAULT_ODDS = {
    2: [1.00, 0.00, 0.00, 0.00, 0.00],
    3: [0.75, 0.25, 0.00, 0.00, 0.00],
    4: [0.55, 0.30, 0.15, 0.00, 0.00],
    5: [0.45, 0.33, 0.18, 0.04, 0.00],
    6: [0.30, 0.35, 0.25, 0.10, 0.00],
    7: [0.19, 0.30, 0.28, 0.20, 0.03],
    8: [0.18, 0.25, 0.28, 0.22, 0.07],
    9: [0.10, 0.15, 0.25, 0.30, 0.20],
    10: [0.05, 0.10, 0.20, 0.35, 0.30],
    11: [0.01, 0.02, 0.12, 0.50, 0.35],
}

# copies of each champion in the shared pool, per cost (set-typical values)
_POOL_SIZES = {1: 30, 2: 25, 3: 18, 4: 10, 5: 9}
# distinct champions per cost — a tier's whole bag is size × champs copies
_CHAMPS_PER_COST = {1: 13, 2: 13, 3: 13, 4: 13, 5: 9}
_SLOTS_PER_SHOP = 5
_STAR_COPIES = {1: 1, 2: 3, 3: 9, 4: 27}
_DATA_DIR = Path(__file__).resolve().parent.parent / "data"


@lru_cache
def shop_odds() -> dict[int, list[float]]:
    path = os.environ.get("TFT_SHOP_ODDS")
    if path:
        try:
            raw = json.loads(open(path).read())  # noqa: SIM115
            return {int(k): v for k, v in raw.items()}
        except Exception:
            pass
    return _DEFAULT_ODDS


@lru_cache
def pool_table() -> dict[str, dict[int, int]]:
    """{'sizes': cost -> copies per champion, 'champs': cost -> champions}.

    TFT_POOL may point to a JSON file of the same shape; set_data.json (when
    fetched) refines the distinct-champion counts for the live set.
    """
    table = {
        "sizes": dict(_POOL_SIZES),
        "champs": dict(_CHAMPS_PER_COST),
    }
    set_path = _DATA_DIR / "set_data.json"
    if set_path.exists():
        try:
            counts: dict[int, int] = {}
            for ch in json.loads(set_path.read_text()).get("champions", []):
                cost = ch.get("cost")
                if isinstance(cost, int) and cost > 0:
                    counts[cost] = counts.get(cost, 0) + 1
            table["champs"].update(counts)
        except Exception:
            pass
    path = os.environ.get("TFT_POOL")
    if path:
        try:
            raw = json.loads(open(path).read())  # noqa: SIM115
            for key in ("sizes", "champs"):
                if isinstance(raw.get(key), dict):
                    table[key].update({int(k): v for k, v in raw[key].items()})
        except Exception:
            pass
    return table


@lru_cache
def set_data_costs() -> dict[str, int]:
    """Unit name -> shop cost from the last fetched set data (lowercased)."""
    path = _DATA_DIR / "set_data.json"
    if not path.exists():
        return {}
    try:
        return {
            ch["name"].lower(): ch["cost"]
            for ch in json.loads(path.read_text()).get("champions", [])
            if ch.get("name") and isinstance(ch.get("cost"), int)
        }
    except Exception:
        return {}


@dataclass
class Pool:
    """Copies seen out of the shared bag: own board/bench/shop + scouted rivals."""

    taken: dict[str, int] = field(default_factory=dict)  # lower name -> copies out
    unit_costs: dict[str, int] = field(default_factory=dict)  # lower name -> cost

    def unit_left(self, name: str) -> int | None:
        cost = self.unit_costs.get(name.lower())
        if cost is None:
            return None
        size = pool_table()["sizes"].get(cost, 1)
        return max(0, size - self.taken.get(name.lower(), 0))

    def bag_left(self, cost: int) -> int:
        table = pool_table()
        total = table["sizes"].get(cost, 1) * table["champs"].get(cost, 1)
        out = sum(n for u, n in self.taken.items() if self.unit_costs.get(u) == cost)
        return max(1, total - out)

    def copies_str(self, name: str) -> str | None:
        left = self.unit_left(name)
        if left is None:
            return None
        size = pool_table()["sizes"].get(self.unit_costs[name.lower()], 1)
        return f"{left}/{size}"


def pool_from_state(state, comp_unit_costs: dict[str, int]) -> Pool:
    """Count pool copies visible in this snapshot.

    Own board/bench (star-scaled: a 2* unit holds 3 copies), shop slots (one
    copy each while shown), and scouted opponent boards. Unscouted rivals and
    force-generated copies (Neeko etc.) stay invisible — `taken` is a floor.
    """
    costs = {u.lower(): c for u, c in set_data_costs().items()}
    costs.update({u.lower(): c for u, c in comp_unit_costs.items()})
    taken: dict[str, int] = {}

    def take(name: str, star: int = 1) -> None:
        key = name.strip().lower()
        if key and key in costs:
            taken[key] = taken.get(key, 0) + _STAR_COPIES.get(star, 1)

    for u in state.board + state.bench:
        take(u.name, u.star)
    for name in state.shop:
        take(name)
    for opp in state.opponents:
        for u in opp.units:
            take(u.name, u.star)
    return Pool(taken=taken, unit_costs=costs)


def _tier_odds(level: int, cost: int) -> float:
    table = shop_odds()
    if not table:
        return 0.0
    level = max(min(level, max(table)), min(table))
    tiers = table[level]
    return tiers[cost - 1] if 1 <= cost <= len(tiers) else 0.0


def _slot_prob(level: int, cost: int, pool: Pool | None, name: str | None) -> float:
    """Per-slot chance of one specific champion of `cost`."""
    tier = _tier_odds(level, cost)
    if pool is None or name is None or pool.unit_left(name) is None:
        # Full bag assumption: tier odds spread over the tier's champions.
        return tier / pool_table()["champs"].get(cost, 1)
    return tier * pool.unit_left(name) / pool.bag_left(cost)


def hit_chance(
    level: int,
    costs: list[int],
    pool: Pool | None = None,
    units: list[str] | None = None,
) -> float:
    """P(at least one wanted unit in a 5-slot refresh).

    `costs` lists the cost of every wanted unit. When `pool` + `units` (same
    order) are given, each unit's chance uses its copies actually left in the
    bag; otherwise the full-bag assumption applies.
    """
    if level <= 0 or not costs:
        return 0.0
    per_slot = 0.0
    for i, c in enumerate(costs):
        name = units[i] if units and i < len(units) else None
        per_slot += _slot_prob(level, c, pool, name)
    return round(1.0 - (1.0 - min(per_slot, 1.0)) ** _SLOTS_PER_SHOP, 3)


def best_roll_level(
    costs: list[int],
    pool: Pool | None = None,
    units: list[str] | None = None,
) -> int | None:
    """Level with the highest per-shop hit chance for the wanted units."""
    if not costs:
        return None
    table = shop_odds()
    return max(table, key=lambda lv: hit_chance(lv, costs, pool, units))


def roll_window(
    level: int,
    costs: list[int],
    pool: Pool | None = None,
    units: list[str] | None = None,
) -> dict:
    """Roll-now vs level-up comparison for a comp's key units, pool-aware."""
    best = best_roll_level(costs, pool, units)
    out = {
        "hit_now": hit_chance(level, costs, pool, units),
        "best_level": best,
        "hit_best": hit_chance(best, costs, pool, units) if best else 0.0,
        "hit_next": hit_chance(level + 1, costs, pool, units),
    }
    if pool is not None and units:
        out["copies"] = {
            name: pool.copies_str(name)
            for name in units
            if pool.copies_str(name) is not None
        }
    return out
