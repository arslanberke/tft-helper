"""Deterministic roll-odds helpers.

TFT shops roll 5 independent slots; each slot picks a cost tier by level, then a
champion of that tier from the shared pool. `hit_chance` is the probability of
seeing at least one wanted unit in a single refresh (ignoring pool depletion,
which slightly favors you as the lobby drains shared units).

Odds are the standard per-set table; patches shift them slightly, so the table
lives here in one place — override via TFT_SHOP_ODDS (path to a JSON file of
the same shape) when a set changes it.
"""

from __future__ import annotations

import json
import os
from functools import lru_cache

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

# champions of each cost in the shared pool (set-typical values)
_POOL_SIZES = {1: 30, 2: 25, 3: 18, 4: 10, 5: 9}
_SLOTS_PER_SHOP = 5


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


def _tier_odds(level: int, cost: int) -> float:
    table = shop_odds()
    if not table:
        return 0.0
    level = max(min(level, max(table)), min(table))
    tiers = table[level]
    return tiers[cost - 1] if 1 <= cost <= len(tiers) else 0.0


def hit_chance(level: int, costs: list[int]) -> float:
    """P(at least one wanted unit in a 5-slot refresh).

    `costs` lists the cost of every wanted unit; each contributes
    tier_odds/pool_size per slot, so duplicates of the same cost stack.
    """
    if level <= 0 or not costs:
        return 0.0
    per_slot = sum(_tier_odds(level, c) / _POOL_SIZES.get(c, 1) for c in costs)
    return round(1.0 - (1.0 - min(per_slot, 1.0)) ** _SLOTS_PER_SHOP, 3)


def best_roll_level(costs: list[int]) -> int | None:
    """Level with the highest per-shop hit chance for the wanted unit costs."""
    if not costs:
        return None
    table = shop_odds()
    return max(table, key=lambda lv: hit_chance(lv, costs))


def roll_window(level: int, costs: list[int]) -> dict:
    """Roll-now vs level-up comparison for a comp's key unit costs."""
    best = best_roll_level(costs)
    return {
        "hit_now": hit_chance(level, costs),
        "best_level": best,
        "hit_best": hit_chance(best, costs) if best else 0.0,
        "hit_next": hit_chance(level + 1, costs),
    }
