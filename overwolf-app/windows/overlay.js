// Overlay window: renders advice pushed by the background page.

const el = (id) => document.getElementById(id);

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
    sub.textContent = bits.join(" · ");
    row.appendChild(sub);
    compsEl.appendChild(row);
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
