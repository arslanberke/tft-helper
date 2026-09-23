"""Cached access to the last fetched TFT set data (set_data.json).

`fetch_set_data.py` writes champion costs/traits, trait names, augment names
and — when CommunityDragon ships them — description text. `describe()` turns
those descriptions into short annotations the decision questions can embed,
so patch-specific augments/shop power-ups evaluate on what they actually do
rather than on name alone.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

_DATA_DIR = Path(__file__).resolve().parent.parent / "data"


@lru_cache
def data() -> dict:
    path = _DATA_DIR / "set_data.json"
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text())
    except Exception:
        return {}


def _desc(entry: dict) -> str:
    desc = entry.get("desc") or ""
    if not desc and isinstance(entry.get("ability"), dict):
        desc = entry["ability"].get("desc") or entry["ability"].get("name") or ""
    return str(desc).strip()


def describe(name: str) -> str:
    """Short description for a champion/trait/augment name ('' if unknown)."""
    key = name.strip().lower()
    if not key:
        return ""
    for group in ("augments", "traits", "champions"):
        for entry in data().get(group, []):
            if str(entry.get("name", "")).lower() == key:
                return _desc(entry)
    return ""


def annotated(name: str) -> str:
    """'name — description' when a description exists, else the bare name."""
    desc = describe(name)
    return f"{name} — {desc}" if desc else name
