# Overwolf app — TFT Comp Advisor

A two-window Overwolf app:

- `windows/background.*` — hidden background page. Subscribes to TFT GEP
  features (`board`, `bench`, `store`, `augments`, `roster`, `match_info`,
  `me`, `live_client_data`), keeps a normalized `GameState`, polls the local
  decision service (`http://127.0.0.1:8371/advice`) and pushes results to the
  overlay via `overwolf.windows.sendMessage`.
- `windows/overlay.*` — transparent in-game overlay showing the top comp picks
  with probabilities, econ recommendation, augment pick, and an AGREE/SPLIT
  badge that reflects whether the decision engines agreed.

## Dev install

1. Start the decision service first:
   `pip install -e ".[laya]"` then `tft-advisor` (or `python -m tft_advisor.app`).
2. In Overwolf: Settings → About → Development options → Load unpacked
   extension → select this `overwolf-app/` directory.
3. Launch TFT — the overlay appears on match start.

## Notes

- TFT and LoL share the client, so `game_targeting` uses the LoL game id
  `5426`; TFT-specific GEP id is `21570`.
- GEP payload key spellings change between patches. The background page logs
  every unmapped `category/key` pair to devtools console — check there first
  if a state field stays empty, then extend `applyKV` in `background.js`.
- Store submission additionally needs icon files in `meta` (see Overwolf
  manifest docs); sideloading for dev does not.
