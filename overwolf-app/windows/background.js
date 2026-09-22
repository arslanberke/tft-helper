// TFT Comp Advisor — background page.
// Listens to Overwolf GEP info-updates/events, keeps a normalized GameState,
// asks the local decision service for advice, forwards it to the overlay window.
//
// GEP payload key spellings vary between game patches; unknown keys are logged
// so the mapping can be tuned without touching the pipeline.

const REQUIRED_FEATURES = [
  "gep_internal",
  "game_info",
  "live_client_data",
  "me",
  "match_info",
  "roster",
  "store",
  "board",
  "bench",
  "carousel",
  "augments",
];

const SERVICE_URL = "http://127.0.0.1:8371";
const OVERLAY_WINDOW = "overlay";
const POLL_MS = 2500;

let gameState = freshState();
let inGame = false;
let overlayWindowId = null;
let pollTimer = null;
let lastAdviceJson = "";
let serviceOnline = null;

function freshState() {
  return {
    stage: "",
    round_type: "",
    level: 0,
    gold: 0,
    hp: 100,
    streak: 0,
    board: [],
    bench: [],
    shop: [],
    items: [],
    offered_augments: [],
    picked_augments: [],
    opponents: [],
  };
}

function parseMaybeJson(value) {
  if (typeof value !== "string") return value;
  try {
    return JSON.parse(value);
  } catch {
    return value;
  }
}

function normOpponent(raw) {
  if (!raw || typeof raw !== "object") return { name: String(raw ?? ""), units: [] };
  const units = (raw.units || raw.board || raw.pieces || []).map(normUnit);
  return {
    name: raw.name || raw.summoner || raw.summoner_name || raw.tag_line || "",
    units,
  };
}

function normUnit(raw) {
  if (!raw || typeof raw !== "object") return { name: String(raw ?? "") };
  const items = (raw.items || []).map((i) =>
    typeof i === "string" ? i : i.name || i.apiName || ""
  );
  return {
    name: raw.name || raw.champion || raw.character || raw.apiName || "",
    star: raw.stars || raw.star || raw.level || 1,
    items: items.filter(Boolean),
  };
}

function applyKV(category, key, rawValue) {
  const value = parseMaybeJson(rawValue);
  switch (category) {
    case "me":
      if (key === "health" || key === "hp") gameState.hp = Number(value) || gameState.hp;
      else if (key === "level") gameState.level = Number(value) || gameState.level;
      else if (key === "gold") gameState.gold = Number(value) || gameState.gold;
      else if (key === "items" || key === "inventory")
        gameState.items = asList(value).map((i) =>
          typeof i === "object" ? i.name || i.apiName || "" : String(i)
        );
      break;
    case "match_info":
      if (key === "round_type") gameState.round_type = String(value);
      else if (key === "streak" || key === "win_streak")
        gameState.streak = Number(value) || 0;
      else if (key === "stage" || key === "round") gameState.stage = String(value);
      else if (key === "opponents")
        gameState.opponents = asList(value).map(normOpponent);
      break;
    case "board":
      if (key === "board_pieces" || key === "board" || key === "units")
        gameState.board = asList(value).map(normUnit);
      break;
    case "bench":
      if (key === "bench_pieces" || key === "bench")
        gameState.bench = asList(value).map(normUnit);
      break;
    case "store":
      if (key === "shop_pieces" || key === "shop" || key === "store")
        gameState.shop = asList(value).map((u) => (typeof u === "object" ? normUnit(u).name : String(u)));
      break;
    case "items":
      if (key === "items" || key === "inventory" || key === "bench_items")
        gameState.items = asList(value).map((i) =>
          typeof i === "object" ? i.name || i.apiName || "" : String(i)
        );
      break;
    case "augments":
      if (key === "picked" || key === "augments" || key === "player_augments")
        gameState.picked_augments = asList(value).map(String);
      else if (key === "item_select" || key === "offered" || key === "choices")
        gameState.offered_augments = asList(value).map((a) =>
          typeof a === "object" ? a.name || a.augment || String(a) : String(a)
        );
      break;
    case "roster":
      if (key === "roster_players" || key === "players")
        gameState.opponents = asList(value)
          .map(normOpponent)
          .filter((o) => o.name || o.units.length);
      break;
    default:
      if (category !== "gep_internal" && category !== "game_info")
        console.debug("[advisor] unmapped info", category, key);
  }
}

