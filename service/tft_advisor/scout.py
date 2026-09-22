"""Screen-based rival scouting.

When the player inspects a rival's board in-game, their 4x7 hex board is
rendered where the player's own board normally sits. This module captures
that region of the screen and template-matches each cell against champion
icons downloaded by `scripts/fetch_champ_icons.py`.

Requires the `scout` extra: pip install -e ".[scout]"
Board region defaults to a 1920x1080 layout; calibrate with TFT_BOARD_REGION
("x,y,w,h") for other resolutions. Icon directory: TFT_CHAMP_ICONS.
"""

from __future__ import annotations

import os
from pathlib import Path

ICON_DIR = Path(
    os.environ.get(
        "TFT_CHAMP_ICONS", Path(__file__).resolve().parent.parent / "data" / "champ_icons"
    )
)

# x, y, w, h of the board grid on screen (default tuned for 1920x1080).
DEFAULT_REGION = (640, 620, 640, 400)
GRID_ROWS = 4
GRID_COLS = 7
MATCH_THRESHOLD = 0.78
DEBUG_SHOT = Path(
    os.environ.get(
        "TFT_SCOUT_DEBUG",
        Path(__file__).resolve().parent.parent / "data" / "last_scout.png",
    )
)


def _imports():
    try:
        import cv2  # noqa: F401
        import mss  # noqa: F401
        import numpy as np  # noqa: F401
    except ImportError:
        return None
    return cv2, mss, np


def available() -> bool:
    return _imports() is not None


def _region() -> tuple[int, int, int, int]:
    raw = os.environ.get("TFT_BOARD_REGION", "")
    parts = [p.strip() for p in raw.split(",") if p.strip()]
    if len(parts) == 4:
        try:
            return tuple(int(p) for p in parts)  # type: ignore[return-value]
        except ValueError:
            pass
    return DEFAULT_REGION


def _load_icons() -> dict[str, object]:
    mods = _imports()
    if not mods:
        return {}
    cv2, _, _ = mods
    icons: dict[str, object] = {}
    for path in sorted(ICON_DIR.glob("*.png")):
        img = cv2.imread(str(path), cv2.IMREAD_COLOR)
        if img is not None:
            icons[path.stem] = img
    return icons


def capture_board():
    """Grab the board region of the primary monitor. Returns a BGR image."""
    mods = _imports()
    if not mods:
        return None
    cv2, mss, np = mods
    x, y, w, h = _region()
    with mss.mss() as sct:
        shot = sct.grab({"left": x, "top": y, "width": w, "height": h})
        img = np.array(shot)[:, :, :3]  # drop alpha -> BGR
    return img


def _cells(img):
    """Yield (row, col, cell-image) for the 4x7 hex grid inside the region.

    Odd rows are shifted right by half a cell (pointy-top hex layout).
    """
    h, w = img.shape[:2]
    cw, ch = w / GRID_COLS, h / GRID_ROWS
    for r in range(GRID_ROWS):
        for c in range(GRID_COLS):
            shift = (cw / 2) if r % 2 else 0
            x0 = int(c * cw + shift)
            x1 = int(x0 + cw)
            y0, y1 = int(r * ch), int((r + 1) * ch)
            yield r, c, img[y0:y1, x0:x1]


def detect_units(img, icons: dict[str, object] | None = None) -> list[dict]:
    """Best champion match per occupied cell: [{row, col, unit, score}]."""
    mods = _imports()
    if img is None or not mods:
        return []
    cv2, _, _ = mods
    icons = icons if icons is not None else _load_icons()
    if not icons:
        return []

    found: list[dict] = []
    for row, col, cell in _cells(img):
        if cell.size == 0:
            continue
        best_name, best_score = "", 0.0
        for name, icon in icons.items():
            res = cv2.matchTemplate(cell, icon, cv2.TM_CCOEFF_NORMED)
            score = float(res.max())
            if score > best_score:
                best_name, best_score = name, score
        if best_score >= MATCH_THRESHOLD:
            found.append(
                {"row": row, "col": col, "unit": best_name, "score": round(best_score, 3)}
            )
    return found


def scout_board() -> dict:
    """Capture the board region and detect unit names. Writes a debug capture
    so the region can be calibrated when nothing is found."""
    img = capture_board()
    if img is None:
        return {"units": [], "cells": [], "error": "scout extras not installed"}
    mods = _imports()
    if mods:
        cv2, _, _ = mods
        try:
            DEBUG_SHOT.parent.mkdir(parents=True, exist_ok=True)
            cv2.imwrite(str(DEBUG_SHOT), img)
        except Exception:
            pass
    cells = detect_units(img)
    seen: list[str] = []
    for c in cells:
        if c["unit"] not in seen:
            seen.append(c["unit"])
    return {"units": seen, "cells": cells, "debug_shot": str(DEBUG_SHOT)}
