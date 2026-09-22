// Overlay window: renders advice pushed by the background page.

const el = (id) => document.getElementById(id);

function abbrev(name) {
  const s = String(name || "").trim();
  return s.length > 7 ? s.slice(0, 7) : s;
}

// Mini 4x7 board for the top comp: frontline on the upper rows,
// backline on the lower rows, remaining core units fill the middle.
function renderBoard(comp) {
  const grid = el("board");
  grid.innerHTML = "";
  el("board-title").hidden = !comp;
  if (!comp) return;

  const pos = comp.positioning || {};
  const carries = new Set(
    Object.keys(comp.carry_items || {}).map((s) => s.toLowerCase())
  );
  const front = [...(pos.frontline || [])];
  const back = [...(pos.backline || [])];
  const lined = new Set([...front, ...back].map((s) => s.toLowerCase()));
  const flex = (comp.units || []).filter((u) => !lined.has(u.toLowerCase()));

  const rows = [front.slice(0, 7), [], [], back.slice(0, 7)];
  for (const u of [...front.slice(7), ...flex, ...back.slice(7)]) {
    const row = rows[1].length <= rows[2].length ? rows[1] : rows[2];
    if (row.length < 7) row.push(u);
  }

  for (const units of rows) {
    const rowEl = document.createElement("div");
    rowEl.className = "brow";
    for (let i = 0; i < 7; i++) {
      const cell = document.createElement("span");
      const name = units[i];
      if (name) {
        cell.className =
          "cell" + (carries.has(String(name).toLowerCase()) ? " carry" : "");
        cell.textContent = abbrev(name);
        cell.title = name;
      } else {
        cell.className = "cell empty";
      }
      rowEl.appendChild(cell);
    }
    grid.appendChild(rowEl);
  }
}

function renderAdvice(advice) {
  el("empty").hidden = true;
  const compsEl = el("comps");
  compsEl.innerHTML = "";
  for (const c of advice.comps || []) {
    const row = document.createElement("div");
    row.className = "comp";
    const badge = c.agreement ? "AGREE" : "SPLIT";
    const badgeClass = c.agreement ? "yes" : "no";
    const contested =
      c.contested > 0 ? `<span class="agree contested">x${c.contested} contested</span>` : "";
    row.innerHTML =
      `<span class="name"></span>` +
      contested +
      `<span class="agree ${badgeClass}">${badge}</span>` +
      `<span class="prob">${Math.round(c.probability * 100)}%</span>`;
    row.querySelector(".name").textContent = c.name;
    const sub = document.createElement("div");
    sub.className = "sub";
    const bits = [];
    if (c.entry && typeof c.entry.score === "number")
      bits.push(`entry ${Math.round(c.entry.score * 100)}%`);
    if (c.roll && c.roll.hit_now > 0) {
      const best =
        c.roll.best_level && c.roll.best_level !== (advice.level || 0)
          ? ` → best L${c.roll.best_level} ${Math.round(c.roll.hit_best * 100)}%`
          : "";
      bits.push(`roll ${Math.round(c.roll.hit_now * 100)}%${best}`);
    }
    if (c.stats && c.stats.avg_place) bits.push(`avg ${c.stats.avg_place}`);
    const piv = (c.pivot_to || [])[0];
    if (piv && (c.contested > 0 || (c.entry && c.entry.score < 0.5)))
      bits.push(`pivot → ${piv.name} (${piv.shared} shared)`);
    if (c.positioning && (c.positioning.frontline || []).length)
      bits.push(
        `front: ${c.positioning.frontline.join(", ")}` +
          (c.positioning.backline && c.positioning.backline.length
            ? ` · back: ${c.positioning.backline.join(", ")}`
            : "")
      );
    if ((c.units || []).length) bits.push(`roster: ${c.units.join(", ")}`);
    const items = Object.entries(c.carry_items || {});
    if (items.length)
      bits.push(`items: ${items.map(([u, i]) => `${u}: ${i.join("/")}`).join("; ")}`);
    const tanks = Object.entries(c.tank_items || {});
    if (tanks.length)
      bits.push(`tank: ${tanks.map(([u, i]) => `${u}: ${i.join("/")}`).join("; ")}`);
    const holders = Object.entries(c.item_holders || {});
    if (holders.length)
      bits.push(
        `holders: ${holders.map(([u, h]) => `${h.join("/")} → ${u}`).join("; ")}`
      );
    if (c.item_plan) bits.push(`item plan: ${c.item_plan}`);
    const missing = (c.missing_units || [])[0];
    if (missing)
      bits.push(
        `missing ${missing.unit}` +
          (missing.sub && missing.sub.length ? ` → ${missing.sub.join("/")}` : "")
      );
    if (c.endgame) bits.push(`endgame: ${c.endgame}`);
    sub.textContent = bits.join(" · ");
    row.appendChild(sub);
    compsEl.appendChild(row);
  }

  renderBoard((advice.comps || [])[0]);

  const shopEl = el("shop");
  shopEl.innerHTML = "";
  el("shop-title").hidden = !(advice.shop || []).length;
  for (const m of advice.shop || []) {
    const chip = document.createElement("span");
    chip.className = `chip mark-${m.reason}`;
    chip.textContent = `${m.unit} (${m.reason})`;
    shopEl.appendChild(chip);
  }

  const nextEl = el("next-ops");
  nextEl.innerHTML = "";
  el("next-title").hidden = !(advice.next_opponents || []).length;
  if ((advice.next_opponents || []).length) {
    const bits = (advice.next_opponents || []).map((o) => {
      const t = o.shared > 0 ? ` — shares ${o.shared}` : "";
      return o.name + t;
    });
    nextEl.textContent =
      (advice.last_fought ? `last: ${advice.last_fought} · ` : "") +
      `next? ${bits.join(", ")}`;
  }

  const prepEl = el("prep");
  if (typeof advice.prep === "number" && advice.prep > 0.5) {
    prepEl.textContent = `Prep adjustment signal: ${Math.round(advice.prep * 100)}%`;
    prepEl.style.color = "#ffbe5a";
  } else {
    prepEl.textContent = "";
  }

  const slamEl = el("slam");
  if (typeof advice.slam === "number") {
    const pct = Math.round(advice.slam * 100);
    slamEl.textContent = pct >= 50 ? `Slam items now: ${pct}%` : `Hold items for BiS: ${100 - pct}%`;
    slamEl.style.color = pct >= 50 ? "#7ddba3" : "#9fb3d8";
  } else {
    slamEl.textContent = "";
  }

  const carEl = el("carousel");
  if (advice.carousel && advice.carousel.item) {
    const r = advice.carousel.rank ? ` (#${advice.carousel.rank} prio)` : "";
    carEl.textContent = `Carousel → take ${advice.carousel.item}${r}`;
    carEl.style.color = "#a8c7ff";
  } else {
    carEl.textContent = "";
  }

  const pfEl = el("postfight");
  if (typeof advice.post_fight === "number") {
    const pct = Math.round(advice.post_fight * 100);
    pfEl.textContent =
      pct >= 50
        ? `React to last fight: ${pct}% — adjust plan`
        : `Stay the course after last fight: ${100 - pct}%`;
    pfEl.style.color = pct >= 50 ? "#ffbe5a" : "#9fb3d8";
  } else {
    pfEl.textContent = "";
  }

  const econEl = el("econ");
  econEl.innerHTML = "";
  el("econ-title").hidden = !advice.econ;
  if (advice.econ) {
    for (const [action, p] of Object.entries(advice.econ.distribution)) {
      const chip = document.createElement("span");
      chip.className = "chip";
      chip.textContent = `${action} ${Math.round(p * 100)}%`;
      if (action === advice.econ.action) chip.style.fontWeight = "700";
      econEl.appendChild(chip);
    }
  }

  const augEl = el("aug");
  augEl.innerHTML = "";
  el("aug-title").hidden = !advice.augment;
  if (advice.augment) {
    const top = document.createElement("div");
    top.innerHTML = `<b></b> <span class="prob"></span>`;
    top.querySelector("b").textContent = advice.augment.pick;
    top.querySelector(".prob").textContent =
      `${Math.round((advice.augment.distribution[advice.augment.pick] || 0) * 100)}%` +
      (advice.augment.agreement ? "" : " · engines disagree");
    augEl.appendChild(top);
  }

  const pivotEl = el("pivot");
  if (typeof advice.pivot === "number" && advice.pivot > 0.5) {
    pivotEl.textContent = `Pivot signal: ${Math.round(advice.pivot * 100)}%`;
    pivotEl.style.color = "#ffbe5a";
  } else {
    pivotEl.textContent = "";
  }
}