function asList(value) {
  return Array.isArray(value) ? value : value ? [value] : [];
}

function handleInfoUpdate(update) {
  // Shape B: single {category, key, value}
  if (update.key !== undefined) applyKV(update.category, update.key, update.value);
  // Shape A: {"info": {"category": {"key": "value", ...}}}
  const info = update.info || {};
  for (const [category, entries] of Object.entries(info)) {
    if (entries && typeof entries === "object" && !Array.isArray(entries)) {
      for (const [key, value] of Object.entries(entries)) applyKV(category, key, value);
    }
  }
}

async function requestAdvice() {
  try {
    const resp = await fetch(`${SERVICE_URL}/advice`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ state: gameState }),
    });
    if (!resp.ok) throw new Error(`advice ${resp.status}`);
    const advice = await resp.json();
    setServiceStatus(true);
    const serialized = JSON.stringify(advice);
    if (serialized !== lastAdviceJson) {
      lastAdviceJson = serialized;
      sendToOverlay("advice", advice);
    }
  } catch (err) {
    console.warn("[advisor] service unreachable", err);
    setServiceStatus(false);
  }
}

function setServiceStatus(online) {
  if (online === serviceOnline) return;
  serviceOnline = online;
  sendToOverlay("service", { online });
}

function sendToOverlay(messageId, content) {
  const send = (id) =>
    overwolf.windows.sendMessage(id, messageId, content, (res) => {
      if (!res || res.success === false) console.debug("[advisor] sendMessage failed", messageId);
    });
  if (overlayWindowId) send(overlayWindowId);
  else
    overwolf.windows.obtainDeclaredWindow(OVERLAY_WINDOW, (res) => {
      if (res && res.success && res.window) {
        overlayWindowId = res.window.id;
        send(overlayWindowId);
      }
    });
}

function onMatchStart() {
  inGame = true;
  gameState = freshState();
  overwolf.windows.obtainDeclaredWindow(OVERLAY_WINDOW, (res) => {
    if (res && res.success && res.window) {
      overlayWindowId = res.window.id;
      overwolf.windows.restore(overlayWindowId, () => {});
    }
  });
  if (!pollTimer) pollTimer = setInterval(requestAdvice, POLL_MS);
  requestAdvice();
}

function onMatchEnd() {
  inGame = false;
  if (pollTimer) {
    clearInterval(pollTimer);
    pollTimer = null;
  }
  if (overlayWindowId) overwolf.windows.minimize(overlayWindowId, () => {});
  gameState = freshState();
  lastAdviceJson = "";
}

function init() {
  overwolf.games.events.setRequiredFeatures(REQUIRED_FEATURES, (res) => {
    const ok = res && (res.status === "success" || res.success);
    console.log(`[advisor] setRequiredFeatures: ${ok ? "ok" : "failed"}`);
  });

  overwolf.games.events.onInfoUpdates2.addListener(handleInfoUpdate);
  overwolf.games.events.onNewEvents.addListener(({ events }) => {
    for (const e of events || []) {
      if (e.name === "match_start") onMatchStart();
      else if (e.name === "match_end") onMatchEnd();
      else if (e.name === "round_start" || e.name === "battle_start") requestAdvice();
    }
  });
  overwolf.games.events.onError.addListener((e) => console.warn("[advisor] gep error", e));

  overwolf.games.getRunningGameInfo((res) => {
    if (res && res.isRunning && res.id && Math.floor(res.id / 10) === 5426) onMatchStart();
  });
}

init();
