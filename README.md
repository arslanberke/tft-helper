# TFT Comp Advisor

Live comp / econ / augment advice for Teamfight Tactics. An Overwolf app streams
your game state to a local decision service; **System-1 decision models**
(TypeSafe **Jev** hosted + open-source **Laya** locally) each answer the same
typed questions and a consensus layer fuses their probabilities — so every
recommendation carries both a probability and an agreement signal.

```
┌──────────────┐  GEP events   ┌──────────────────┐  POST /advice  ┌─────────────────────┐
│ Overwolf app │ ────────────► │ background.js     │ ─────────────► │ Python service      │
│ (overlay)    │ ◄──────────── │ GameState tracker │ ◄───────────── │ comps + engines     │
└──────────────┘ sendMessage   └──────────────────┘                │  ├─ LayaEngine      │
                                                                   │  └─ JevEngine       │
                                                                   │  └─ EnsembleEngine  │
                                                                   └─────────────────────┘
```

## Why System-1 models

Jev/Laya don't generate text: you pass a `state` plus typed questions
(`Choice` / `Score` / `Noul`) and get calibrated probabilities back in tens of
milliseconds — the exact shape of "which comp / roll or level / which augment /
should I pivot". No parsing, no hallucinated JSON.

## Components

- **`service/`** — Python (FastAPI) decision service.
  - `engines.py` — `LayaEngine` (local, free, `pip install laya`), `JevEngine`
    (`pip install typesafe-sdk` + `TYPESAFE_API_KEY`), `EnsembleEngine`
    (fuses both: weighted mean of per-option distributions, `agreement` flag).
  - `questions.py` — translates game state + comp library into typed questions.
  - `comps.py` — comp library with per-site ratings and a consensus tier.
  - `sources/` — meta-site adapters (tactics.tools, MetaTFT, Mobalytics,
    TFT Academy) normalizing tier lists into one schema, merged by
    `sources/merge.py`.
- **`overwolf-app/`** — the in-game overlay (see its README).
- **`service/scripts/`** — `fetch_set_data.py` (CommunityDragon champions /
  traits / augments + icons), `build_comp_library.py` (regenerates
  `data/comps.json` from configured sources).

## Setup

```bash
pip install -e ".[laya,jev]"   # jev extra optional, needs TYPESAFE_API_KEY
export TYPESAFE_API_KEY=...    # only for Jev; without it Laya runs alone
export KEV_URL=http://localhost:8009  # optional: local Kev server (github.com/jaredpalmer/kev)
tft-advisor                    # serves http://127.0.0.1:8371
```

Then sideload `overwolf-app/` in Overwolf dev mode (`overwolf-app/README.md`).

## Comp data

`service/data/comps.json` ships seeded example comps. For the live meta:

1. Put each site's tierlist URL (or a local export path) in
   `service/data/sources.json`.
2. `python service/scripts/build_comp_library.py` → merged `comps.json` where
   every comp keeps its per-site tier; `consensus_tier()` blends them.
3. `python service/scripts/fetch_set_data.py --icons` for current-set
   champion/trait/augment names + icons.

## Patch day

When a TFT patch/set lands, once the meta sites have updated:

```bash
python -m service.scripts.refresh_meta          # icons + comp library
python -m service.scripts.refresh_meta --set 14 # pin a set
```

Then: restart `tft-advisor`, and if the board looks shifted recalibrate
`TFT_BOARD_REGION` using the debug capture at `service/data/last_scout.png`.
New GEP key spellings show up as "unmapped info" logs in the background
console.

## Tests

```bash
pip install -e ".[dev]"
pytest tests/
```

## Notes / limitations

- The meta sites have no stable free API (MetaTFT's is paid); adapters are
  best-effort parsers behind a common interface — a broken site is skipped,
  never fatal.
- GEP field spellings drift between patches; unmapped keys are logged to the
  background page console for easy remapping (`background.js` → `applyKV`).
- Passive overlay only: reads GEP events, never touches game memory — same
  class of tool as MetaTFT/Blitz on Overwolf.
