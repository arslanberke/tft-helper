"""Download TFT champion tile icons for the screen-scout matcher.

Pulls the current set's champion list from CommunityDragon and saves each
champion's icon to service/data/champ_icons/<Name>.png. Run:

    python -m service.scripts.fetch_champ_icons            # latest set
    python -m service.scripts.fetch_champ_icons --set 14   # specific set
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path

import httpx

CDRAGON_JSON = "https://raw.communitydragon.org/latest/cdragon/tft/en_us.json"
ASSETS = "https://raw.communitydragon.org/latest/game"
OUT_DIR = Path(__file__).resolve().parent.parent / "data" / "champ_icons"


def _latest_set(data: dict) -> str:
    keys = [k for k in data.get("setData", data) if re.fullmatch(r"TFTSet\d+", k)]
    if not keys:
        keys = [k for k in data.get("setData", data) if re.fullmatch(r"\d+", k)]
    if not keys:
        raise SystemExit("could not locate set data in communitydragon json")
    return sorted(keys, key=lambda k: int(re.sub(r"\D", "", k)))[-1]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--set", dest="set_num", default=None, help="TFT set number")
    args = parser.parse_args()

    data = httpx.get(CDRAGON_JSON, timeout=30).json()
    set_num = args.set_num or re.sub(r"\D", "", _latest_set(data))

    champs: dict[str, str] = {}
    for set_data in data.get("setData", {}).values():
        for ch in set_data.get("champions", []):
            api = ch.get("apiName", "")
            if not api.startswith(f"TFT{set_num}_"):
                continue
            name = ch.get("name") or api.split("_", 1)[-1]
            icon = ch.get("icon") or ""
            url = icon if icon.startswith("http") else f"{ASSETS}/{icon.lower()}"
            champs[re.sub(r"\s", "", name)] = url
    if not champs:
        raise SystemExit(f"no champions found for set {set_num}")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    ok = 0
    for name, url in sorted(champs.items()):
        dest = OUT_DIR / f"{name}.png"
        try:
            resp = httpx.get(url, timeout=30, follow_redirects=True)
            resp.raise_for_status()
        except Exception:
            continue
        dest.write_bytes(resp.content)
        ok += 1
    print(f"saved {ok}/{len(champs)} champion icons to {OUT_DIR}")


if __name__ == "__main__":
    main()
