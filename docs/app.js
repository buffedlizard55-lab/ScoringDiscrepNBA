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
let LAST_FOCUSED_CARD = null;

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
    card.addEventListener("click", () => openDetail(card.dataset.id, card));
    card.addEventListener("keydown", e => {
      if (e.key === "Enter" || e.key === " " || e.key === "Spacebar") {
        e.preventDefault();
        openDetail(card.dataset.id, card);
      }
    });
  });
  const clear = el("clear-filters");
  if (clear) clear.addEventListener("click", e => {
    e.preventDefault();
    el("search").value = ""; el("filter-type").value = ""; el("filter-layer").value = "";
    el("filter-outcome").value = ""; el("filter-status").value = "";
    applyFilters();
  });
}

function openDetail(id, trigger = null) {
  const c = ALL_CASES.find(x => x.id === id);
  if (!c) return;
  LAST_FOCUSED_CARD = trigger || document.activeElement;
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
    <button type="button" class="close-btn" id="detail-close">Close case details</button>
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
      <li><strong>Score after play:</strong> ${esc(c.score_after_play || "Unknown or not independently captured")}</li>
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
  const closeButton = el("detail-close");
  closeButton.addEventListener("click", closeDetail);
  closeButton.focus();
}
function closeDetail() {
  el("detail").classList.remove("open");
  document.body.style.overflow = "";
  if (LAST_FOCUSED_CARD && typeof LAST_FOCUSED_CARD.focus === "function") LAST_FOCUSED_CARD.focus();
}

function renderFeed(inv) {
  const mount = el("monitor-feed");
  const recs = (inv.records || []).filter(r => !["resolved", "escalated-to-case"].includes(r.status));
  el("feed-count").textContent = recs.length
    ? `${recs.length} open investigation${recs.length === 1 ? "" : "s"}`
    : "No open investigation records are stored.";
  if (!recs.length) {
    mount.innerHTML = `<div class="feed-empty">No open investigation record is currently stored. ` +
      `This does not by itself prove that the latest feeds agreed or were reachable; check the latest poll and source health above. ` +
      `Resolved and escalated records remain in <code class="inline">data/investigations.json</code>. ` +
      `The unidentified 213-vs-214 report and Kevin Porter Jr. lead remain separately labeled <strong>unverified</strong> in the case collection.</div>`;
    return;
  }
  const rows = recs.map(r => {
    const observations = r.observations || [];
    const history = r.history || [];
    const events = [
      ...observations.map(o => {
        const evidence = o.evidence || {};
        const detail = evidence.detail || JSON.stringify(evidence.check_observation || evidence.source_snapshot || evidence.nba_cdn_and_pbp || evidence);
        return { at: o.at || "", html: `<strong>${esc(o.at || "Time unavailable")}</strong> · source observation (${esc(o.severity || "severity unknown")}) — ${esc(detail)}` };
      }),
      ...(r.resolution_observations || []).map(o => ({
        at: o.at || "",
        html: `<strong>${esc(o.at || "Time unavailable")}</strong> · later source values agreed: <code class="inline">${esc(JSON.stringify(o.evidence || {}))}</code>`
      })),
      ...history.map(item => ({
        at: item.at || "",
        html: `<strong>${esc(item.at || "Time unavailable")}</strong> · status event — ${esc(item.note || "Status event")}`
      })),
    ].sort((a, b) => a.at.localeCompare(b.at));
    const timeline = events.map(item => `<li>${item.html}</li>`).join("");
    const details = events.length
      ? `<details><summary>${observations.length} source observation${observations.length === 1 ? "" : "s"} · ${history.length} status event${history.length === 1 ? "" : "s"} · ${esc(r.repeat_count || 1)} poll${(r.repeat_count || 1) === 1 ? "" : "s"}</summary><ol>${timeline}</ol></details>`
      : "";
    return `<tr><td>${esc(r.created_utc || "Time unknown")}</td><td>${esc(r.game_date || "Date unknown")} ${esc(r.game_key || "Game unknown")}</td>` +
      `<td>${esc(r.check || "Check unknown")}${r.check_scope ? ` · ${esc(r.check_scope)}` : ""}</td><td>${esc(r.status || "Status unknown")}</td>` +
      `<td>${esc((r.evidence || {}).detail || "")} ${details}</td></tr>`;
  }).join("");
  mount.innerHTML = `<table class="clean"><thead><tr><th>Detected (UTC)</th><th>Game</th><th>Check / scope</th><th>Status</th><th>Evidence &amp; history</th></tr></thead><tbody>${rows}</tbody></table>`;
}

