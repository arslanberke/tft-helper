"""Patch-day refresh: pull fresh champion icons and rebuild the comp library
in one command. Run after a TFT patch once the meta sites have updated:

    python -m service.scripts.refresh_meta            # latest set
    python -m service.scripts.refresh_meta --set 14   # specific set

Best-effort: each step reports its own failure and the others continue.
After this, restart the advisor service and check the GEP "unmapped info"
logs in the Overwolf background console for renamed event keys.
"""

from __future__ import annotations

import argparse
import importlib
import sys
from pathlib import Path

# Repo root on sys.path so `service.scripts.*` resolves as a namespace package.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
# `service/` too, so the sibling scripts' own `tft_advisor` imports work.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

STEPS = ["fetch_champ_icons", "build_comp_library"]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--set", dest="set_num", default=None, help="TFT set number")
    args = parser.parse_args()
    sys.argv = [sys.argv[0]] + (["--set", args.set_num] if args.set_num else [])

    for step in STEPS:
        print(f"--- {step} ---")
        try:
            mod = importlib.import_module(f"service.scripts.{step}")
        except ImportError:
            try:
                mod = importlib.import_module(f"scripts.{step}")
            except ImportError as e:
                print(f"!! {step}: import failed ({e})")
                continue
        try:
            mod.main()
        except SystemExit as e:
            if e.code:
                print(f"!! {step}: exited with {e.code}")
        except Exception as e:  # noqa: BLE001 — patch-day tool, keep going
            print(f"!! {step}: failed ({e})")

    print(
        "\nDone. Reminders:\n"
        "  - restart the advisor service so the new comps/icons load\n"
        "  - meta sites may lag a patch by a few days — rerun this once they update\n"
        "  - if the board region moved in a UI update, recalibrate TFT_BOARD_REGION\n"
        "    using service/data/last_scout.png\n"
        "  - check the Overwolf background console for 'unmapped info' keys after the patch"
    )


if __name__ == "__main__":
    main()
