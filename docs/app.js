/* ScoringDiscrepNBA site app — vanilla JS, no build step. */
const TYPE_LABELS = {
  "missed-made-basket": "Missed made basket",
  "free-throw-entry-error": "Free-throw entry error",
  "two-vs-three-point-ruling": "2-pt vs 3-pt ruling",
  "scoreboard-display-error": "Scoreboard display error",
  "official-scorer-book-error": "Official scorer book error",
  "stat-correction-non-scoring": "Stat correction (non-scoring)",
  "stat-correction-denied": "Correction requested, denied",
  "timing-buzzer-dispute": "Timing / buzzer dispute",
  "data-feed-conflict": "Data-feed conflict",
  "unknown": "Unknown (under investigation)"
};
const LAYER_LABELS = {
  "official-record-wrong-then-corrected": "Official record was wrong, then corrected",
  "official-record-wrong-stands": "Official record disputed, stands",
  "official-record-correct-secondary-wrong": "Official record correct; secondary wrong",
  "unresolved": "Unresolved"
};
const OUTCOME_LABELS = {
  "corrected-next-day": "Corrected next day",
  "corrected-in-game": "Corrected in game",
  "corrected-via-replay": "Corrected via replay",
  "stands-protest-denied": "Stands (protest denied)",
  "stands-no-review": "Stands (never reviewed)",
  "stands-ruled-correct": "Stands (ruled correct)",
  "pending": "Pending",
  "unknown": "Unknown"
};
const STATUS_LABELS = {
  "verified": "Verified",
  "verified-partial": "Verified (partial)",
  "under-investigation": "Under investigation",
  "unverified": "UNVERIFIED",
  "disputed": "Disputed",
  "not-a-discrepancy": "Not a discrepancy"
};

let ALL_CASES = [];