function safeSourceLink(url, label) {
  if (typeof url !== "string" || !url.startsWith("https://")) return "";
  return `<a href="${esc(url)}" target="_blank" rel="noopener">${esc(label)}</a>`;
}

function formatObservedScore(block) {
  if (!block || typeof block !== "object") return "Unavailable — not assumed to be zero";
  const away = block.away == null ? "Unknown" : String(block.away);
  const home = block.home == null ? "Unknown" : String(block.home);
  const total = block.total == null ? "unavailable" : String(block.total);
  return `${away}–${home} (combined ${total})`;
}

function renderCurrentMonitor(snapshot) {
  const mount = el("monitor-current");
  if (!snapshot || snapshot.status === "not-run") {
    mount.innerHTML = `<p><strong>No scheduled monitor snapshot has been published yet.</strong> This is not a statement that either feed is currently reachable.</p>`;
    return;
  }
  const sourceStatus = Object.entries(snapshot.sourceStatus || {}).map(([name, value]) =>
    `<li><strong>${esc(name)}:</strong> ${value === true ? "reachable" : esc(value || "not checked")}</li>`
  ).join("");
  const warnings = (snapshot.feedWarnings || []).map(item => `<li>${esc(item)}</li>`).join("");
  const rows = (snapshot.games || []).map(row => {
    const espn = row.espn || {}, nba = row.nba_cdn || {};
    const findings = (row.findings || []).map(item => `<li><strong>${esc(item.check || "check")}</strong>: ${esc(item.detail || "")}</li>`).join("");
    const comparisonLabels = {
      equal: "Feeds agree on displayed score",
      different: "Feeds differ — unverified source divergence",
      "no-nba-match": "No NBA matchup match; not treated as a score difference",
      "nba-scoreboard-unavailable": "NBA scoreboard unavailable; no comparison",
      "nba-boxscore-unavailable": "NBA box score unavailable; no comparison",
      "incomplete-score-data": "One or more score values missing; no comparison",
    };
    return `<tr><td>${esc(row.game_date || "Date unknown")} · ${esc(row.away_team || "Away team unknown")} @ ${esc(row.home_team || "Home team unknown")}<br><span class="meta">${esc(row.status || "Status unknown")} · observed ${esc(row.observed_at_utc || "time unknown")}</span></td>` +
      `<td>${esc(formatObservedScore(espn.score))}<br>${safeSourceLink(espn.url, "ESPN source")}</td>` +
      `<td>${esc(formatObservedScore(nba.score))}<br>${safeSourceLink(nba.boxscore_url || nba.scoreboard_url, "NBA CDN source")}` +
      `${nba.play_by_play_url ? `<br>${safeSourceLink(nba.play_by_play_url, "NBA play-by-play")}` : ""}</td>` +
      `<td>${esc(comparisonLabels[row.comparison] || row.comparison || "Not compared")}</td>` +
      `<td>${findings ? `<ul>${findings}</ul>` : "No finding recorded for this row."}</td></tr>`;
  }).join("");
  const currentRows = rows
    ? `<div class="table-scroll"><table class="clean"><thead><tr><th>Game / observed time (UTC)</th><th>ESPN observation</th><th>NBA CDN observation</th><th>Comparison</th><th>Checks</th></tr></thead><tbody>${rows}</tbody></table></div>`
    : `<p>No game rows were returned for this poll date. This may be an off-day or a source/coverage limitation.</p>`;
  mount.innerHTML = `<p><strong>Latest committed poll:</strong> ${esc(snapshot.generatedAt || "time unavailable")} · status <strong>${esc(snapshot.status || "unknown")}</strong> · requested date ${esc(snapshot.requestedDate || "unknown")}. ` +
    `Last poll with both score feeds available: ${esc(snapshot.lastSuccessfulAt || "none recorded")}.</p>` +
    `<p>Games compared: ${esc(snapshot.counts && snapshot.counts.gamesCompared != null ? snapshot.counts.gamesCompared : 0)} · ` +
    `findings: ${esc(snapshot.counts && snapshot.counts.findings != null ? snapshot.counts.findings : 0)} · ` +
    `feed warnings: ${esc(snapshot.counts && snapshot.counts.feedWarnings != null ? snapshot.counts.feedWarnings : 0)}.</p>` +
    `<h3>Source health</h3><ul>${sourceStatus || "<li>No source-health data recorded.</li>"}</ul>` +
    `${warnings ? `<h3>Feed warnings (not scoring findings)</h3><ul>${warnings}</ul>` : ""}` +
    `${currentRows}<ul>${(snapshot.notes || []).map(note => `<li>${esc(note)}</li>`).join("")}</ul>`;
}