overwolf.windows.onMessageReceived.addListener((message) => {
  if (message.id === "advice") renderAdvice(message.content);
  else if (message.id === "service") {
    const status = el("status");
    status.textContent = message.content.online ? "service online" : "service offline";
    status.className = message.content.online ? "on" : "off";
  }
});

const SERVICE_URL = "http://127.0.0.1:8371";

// Manual scout: the user inspected a rival's board in-game and types what
// they saw — GEP never exposes opponent boards, so this is the only way
// rival unit data reaches the service.
el("scout-save").addEventListener("click", () => {
  const name = el("s-name").value.trim();
  const msg = el("scout-msg");
  if (!name) {
    msg.textContent = "rival name required";
    return;
  }
  const units = el("s-units").value
    .split(/[,\n]/)
    .map((s) => s.trim())
    .filter(Boolean);
  const send = (id) =>
    overwolf.windows.sendMessage(id, "scout", { name, units }, (res) => {
      msg.textContent =
        res && res.success !== false ? `scouted ${name}` : "send failed";
    });
  overwolf.windows.obtainDeclaredWindow("background", (res) => {
    if (res && res.success && res.window) send(res.window.id);
    else msg.textContent = "background not reachable";
  });
});

el("builder-toggle").addEventListener("click", () => {
  const form = el("builder");
  form.hidden = !form.hidden;
});

el("builder-save").addEventListener("click", async () => {
  const name = el("b-name").value.trim();
  const msg = el("builder-msg");
  if (!name) {
    msg.textContent = "name required";
    return;
  }
  const parseList = (v) =>
    v
      .split(/[,\n]/)
      .map((s) => s.trim())
      .filter(Boolean);
  const body = {
    name,
    units: parseList(el("b-units").value),
    traits: parseList(el("b-traits").value),
    strategy: el("b-strategy").value.trim(),
    positioning: {
      frontline: parseList(el("b-front").value),
      backline: parseList(el("b-back").value),
    },
  };
  for (const line of el("b-items").value.split("\n")) {
    const m = line.match(/^\s*([^:>]+)\s*:\s*(.+)$/);
    if (m) body.carry_items = body.carry_items || {};
    if (m) body.carry_items[m[1].trim()] = parseList(m[2]);
  }
  try {
    const resp = await fetch(`${SERVICE_URL}/comps`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    if (!resp.ok) throw new Error(await resp.text());
    msg.textContent = `saved "${name}"`;
    el("b-name").value = "";
  } catch (err) {
    msg.textContent = `save failed: ${String(err).slice(0, 80)}`;
  }
});
