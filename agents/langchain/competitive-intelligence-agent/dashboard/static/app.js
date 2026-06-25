/* CI Dashboard — client logic.
 *
 * Fetches from FastAPI backend, renders phosphor-styled ledger, supports
 * filters and a verification-queue tab. Read-only for now; approvals/HITL
 * to be added later.
 */

// palette — mirror of facts_viewer.py
const COLORS = {
  status:   { verified: "#3fb950", needs_review: "#d29922", stale: "#d29922", conflicting: "#f85149", rejected: "#f85149" },
  conf:     { high: "#3fb950", medium: "#d29922", low: "#f85149" },
  risk:     { low: "#3fb950", medium: "#d29922", high: "#f85149" },
  posture:  { direct_fact: "#7ee787", vendor_claim: "#d29922", third_party_report: "#79c0ff", inference: "#8b949b" },
};
const CAT_COLORS = ["#7ee787", "#79c0ff", "#d29922", "#f85149", "#a371f7", "#56d4be", "#e3b341", "#ff7b72", "#d2a8ff"];
const ESC_MAP = { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" };

function esc(s) {
  if (s === null || s === undefined) return "";
  return String(s).replace(/[&<>"']/g, c => ESC_MAP[c]);
}

function badge(text, color) {
  return `<span style="color:${color}">${esc(text)}</span>`;
}

function rowClass(fact) {
  if (fact.risk_level === "high" || ["rejected", "conflicting"].includes(fact.status)) return "bad";
  if (fact.status === "needs_review" || fact.risk_level === "medium") return "warn";
  return "ok";
}

// ----------------------------------------------------------------- state

const state = {
  companies: [],
  currentUuid: null,
  currentData: null,
  queueMd: null,
  activeTab: "ledger",
  filters: {
    q: "",
    cats: new Set(),
    confs: new Set(),
    statuses: new Set(),
    risks: new Set(),
    srcs: new Set(),
    postures: new Set(),
    copySafeOnly: false,
    attentionOnly: false,
  },
};

// ----------------------------------------------------------------- loaders

async function fetchJSON(url) {
  const r = await fetch(url);
  if (!r.ok) throw new Error(`${r.status} ${r.statusText} @ ${url}`);
  return r.json();
}

async function loadCompanies() {
  state.companies = await fetchJSON("/api/companies");
  document.getElementById("caption").textContent =
    `${state.companies.length} companies · output/companies/`;
  if (state.companies.length === 0) {
    document.getElementById("ledger-body").innerHTML =
      `<div class="state-msg error">// no companies found under output/companies //</div>`;
    return;
  }
  renderCompanyList();
  selectCompany(state.companies[0].uuid);
}

async function selectCompany(uuid) {
  state.currentUuid = uuid;
  state.queueMd = null;
  renderCompanyList();
  try {
    state.currentData = await fetchJSON(`/api/companies/${uuid}`);
  } catch (e) {
    document.getElementById("ledger-body").innerHTML =
      `<div class="state-msg error">// failed to load: ${esc(e.message)} //</div>`;
    return;
  }
  buildCategoryChips();
  buildSourceChips();
  buildPostureChips();
  document.getElementById("filters").style.display = "block";
  document.getElementById("refresh-btn").style.display = "block";
  renderAll();
}

async function refreshCurrent() {
  if (!state.currentUuid) return;
  const body = document.getElementById("ledger-body");
  body.innerHTML = `<div class="state-msg blink">refreshing</div>`;
  await selectCompany(state.currentUuid);
}

async function loadQueue() {
  if (state.queueMd !== null) return;
  if (!state.currentUuid) return;
  try {
    const r = await fetch(`/api/companies/${state.currentUuid}/verification-queue`);
    state.queueMd = r.ok ? await r.text() : `// ${r.status} ${r.statusText} //`;
  } catch (e) {
    state.queueMd = `// failed to load verification queue: ${e.message} //`;
  }
}

// ----------------------------------------------------------------- sidebar

function renderCompanyList() {
  const list = document.getElementById("company-list");
  list.innerHTML = state.companies.map(c => `
    <label data-uuid="${esc(c.uuid)}" class="${state.currentUuid === c.uuid ? "active" : ""}">
      ${esc(c.name)}
      <span class="count">${c.fact_count}</span>
    </label>`).join("");
  list.querySelectorAll("label").forEach(el => {
    el.addEventListener("click", () => selectCompany(el.dataset.uuid));
  });
}

function buildChips(elId, values) {
  const el = document.getElementById(elId);
  el.innerHTML = values.map(v =>
    `<span class="chip" data-v="${esc(v)}">${esc(v.toUpperCase())}</span>`).join("");
  el.querySelectorAll(".chip").forEach(chip => {
    chip.addEventListener("click", () => {
      const v = chip.dataset.v;
      const set = elId === "cats"     ? state.filters.cats
                : elId === "srcs"     ? state.filters.srcs
                : elId === "postures" ? state.filters.postures
                : null;
      if (!set) return;
      set.has(v) ? set.delete(v) : set.add(v);
      chip.classList.toggle("on");
      renderAll();
    });
  });
}

function buildCategoryChips() {
  const cats = [];
  for (const f of state.currentData.facts) {
    if (f.category && !cats.includes(f.category)) cats.push(f.category);
  }
  state.filters.cats = new Set(cats);   // default: all on
  buildChips("cats", cats);
  document.querySelectorAll("#cats .chip").forEach(c => c.classList.add("on"));
}

function buildSourceChips() {
  const srcs = [];
  for (const f of state.currentData.facts) {
    if (f.source_type && !srcs.includes(f.source_type)) srcs.push(f.source_type);
  }
  srcs.sort();
  state.filters.srcs = new Set();   // default: all off (acts as "no filter")
  buildChips("srcs", srcs);
}

function buildPostureChips() {
  const postures = [];
  for (const f of state.currentData.facts) {
    if (f.evidence_posture && !postures.includes(f.evidence_posture)) postures.push(f.evidence_posture);
  }
  postures.sort();
  state.filters.postures = new Set();
  buildChips("postures", postures);
}

function wireStaticChips(elId, setKey) {
  const el = document.getElementById(elId);
  el.querySelectorAll(".chip").forEach(chip => {
    chip.addEventListener("click", () => {
      const v = chip.dataset.v;
      const s = state.filters[setKey];
      s.has(v) ? s.delete(v) : s.add(v);
      chip.classList.toggle("on");
      renderAll();
    });
  });
}

// ---------------------------------------------------------------- filtering

function matches(fact) {
  const f = state.filters;
  if (f.copySafeOnly && !fact.copy_safe) return false;
  if (f.attentionOnly) {
    if (!(fact.status === "needs_review" || fact.risk_level === "high" || !fact.copy_safe)) return false;
  }
  if (f.cats.size && !f.cats.has(fact.category)) return false;
  if (f.confs.size && !f.confs.has(fact.confidence)) return false;
  if (f.statuses.size && !f.statuses.has(fact.status)) return false;
  if (f.risks.size && !f.risks.has(fact.risk_level)) return false;
  if (f.srcs.size && !f.srcs.has(fact.source_type)) return false;
  if (f.postures.size && !f.postures.has(fact.evidence_posture)) return false;
  if (f.q) {
    const hay = [fact.id, fact.claim, fact.approved_wording, fact.source_title,
                 fact.source_url, fact.notes, fact.scope]
                .map(x => String(x || "").toLowerCase()).join(" ");
    if (!hay.includes(f.q.toLowerCase())) return false;
  }
  return true;
}

// ----------------------------------------------------------------- render

function kpiStrip(facts) {
  const total = facts.length;
  const verified = facts.filter(f => f.status === "verified").length;
  const highConf = facts.filter(f => f.confidence === "high").length;
  const needsReview = facts.filter(f => f.status === "needs_review").length;
  const highRisk = facts.filter(f => f.risk_level === "high").length;
  const copySafe = facts.filter(f => f.copy_safe).length;
  const cells = [
    ["VERIFIED", `${verified}/${total}`, "ok"],
    ["HIGH CONF", String(highConf), highConf ? "ok" : ""],
    ["NEEDS REVIEW", String(needsReview), needsReview ? "warn" : ""],
    ["HIGH RISK", String(highRisk), highRisk ? "bad" : ""],
    ["COPY-SAFE", String(copySafe), copySafe === total ? "ok" : "warn"],
  ];
  return `<div class="kpi-grid">${cells.map(([lbl, val, cls]) =>
    `<div class="kpi ${cls}"><div class="label">${lbl}</div><div class="val">${val}</div></div>`
  ).join("")}</div>`;
}

function catBar(facts) {
  const counts = {};
  for (const f of facts) {
    const c = f.category || "?";
    counts[c] = (counts[c] || 0) + 1;
  }
  const entries = Object.entries(counts).sort((a, b) => a[0].localeCompare(b[0]));
  if (entries.length === 0) return "";
  const total = entries.reduce((s, [, n]) => s + n, 0);
  const segs = entries.map(([cat, n], i) => {
    const color = CAT_COLORS[i % CAT_COLORS.length];
    const pct = (n / total * 100).toFixed(2);
    return `<div class="seg" style="width:${pct}%;background:${color}" title="${esc(cat)}: ${n}"></div>`;
  });
  const legend = entries.map(([cat, n], i) => {
    const color = CAT_COLORS[i % CAT_COLORS.length];
    return `<span><span class="sq" style="background:${color}"></span>${esc(cat)} · ${n}</span>`;
  });
  return `<div class="catbar">${segs.join("")}</div><div class="cat-legend">${legend.join("")}</div>`;
}

function fmtObserved(v) {
  if (v === null || v === undefined || v === "") return "";
  if (typeof v === "string") return v;
  try { return yamlish(v); } catch { return JSON.stringify(v, null, 2); }
}

// naive YAML-ish formatter for nested observed_value dicts/lists
function yamlish(obj, indent = 0) {
  const pad = "  ".repeat(indent);
  if (Array.isArray(obj)) {
    return obj.map(v => `${pad}- ${typeof v === "object" && v !== null ? "\n" + yamlish(v, indent + 1) : esc(v)}`).join("\n");
  }
  if (typeof obj === "object" && obj !== null) {
    return Object.entries(obj).map(([k, v]) => {
      if (typeof v === "object" && v !== null) return `${pad}${k}:\n${yamlish(v, indent + 1)}`;
      return `${pad}${k}: ${esc(v)}`;
    }).join("\n");
  }
  return `${pad}${esc(obj)}`;
}

function renderFactRow(fact) {
  const fid = esc(fact.id || "?");
  const claim = esc(String(fact.claim || "").replace(/\n/g, " "));
  const conf = esc(fact.confidence || "");
  const status = esc(fact.status || "");
  const risk = esc(fact.risk_level || "");
  const cs = fact.copy_safe ? "✓" : "✗";
  const csColor = fact.copy_safe ? "#3fb950" : "#f85149";

  const summary = `
    <div class="id">${fid}</div>
    <div class="claim">${claim}</div>
    <div class="conf">${badge(conf.slice(0, 3).toUpperCase(), COLORS.conf[conf] || "#8b949b")}</div>
    <div class="status">${badge(status, COLORS.status[status] || "#8b949b")}</div>
    <div class="risk">${badge(risk, COLORS.risk[risk] || "#8b949b")}</div>
    <div class="cs">${badge(cs, csColor)}</div>`;

  const srcUrl = esc(fact.source_url || "");
  const srcTitle = esc(fact.source_title || "");
  const srcType = esc(fact.source_type || "");
  const posture = String(fact.evidence_posture || "");
  const fit = esc(fact.source_fit || "");

  const body = `
    <div class="ci-body">
      <div class="field full">
        <div class="k">approved wording ${badge(fact.copy_safe ? "copy-safe" : "do-not-copy", csColor)}</div>
        <div class="wording">${esc(fact.approved_wording || "—")}</div>
      </div>
      <div class="field full">
        <div class="k">raw claim</div>
        <div class="rawclaim">${esc(fact.claim || "—")}</div>
      </div>
      <div class="field">
        <div class="k">source</div>
        <div class="v srcrow">
          <span><a href="${srcUrl}" target="_blank" rel="noreferrer">${srcTitle || srcUrl}</a></span>
        </div>
        <div class="v">${badge(srcType, "#8b949b")} · ${esc(fact.date_checked || "")}</div>
      </div>
      <div class="field">
        <div class="k">evidence posture</div>
        <div class="v">${badge(posture, COLORS.posture[posture] || "#8b949b")} · fit=${fit}</div>
        <div class="k" style="margin-top:6px">scope</div>
        <div class="v">${esc(fact.scope || "—")}</div>
      </div>
      <div class="field">
        <div class="k">observed value</div>
        <pre>${esc(fmtObserved(fact.observed_value))}</pre>
      </div>
      <div class="field">
        <div class="k">provenance</div>
        <div class="v">conf=${badge(String(fact.confidence || ""), COLORS.conf[fact.confidence] || "#8b949b")} · status=${badge(String(fact.status || ""), COLORS.status[fact.status] || "#8b949b")} · risk=${badge(String(fact.risk_level || ""), COLORS.risk[fact.risk_level] || "#8b949b")}</div>
        <div class="v">freshness=${esc(fact.freshness_days || "")}d · company_id=${esc(String(fact.company_id || "").slice(0, 8))}</div>
      </div>
      ${fact.notes ? `<div class="field full"><div class="k">notes</div><div class="nav-note">${esc(fact.notes)}</div></div>` : ""}
    </div>`;

  return `<details class="ci-row ${rowClass(fact)}"><summary>${summary}</summary>${body}</details>`;
}

function renderLedger(facts, total) {
  if (facts.length === 0) {
    return `<div class="emptyrow">// no facts match current filters //</div>`;
  }
  const rows = facts.map(renderFactRow).join("");
  return `<div class="ledger"><div class="count">// showing ${facts.length} of ${total} facts //</div>${rows}</div>`;
}

function renderDossier() {
  const c = state.currentData;
  if (!c) return;
  const copySafeOnly = state.filters.copySafeOnly;
  const attentionOnly = state.filters.attentionOnly;
  const clsMode = copySafeOnly ? "COPY_SAFE_ONLY" : attentionOnly ? "ATTENTION_QUEUE" : "FULL_LEDGER";
  const filtered = c.facts.filter(matches);
  document.getElementById("dossier").innerHTML = `
    <div class="dossier-head">
      <div class="kicker">Dossier · 0x${esc(c.uuid.slice(0, 8).toUpperCase())}</div>
      <div class="title">${esc(c.name)} <span style="color:var(--dimmer);font-weight:400;font-size:0.8rem">· ${c.facts.length} facts · ${esc(c.date_researched || "no date")}</span></div>
      <div class="meta">CLASSIFIED ⟶ ${clsMode} · ${filtered.length} pass filters</div>
    </div>`;
}

function renderAll() {
  if (!state.currentData) return;
  if (state.activeTab !== "ledger") {
    renderQueue();
    return;
  }
  const c = state.currentData;
  const filtered = c.facts.filter(matches);
  renderDossier();
  document.getElementById("kpi").innerHTML = kpiStrip(filtered);
  document.getElementById("catbar").innerHTML = catBar(filtered);
  document.getElementById("ledger-body").innerHTML = renderLedger(filtered, c.facts.length);
}

async function renderQueue() {
  const c = state.currentData;
  if (!c) return;
  renderDossier();
  document.getElementById("kpi").innerHTML = "";
  document.getElementById("catbar").innerHTML = "";
  const body = document.getElementById("ledger-body");
  body.innerHTML = `<div class="state-msg blink">loading verification queue</div>`;
  await loadQueue();
  body.innerHTML = `<pre class="queue-pre">${esc(state.queueMd)}</pre>`;
}

// ----------------------------------------------------------------- tabs

function wireTabs() {
  document.querySelectorAll(".tab-strip .tab").forEach(tab => {
    tab.addEventListener("click", async () => {
      document.querySelectorAll(".tab-strip .tab").forEach(t => t.classList.remove("active"));
      tab.classList.add("active");
      state.activeTab = tab.dataset.tab;
      if (state.activeTab === "queue") {
        await renderQueue();
      } else {
        renderAll();
      }
    });
  });
}

// ----------------------------------------------------------------- init

function init() {
  document.getElementById("search").addEventListener("input", e => {
    state.filters.q = e.target.value;
    renderAll();
  });
  document.getElementById("copy-safe-only").addEventListener("change", e => {
    state.filters.copySafeOnly = e.target.checked;
    renderAll();
  });
  document.getElementById("attention-only").addEventListener("change", e => {
    state.filters.attentionOnly = e.target.checked;
    renderAll();
  });
  document.getElementById("refresh-btn").addEventListener("click", refreshCurrent);
  wireStaticChips("confs", "confs");
  wireStaticChips("statuses", "statuses");
  wireStaticChips("risks", "risks");
  wireTabs();
  loadCompanies();
}

document.addEventListener("DOMContentLoaded", init);
