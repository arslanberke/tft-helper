"""Regenerate service/data/comps.json from the configured meta sources.

Every configured site is fetched and normalized to RawComp, then merged into
the consensus library (per-site ratings preserved). Manual comps in
service/data/comps_manual.json are merged in and survive regeneration.

Usage: python service/scripts/build_comp_library.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tft_advisor.comps import Comp  # noqa: E402
from tft_advisor.sources.merge import merge_sources  # noqa: E402
from tft_advisor.sources.sites import fetch_source  # noqa: E402

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


def main() -> None:
    config = json.loads((DATA_DIR / "sources.json").read_text())
    groups = []
    for entry in config.get("sources", []):
        url = entry.get("url") or ""
        if not url:
            print(f"[sources] {entry['site']}: no url configured — skipping")
            continue
        raws = fetch_source(entry["site"], url)
        print(f"[sources] {entry['site']}: {len(raws)} comps")
        groups.append(raws)

    manual: list[Comp] = []
    manual_path = DATA_DIR / "comps_manual.json"
    if manual_path.exists():
        manual = [Comp.model_validate(c) for c in json.loads(manual_path.read_text())["comps"]]
        print(f"[sources] manual: {len(manual)} comps")

    merged = merge_sources(groups, manual)
    out = {"comps": [c.model_dump() for c in merged]}
    dest = DATA_DIR / "comps.json"
    dest.write_text(json.dumps(out, indent=2))
    print(f"wrote {len(merged)} comps -> {dest}")


if __name__ == "__main__":
    main()