function renderMethodology(src) {
  el("tier-table").innerHTML = `<table class="clean"><tr><th>Tier</th><th>Label</th><th>Use</th></tr>` +
    src.tiers.map(t => `<tr><td><code class="inline">${esc(t.tier)}</code></td><td>${esc(t.label)}<br><span class="meta">${esc(t.examples.join("; "))}</span></td><td>${esc(t.use)}</td></tr>`).join("") + `</table>`;
  el("ref-list").innerHTML = src.authoritative_references.map(r =>
    `<li><a href="${esc(r.url)}" target="_blank" rel="noopener">${esc(r.url)}</a> — ${esc(r.note)}</li>`).join("");
}

async function init() {
  try {
    const [cases, stats, inv, src, monitorSnapshot] = await Promise.all([
      loadJSON("data/cases.json"), loadJSON("data/stats.json"),
      loadJSON("data/investigations.json"), loadJSON("data/sources.json"),
      loadJSON("data/monitor/current.json")
    ]);
    ALL_CASES = cases.cases || [];
    renderStats(stats);
    ["search", "filter-type", "filter-layer", "filter-outcome", "filter-status"]
      .forEach(id => el(id).addEventListener("input", applyFilters));
    applyFilters();
    renderFeed(inv);
    renderCurrentMonitor(monitorSnapshot);
    renderMethodology(src);
    el("detail").addEventListener("click", e => { if (e.target.id === "detail") closeDetail(); });
    document.addEventListener("keydown", e => {
      const dialog = el("detail");
      if (!dialog.classList.contains("open")) return;
      if (e.key === "Escape") {
        closeDetail();
        return;
      }
      if (e.key !== "Tab") return;
      const focusable = [...dialog.querySelectorAll('a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])')]
        .filter(node => node.offsetParent !== null);
      if (!focusable.length) {
        e.preventDefault();
        return;
      }
      const first = focusable[0], last = focusable[focusable.length - 1];
      if (e.shiftKey && document.activeElement === first) {
        e.preventDefault();
        last.focus();
      } else if (!e.shiftKey && document.activeElement === last) {
        e.preventDefault();
        first.focus();
      }
    });
  } catch (err) {
    document.querySelector("main").innerHTML =
      `<div class="wrap"><div class="alert unverified"><strong>Data failed to load.</strong>` +
      `${esc(err.message)}. If you opened this file directly, serve the <code class="inline">docs/</code> folder ` +
      `over HTTP (e.g. <code class="inline">python3 -m http.server</code>) or visit the deployed GitHub Pages URL.</div></div>`;
  }
}
document.addEventListener("DOMContentLoaded", init);