function el(id) { return document.getElementById(id); }
function esc(s) {
  return String(s == null ? "" : s).replace(/[&<>"']/g, c => (
    { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}
function statusChip(s) {
  const cls = s === "verified" ? "ok" : s === "verified-partial" ? "info"
    : s === "unverified" ? "bad" : "warn";
  return `<span class="chip ${cls}">${esc(STATUS_LABELS[s] || s)}</span>`;
}
function layerChip(l) {
  const cls = l === "official-record-wrong-then-corrected" ? "warn"
    : l === "official-record-wrong-stands" ? "bad"
    : l === "official-record-correct-secondary-wrong" ? "ok" : "warn";
  return `<span class="chip ${cls}">${esc(LAYER_LABELS[l] || l)}</span>`;
}

async function loadJSON(path) {
  const res = await fetch(path);
  if (!res.ok) throw new Error(`Failed to load ${path}: ${res.status}`);
  return res.json();
}

function renderStats(stats) {
  el("stat-verified").textContent = stats.verified_count;
  el("stat-total").textContent = stats.collection_size;
  el("stat-score-changed").textContent = stats.final_score_changed_ids.length;
  el("stat-onepoint").textContent = stats.one_point_total_change_ids.length;
  el("stat-official-wrong").textContent =
    Math.round(stats.headline.official_record_wrong_share * 100) + "%";
  el("stat-secondary-only").textContent =
    Math.round(stats.headline.secondary_only_share * 100) + "%";
  el("scope-caveat").textContent = stats.scope_caveat;
  el("stats-generated").textContent = `Collection statistics generated ${stats.generated}.`;

  const dist = (counts, mountId) => {
    const mount = el(mountId);
    const total = Object.values(counts).reduce((a, b) => a + b, 0) || 1;
    mount.innerHTML = Object.entries(counts).sort((a, b) => b[1] - a[1]).map(([k, v]) => {
      const label = TYPE_LABELS[k] || LAYER_LABELS[k] || OUTCOME_LABELS[k] || k;
      const pct = Math.round((v / total) * 100);
      return `<div class="dist-row"><div><strong>${esc(label)}</strong> — ${v} case${v === 1 ? "" : "s"} (${pct}%)</div>` +
        `<div class="bar"><span style="width:${pct}%"></span></div></div>`;
    }).join("");
  };
  dist(stats.verified_type_counts, "dist-type");
  dist(stats.verified_layer_counts, "dist-layer");
  dist(stats.verified_outcome_counts, "dist-outcome");

  el("rarity-list").innerHTML = stats.rarity_notes.map(n => `<li>${esc(n)}</li>`).join("");
  el("duration-list").innerHTML = (stats.duration_notes || []).map(n => `<li>${esc(n)}</li>`).join("");
}

function caseCard(c) {
  const teams = [c.away_team, c.home_team].filter(Boolean).join(" @ ") || "Teams TBD (unverified)";
  return `<article class="case-card" data-id="${esc(c.id)}" tabindex="0" role="button" aria-label="${esc(c.title)}">
    <h3>${esc(c.title)}</h3>
    <div class="meta">${esc(c.game_date || "Date unknown")} · ${esc(teams)}${c.season ? " · " + esc(c.season) : ""}</div>
    <div>${statusChip(c.status)}<span class="chip">${esc(TYPE_LABELS[c.classification.type] || c.classification.type)}</span></div>
    <div>${layerChip(c.classification.layer)}</div>
    <div class="score-compare">
      <div class="score-row"><b>Original</b><span>${esc(c.originally_reported.value || "—")}</span></div>
      <div class="score-row final"><b>Final official</b><span>${esc(c.final_official.value || "—")}</span></div>
    </div>
    <div class="meta">${esc(c.sources.length)} source${c.sources.length === 1 ? "" : "s"} · Last reviewed ${esc(c.last_reviewed)}</div>
  </article>`;
}

function applyFilters() {
  const q = el("search").value.trim().toLowerCase();
  const t = el("filter-type").value, l = el("filter-layer").value,
        o = el("filter-outcome").value, s = el("filter-status").value;
  const cards = ALL_CASES.filter(c => {
    if (t && c.classification.type !== t) return false;
    if (l && c.classification.layer !== l) return false;
    if (o && c.classification.outcome !== o) return false;
    if (s && c.status !== s) return false;
    if (q) {
      const hay = [c.title, c.incident_summary, c.away_team, c.home_team,
        c.affected_player, c.game_date, c.id].filter(Boolean).join(" ").toLowerCase();
      if (!hay.includes(q)) return false;
    }
    return true;
  });
  el("case-count").textContent = `${cards.length} of ${ALL_CASES.length} records shown`;
  el("case-grid").innerHTML = cards.map(caseCard).join("") ||
    `<div class="feed-empty">No records match these filters. <a href="#" id="clear-filters">Clear filters</a>.</div>`;
  document.querySelectorAll(".case-card").forEach(card => {
    card.addEventListener("click", () => openDetail(card.dataset.id));
    card.addEventListener("keydown", e => { if (e.key === "Enter") openDetail(card.dataset.id); });
  });
  const clear = el("clear-filters");
  if (clear) clear.addEventListener("click", e => {
    e.preventDefault();
    el("search").value = ""; el("filter-type").value = ""; el("filter-layer").value = "";
    el("filter-outcome").value = ""; el("filter-status").value = "";
    applyFilters();
  });
}

function openDetail(id) {
  const c = ALL_CASES.find(x => x.id === id);
  if (!c) return;
  const teams = [c.away_team, c.home_team].filter(Boolean).join(" @ ") || "Unknown (unverified report)";
  const srcItems = c.sources.map((s, i) =>
    `<li><strong>[${i}] ${esc(s.publisher)}</strong> <span class="chip">${esc(s.tier)}</span><br>` +
    `<a href="${esc(s.url)}" target="_blank" rel="noopener">${esc(s.url)}</a><br>` +
    `<em>Confirms:</em> ${esc(s.confirms)} <span class="meta">(accessed ${esc(s.accessed || "n/a")})</span></li>`
  ).join("");
  const timeline = c.timeline.map(t =>
    `<div><span class="tdate">${esc(t.date)}</span> — ${esc(t.event)}` +
    (t.source_index != null ? ` <span class="meta">[${t.source_index}]</span>` : "") + `</div>`
  ).join("");
  const disputed = (c.disputed_points || []).map(d =>
    `<li><strong>${esc(d.claim)}</strong><ul>${d.positions.map(p => `<li>${esc(p)}</li>`).join("")}</ul></li>`
  ).join("");
  el("detail-body").innerHTML = `
    <button class="close-btn" id="detail-close">Close ✕</button>
    <h2>${esc(c.title)}</h2>
    <div class="meta">${esc(c.game_date || "Date unknown")} · ${esc(teams)}${c.season ? " · " + esc(c.season) : ""}${c.venue ? " · " + esc(c.venue) : ""}</div>
    <div style="margin:8px 0">${statusChip(c.status)}
      <span class="chip">${esc(TYPE_LABELS[c.classification.type])}</span>
      <span class="chip info">${esc(OUTCOME_LABELS[c.classification.outcome])}</span></div>
    <div>${layerChip(c.classification.layer)}</div>
    <h4>What happened</h4><p>${esc(c.incident_summary)}</p>
    <h4>Original vs corrected vs final</h4>
    <div class="score-compare">
      <div class="score-row"><b>Originally reported</b><span>${esc(c.originally_reported.value || "—")}${c.originally_reported.total != null ? ` (total ${c.originally_reported.total})` : ""}<br><span class="meta">${esc(c.originally_reported.basis)}</span></span></div>
      <div class="score-row"><b>Correction</b><span>${esc(c.corrected_value.value || "— none —")}${c.corrected_value.total != null ? ` (total ${c.corrected_value.total})` : ""}<br><span class="meta">${esc(c.corrected_value.basis)}</span></span></div>
      <div class="score-row final"><b>Final official</b><span>${esc(c.final_official.value || "—")}${c.final_official.total != null ? ` (total ${c.final_official.total})` : ""}<br><span class="meta">${esc(c.final_official.basis)}</span></span></div>
    </div>
    <h4>Key facts</h4>
    <ul>
      <li><strong>Clock:</strong> ${esc(c.period_clock || "Unknown — not inferred")}</li>
      <li><strong>Scoring play:</strong> ${esc(c.scoring_play || "Unknown")}</li>
      <li><strong>Score before:</strong> ${esc(c.score_before || "Unknown")}</li>
      <li><strong>Affected:</strong> ${esc(c.affected_player || "—")} (${esc(c.affected_team || "—")})</li>
      <li><strong>Was the NBA's official record wrong?</strong> ${esc(c.official_record_was_wrong)}</li>
      <li><strong>Cause (${esc(c.cause.determination)}):</strong> ${esc(c.cause.detail)}</li>
      ${c.duration_note ? `<li><strong>Duration:</strong> ${esc(c.duration_note)}</li>` : ""}
      ${(c.sources_disagreed || []).length ? `<li><strong>Sources that disagreed:</strong><ul>${c.sources_disagreed.map(s => `<li>${esc(s)}</li>`).join("")}</ul></li>` : ""}
      ${c.betting_notes ? `<li><strong>Betting notes:</strong> ${esc(c.betting_notes)}</li>` : ""}
    </ul>
    <h4>Timeline</h4><div class="timeline">${timeline}</div>
    ${disputed ? `<h4>Disputed points (flagged, not resolved)</h4><ul>${disputed}</ul>` : ""}
    <h4>Open questions</h4>
    <ul>${(c.open_questions || []).map(q => `<li>${esc(q)}</li>`).join("") || "<li>None — fully verified.</li>"}</ul>
    ${(c.reproduce_steps || []).length ? `<h4>Reproduce this research</h4><ol>${c.reproduce_steps.map(s => `<li>${esc(s)}</li>`).join("")}</ol>` : ""}
    <h4>Sources (${c.sources.length}) — verify every claim yourself</h4>
    <ul class="src-list">${srcItems}</ul>
    <p class="meta">Record <code class="inline">${esc(c.id)}</code> · verification: ${esc(c.verification_level)} · last reviewed ${esc(c.last_reviewed)}</p>`;
  el("detail").classList.add("open");
  document.body.style.overflow = "hidden";
  el("detail-close").addEventListener("click", closeDetail);
}
function closeDetail() {
  el("detail").classList.remove("open");
  document.body.style.overflow = "";
}

function renderFeed(inv) {
  const mount = el("monitor-feed");
  const recs = (inv.records || []).filter(r => !["resolved", "escalated-to-case"].includes(r.status));
  el("feed-count").textContent = recs.length
    ? `${recs.length} open investigation${recs.length === 1 ? "" : "s"}`
    : "No open investigations — last checks agreed across sources.";
  if (!recs.length) {
    mount.innerHTML = `<div class="feed-empty">The monitor's latest runs found no cross-source disagreements. ` +
      `Resolved and escalated records remain in <code class="inline">data/investigations.json</code> in the repository. ` +
      `Note: the originating 213-vs-214 report is tracked as an <strong>unverified</strong> record above, not here, until its game is identified.</div>`;
    return;
  }
  mount.innerHTML = `<table class="clean"><tr><th>Detected (UTC)</th><th>Game</th><th>Check</th><th>Status</th><th>Evidence</th></tr>` +
    recs.map(r => `<tr><td>${esc(r.created_utc)}</td><td>${esc(r.game_date)} ${esc(r.game_key)}</td>` +
      `<td>${esc(r.check)}</td><td>${esc(r.status)}</td><td>${esc((r.evidence || {}).detail || "")}</td></tr>`).join("") + `</table>`;
}

function renderMethodology(src) {
  el("tier-table").innerHTML = `<table class="clean"><tr><th>Tier</th><th>Label</th><th>Use</th></tr>` +
    src.tiers.map(t => `<tr><td><code class="inline">${esc(t.tier)}</code></td><td>${esc(t.label)}<br><span class="meta">${esc(t.examples.join("; "))}</span></td><td>${esc(t.use)}</td></tr>`).join("") + `</table>`;
  el("ref-list").innerHTML = src.authoritative_references.map(r =>
    `<li><a href="${esc(r.url)}" target="_blank" rel="noopener">${esc(r.url)}</a> — ${esc(r.note)}</li>`).join("");
}

async function init() {
  try {
    const [cases, stats, inv, src] = await Promise.all([
      loadJSON("data/cases.json"), loadJSON("data/stats.json"),
      loadJSON("data/investigations.json"), loadJSON("data/sources.json")
    ]);
    ALL_CASES = cases.cases || [];
    renderStats(stats);
    ["search", "filter-type", "filter-layer", "filter-outcome", "filter-status"]
      .forEach(id => el(id).addEventListener("input", applyFilters));
    applyFilters();
    renderFeed(inv);
    renderMethodology(src);
    el("detail").addEventListener("click", e => { if (e.target.id === "detail") closeDetail(); });
    document.addEventListener("keydown", e => { if (e.key === "Escape") closeDetail(); });
  } catch (err) {
    document.querySelector("main").innerHTML =
      `<div class="wrap"><div class="alert unverified"><strong>Data failed to load.</strong>` +
      `${esc(err.message)}. If you opened this file directly, serve the <code class="inline">docs/</code> folder ` +
      `over HTTP (e.g. <code class="inline">python3 -m http.server</code>) or visit the deployed GitHub Pages URL.</div></div>`;
  }
}
document.addEventListener("DOMContentLoaded", init);
