"""Best-effort parsers for meta-site tier lists.

None of these sites publish a stable public API, so each adapter takes a raw
JSON payload (from a configured endpoint or a saved export) and normalizes it
into RawComp. Parsers tolerate missing fields; a site that changes its shape
simply yields fewer/empty entries rather than crashing the merge.

Configure endpoints in service/data/sources.json:
    {"sources": [{"site": "tactics_tools", "url": "https://.../tierlist.json"}, ...]}
`url` may also be a local file path for manual exports.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path

import httpx

from .base import RawComp, slugify


def _num(entry: dict, *keys: str) -> float | None:
    for key in keys:
        value = entry.get(key)
        if isinstance(value, int | float):
            return float(value)
        if isinstance(value, str):
            try:
                return float(value.rstrip("%")) / (100.0 if value.endswith("%") else 1.0)
            except ValueError:
                continue
    return None


def _rate(entry: dict, *keys: str) -> float | None:
    """A 0..1 rate; sites report these as either fractions or percentages."""
    value = _num(entry, *keys)
    if value is None:
        return None
    return value / 100.0 if value > 1.0 else value


def _tier(rank: int, total: int) -> str:
    frac = rank / max(total, 1)
    if frac <= 0.1:
        return "S"
    if frac <= 0.3:
        return "A"
    if frac <= 0.6:
        return "B"
    return "C"


def parse_tactics_tools(payload: dict) -> list[RawComp]:
    comps: list[RawComp] = []
    entries = payload.get("comps") or payload.get("data") or []
    total = len(entries)
    for i, entry in enumerate(entries, start=1):
        if not isinstance(entry, dict):
            continue
        name = entry.get("name") or entry.get("title") or ""
        if not name:
            continue
        units = [
            u.get("name") or u.get("unit") or ""
            for u in entry.get("units", [])
            if isinstance(u, dict)
        ]
        traits = [
            t.get("name") or ""
            for t in entry.get("traits", [])
            if isinstance(t, dict)
        ]
        comps.append(
            RawComp(
                site="tactics.tools",
                slug=slugify(entry.get("id") or name),
                name=name,
                tier=(entry.get("tier") or _tier(i, total)),
                rank=i,
                units=[u for u in units if u],
                traits=[t for t in traits if t],
            )
        )
    return comps


def parse_metatft(payload: dict) -> list[RawComp]:
    comps: list[RawComp] = []
    entries = payload.get("comps") or payload.get("data") or []
    total = len(entries)
    for i, entry in enumerate(entries, start=1):
        if not isinstance(entry, dict):
            continue
        name = entry.get("name") or entry.get("comp") or ""
        if not name:
            continue
        units = [u for u in (entry.get("units") or []) if isinstance(u, str)]
        comps.append(
            RawComp(
                site="metatft",
                slug=slugify(name),
                name=name,
                tier=(entry.get("tier") or _tier(i, total)),
                rank=i,
                units=units,
            )
        )
    return comps


def parse_generic(site: str) -> Callable[[dict], list[RawComp]]:
    """Fallback for sites (Mobalytics, TFT Academy, ...) that expose a flat list
    of {name, tier, units?} entries."""

    def parse(payload: dict) -> list[RawComp]:
        comps: list[RawComp] = []
        entries = payload if isinstance(payload, list) else payload.get("comps", [])
        total = len(entries)
        for i, entry in enumerate(entries, start=1):
            if not isinstance(entry, dict):
                continue
            name = entry.get("name") or entry.get("title") or ""
            if not name:
                continue
            conditions = entry.get("when_to_play") or entry.get("conditions") or {}
            if not isinstance(conditions, dict):
                conditions = {}
            for key in ("strategy", "reroll_level", "pivot_slugs"):
                if key in entry and key not in conditions:
                    conditions[key] = entry[key]
            raw_units = entry.get("units") or []
            units: list[str] = []
            unit_costs: dict[str, int] = {}
            for u in raw_units:
                if isinstance(u, str):
                    units.append(u)
                elif isinstance(u, dict) and (u.get("name") or u.get("unit")):
                    uname = u.get("name") or u.get("unit")
                    units.append(uname)
                    if isinstance(u.get("cost"), int | float):
                        unit_costs[uname] = int(u["cost"])
            comps.append(
                RawComp(
                    site=site,
                    slug=slugify(name),
                    name=name,
                    tier=str(entry.get("tier") or _tier(i, total)),
                    rank=i,
                    units=units,
                    traits=[t for t in entry.get("traits", []) if isinstance(t, str)],
                    conditions=conditions,
                    unit_costs=unit_costs,
                    avg_place=_num(entry, "avg_place", "average_place", "placement"),
                    top4=_rate(entry, "top4", "top4_rate"),
                    pick_rate=_rate(entry, "pick_rate", "play_rate"),
                )
            )
        return comps

    return parse


PARSERS: dict[str, Callable[[dict], list[RawComp]]] = {
    "tactics_tools": parse_tactics_tools,
    "metatft": parse_metatft,
    "mobalytics": parse_generic("mobalytics"),
    "tft_academy": parse_generic("tftacademy"),
}


def fetch_source(site: str, url: str, timeout: float = 20.0) -> list[RawComp]:
    """Fetch and parse one site's payload. Returns [] on any failure."""
    parser = PARSERS.get(site, parse_generic(site))
    try:
        if url.startswith(("http://", "https://")):
            resp = httpx.get(url, timeout=timeout, follow_redirects=True)
            resp.raise_for_status()
            payload = resp.json()
        else:
            payload = json.loads(Path(url).read_text())
    except Exception as exc:  # noqa: BLE001 - a broken site must not kill the build
        print(f"[sources] {site}: fetch failed ({exc}) — skipping")
        return []
    try:
        return parser(payload)
    except Exception as exc:  # noqa: BLE001
        print(f"[sources] {site}: parse failed ({exc}) — skipping")
        return []
