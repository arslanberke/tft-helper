"""Fetch the current TFT set's static data (champions, traits, augments) from
CommunityDragon and write service/data/set_data.json.

Usage: python service/scripts/fetch_set_data.py [--icons]
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import httpx

CDRAGON_TFT = "https://raw.communitydragon.org/latest/cdragon/tft/en_us.json"
CDN_ASSET = "https://raw.communitydragon.org/latest/game/"
DATA_DIR = Path(__file__).resolve().parent.parent / "data"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--icons", action="store_true", help="also download trait/champion icons")
    args = parser.parse_args()

    payload = httpx.get(CDRAGON_TFT, timeout=30).json()
    sets = payload.get("sets") or payload.get("setData") or {}
    # CommunityDragon keys sets by number; the newest entry is the live set.
    numeric = lambda k: float(k) if str(k).replace(".", "").isdigit() else 0  # noqa: E731
    latest_key = sorted(sets, key=numeric)[-1]
    current = sets[latest_key]

    out = {
        "set": latest_key,
        "name": current.get("name", ""),
        "champions": [
            {
                "apiName": c.get("apiName"),
                "name": c.get("name"),
                "cost": c.get("cost"),
                "traits": c.get("traits", []),
                "icon": c.get("icon"),
            }
            for c in current.get("champions", [])
        ],
        "traits": [
            {"apiName": t.get("apiName"), "name": t.get("name"), "icon": t.get("icon")}
            for t in current.get("traits", [])
        ],
        "items": current.get("items", []),
        "augments": [
            {"apiName": a.get("apiName"), "name": a.get("name"), "icon": a.get("icon")}
            for a in payload.get("augments", current.get("augments", []))
        ],
    }

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    dest = DATA_DIR / "set_data.json"
    dest.write_text(json.dumps(out, indent=2))
    print(f"set {out['set']} ({out['name']}): {len(out['champions'])} champions, "
          f"{len(out['traits'])} traits, {len(out['augments'])} augments -> {dest}")

    if args.icons:
        icons_dir = DATA_DIR / "icons"
        icons_dir.mkdir(exist_ok=True)
        for entry in out["champions"] + out["traits"] + out["augments"]:
            icon = entry.get("icon")
            if not icon:
                continue
            url = CDN_ASSET + icon.lower().replace(".tex", ".png")
            target = icons_dir / Path(icon).name.replace(".tex", ".png")
            if target.exists():
                continue
            try:
                target.write_bytes(httpx.get(url, timeout=30).content)
            except Exception as exc:  # noqa: BLE001
                print(f"icon fetch failed {url}: {exc}")
        print(f"icons -> {icons_dir}")


if __name__ == "__main__":
    main()
