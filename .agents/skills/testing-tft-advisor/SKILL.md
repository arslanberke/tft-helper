---
name: testing-tft-advisor
description: How to run and end-to-end test the TFT Comp Advisor FastAPI service with the deterministic MockEngine, including its scoring quirks and seeded comp data.
---

# Testing the TFT Comp Advisor service

## Run it (no model downloads needed)

```bash
cd <repo root>
TFT_ENGINE=mock .venv/bin/python -m tft_advisor.app   # uvicorn on 127.0.0.1:8371
```

The blueprint already covers venv + `.[dev]` install; `service/` is the package dir
(`tft_advisor` importable anywhere once `pip install -e .` ran).

## Key facts for crafting test states

- Seeded comps live in `service/data/comps.json` and use generic unit names
  ("4-cost carry", "trait unit 1", ...). To make `contested >= 1`, give an
  opponent ≥2 units whose names match a comp's `units` list.
- **MockEngine quirk**: it substring-matches `Unit.describe()` strings
  (e.g. `"2* 4-cost carry [bis 1, bis 2]"`) against comp criteria text, so
  units with `star > 1` or items NEVER match comp core units. Use star-1,
  itemless unit names on board/bench when you want a comp to score.
- Deterministic values: `pivot` noul = 0.3; augment/comp choices fuse to a
  score-proportional distribution (score 1.0 base +1 per matched owned name).
- Econ heuristic (engines.py `_score`): stage_num≥4 & level<8 → "level" (needs
  gold≥20); gold≥50 & not behind → "hold"; else "roll". Scores are 3.0 vs 1.0
  → e.g. stage "4-2"/level 7/gold 45 → {level: 0.6, roll: 0.2, hold: 0.2}.
- `entry.score` is weighted over comp.conditions (openers .45, items .30,
  augments .25); haystack includes board+bench+shop+items+augments — a unit
  sitting in `shop` counts as a match.
- **Fragile inputs**: non-numeric `stage` (e.g. "x-y") crashes with ValueError
  → HTTP 500 (questions.py int() call + engines.py `_score`). `top_n=0`
  returns 1 comp (append-then-break). Both are known sharp edges.
- The Overwolf app (`overwolf-app/`) can't run outside Overwolf+TFT;
  `node --check overwolf-app/windows/*.js` is the sanity check. overlay.js
  consumes: c.entry.score, c.roll.{hit_now,best_level,hit_best},
  c.stats.avg_place, c.pivot_to[0].{name,shared}, advice.level,
  advice.econ.{action,distribution}, advice.augment.{pick,distribution,
  agreement}, advice.pivot.
