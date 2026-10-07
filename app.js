"use strict";

const DATA_PATHS = {
  cases: "./data/cases.json",
  leads: "./data/leads.json",
  sources: "./data/sources.json",
  current: "./data/monitor/current.json",
  candidates: "./data/monitor/candidates.json"
};

const cache = { cases: [], leads: [], sources: [], current: {}, candidates: [] };
const sourceById = new Map();
const el = (selector) => document.querySelector(selector);

function node(tag, className, text) {
  const value = document.createElement(tag);
  if (className) value.className = className;
  if (text !== undefined && text !== null) value.textContent = String(text);
  return value;
}

function sourceLink(sourceId, label) {
  const source = sourceById.get(sourceId);
  if (!source || !/^https?:\/\//i.test(source.url || "") || /[{}]/.test(source.url)) return null;
  const link = node("a", "", label || source.organization);
  link.href = source.url;
  link.target = "_blank";
  link.rel = "noopener noreferrer";
  link.setAttribute("aria-label", `Open ${source.organization} source in a new tab`);
  return link;
}

function appendCitations(parent, ids) {
  const wrap = node("div", "citation-links");
  [...new Set(ids || [])].forEach((id) => {
    const link = sourceLink(id, sourceById.get(id)?.organization || id);
    if (link) wrap.append(link);
  });
  if (wrap.childElementCount) parent.append(wrap);
}

function formatScore(score, order) {
  if (!score || score.away === null || score.home === null) return "Not reported";
  return `${score.away}–${score.home}`;
}

function scoreLabel(score, order) {
  const codes = order || [];
  const labels = [];
  if (codes[0]) labels.push(`${codes[0]} ${score?.away ?? "—"}`);
  if (codes[1]) labels.push(`${codes[1]} ${score?.home ?? "—"}`);
  return labels.join(" · ");
}

function makeScoreState(label, value, order, final) {
  const wrap = node("div", `score-state${final ? " final" : ""}`);
  const textWrap = node("div");
  textWrap.append(node("span", "score-state-label", label));
  textWrap.append(node("span", "score-number", formatScore(value, order)));
  wrap.append(textWrap);
  const codes = node("span", "source-flag", order.join(" / "));
  wrap.append(codes);
  return wrap;
}

function appendEvidenceColumn(parent, title, items, ordered = false) {
  const section = node("section", "detail-column");
  section.append(node("h4", "", title));
  const list = node(ordered ? "ol" : "ul");
  for (const item of items || []) {
    const li = node("li", "evidence-item");
    if (typeof item === "string") {
      li.textContent = item;
    } else {
      const p = node("p", "", item.claim || item.description || item.event || "");
      li.append(p);
      if (item.observedAt) li.append(node("p", "inline-note", `Source conflict observed: ${item.observedAt} · ${item.observedAtPrecision || "precision not supplied"}.`));
      if (item.sourceObservations?.length) {
        const observations = node("ul");
        item.sourceObservations.forEach((observation) => {
          const observationItem = node("li", "", `${sourceById.get(observation.sourceId)?.organization || observation.sourceId} · ${observation.field || "field"}: ${(observation.values || []).join(" vs ")}`);
          appendCitations(observationItem, [observation.sourceId]);
          observations.append(observationItem);
        });
        li.append(observations);
      }
      appendCitations(li, item.sourceIds);
    }
    list.append(li);
  }
  section.append(list);
  parent.append(section);
}

function appendContext(parent, record) {
  const context = record.playContext;
  const section = node("section", "detail-column");
  section.append(node("h4", "", "Play and score context"));
  const p = node("p", "", `${context.period ? `Q${context.period}` : "Period not known"} · ${context.clock || "clock not known"}. ${context.event || ""}`);
  section.append(p);
  const scoreGrid = node("div", "score-context");
  const before = node("div", "context-cell");
  before.append(node("span", "context-label", "Score before · reported"));
  before.append(node("span", "context-score", formatContextScore(context.scoreBefore, record.scores.displayOrder)));
  appendCitations(before, context.scoreBefore?.sourceIds);
  scoreGrid.append(before);
  const after = node("div", "context-cell");
  after.append(node("span", "context-label", "Immediately after"));
  after.append(node("span", "context-score", formatContextScore(context.scoreImmediatelyAfter, record.scores.displayOrder)));
  if (context.scoreImmediatelyAfter?.isDerived) after.append(node("span", "context-derived", "Derived from cited score + rule; not a captured feed row"));
  appendCitations(after, context.scoreImmediatelyAfter?.sourceIds);
  scoreGrid.append(after);
  section.append(scoreGrid);
  parent.append(section);
}

function formatContextScore(value, order) {
  if (!value || !order?.length) return "Not established";
  const away = value[order[0]];
  const home = value[order[1]];
  return `${order[0]} ${away ?? "—"} · ${order[1]} ${home ?? "—"}`;
}

function renderCase(record) {
  const article = node("article", "case-card");
  article.setAttribute("aria-labelledby", `title-${record.id}`);

  const header = node("header", "case-card-header");
  const heading = node("div");
  heading.append(node("p", "case-label", `${record.game.season} · NBA GAME ${record.game.nbaGameId}`));
  const title = node("h3", "case-title", `${record.game.awayTeam.name} at ${record.game.homeTeam.name}`);
  title.id = `title-${record.id}`;
  heading.append(title);
  heading.append(node("p", "case-date", new Date(`${record.game.date}T12:00:00Z`).toLocaleDateString(undefined, { year: "numeric", month: "long", day: "numeric", timeZone: "UTC" })));
  header.append(heading);
  const tags = node("div", "case-tags");
  tags.append(node("span", "case-tag", "Confirmed · NBA record corrected"));
  tags.append(node("span", "case-tag neutral", record.cause?.status === "league_acknowledged_recording_error" ? "League-acknowledged" : "Cause attribution qualified"));
  header.append(tags);
  article.append(header);

  const score = node("div", "score-comparison");
  score.append(makeScoreState("ORIGINAL REPORTED FINAL", record.scores.originalReported, record.scores.displayOrder, false));
  score.append(node("span", "score-arrow", "→"));
  score.append(makeScoreState("CORRECTED · FINAL", record.scores.finalOfficial, record.scores.displayOrder, true));
  article.append(score);

  article.append(node("p", "case-summary", record.cause?.summary || "Correction details are under review."));
  const facts = node("div", "case-facts");
  const player = node("span"); player.append(node("strong", "", "Affected: ")); player.append(document.createTextNode(`${record.affected.player} · ${record.affected.team}`)); facts.append(player);
  const play = node("span"); play.append(node("strong", "", "Play: ")); play.append(document.createTextNode(`Q${record.playContext.period} · ${record.playContext.clock}`)); facts.append(play);
  const change = node("span"); change.append(node("strong", "", "NBA record: ")); change.append(document.createTextNode(`${record.scores.originalReported.away}–${record.scores.originalReported.home} → ${record.scores.finalOfficial.away}–${record.scores.finalOfficial.home}`)); facts.append(change);
  article.append(facts);

  const details = node("details", "case-details");
  const summary = node("summary", "", "Open evidence, timeline, and source conflicts");
  details.append(summary);
  const content = node("div", "case-detail-content");
  const left = node("div", "detail-stack");
  appendContext(left, record);
  const playerLine = record.affected.correctedLine || {};
  const statSection = node("section", "detail-column");
  statSection.append(node("h4", "", "Affected player line"));
  statSection.append(node("p", "", record.affected.originalProviderLine?.points !== undefined && record.affected.originalProviderLine.points !== null
    ? `Original secondary-provider observation: ${record.affected.originalProviderLine.points} points (${record.affected.originalProviderLine.freeThrowsMade}/${record.affected.originalProviderLine.freeThrowsAttempted} FT). Corrected line: ${playerLine.points ?? "not reported"} points (${playerLine.freeThrowsMade ?? "?"}/${playerLine.freeThrowsAttempted ?? "?"} FT).`
    : `Original player-point line: not independently preserved. Corrected line: ${playerLine.points ?? "not reported"} points (${playerLine.freeThrowsMade ?? "?"}/${playerLine.freeThrowsAttempted ?? "?"} FT).`));
  statSection.append(node("p", "inline-note", record.affected.originalProviderLine?.qualification || playerLine.qualification || "Player-line provenance is limited."));
  appendCitations(statSection, [...(record.affected.originalProviderLine?.sourceIds || []), ...(playerLine.sourceIds || [])]);
  left.append(statSection);
  const causeSection = node("section", "detail-column");
  causeSection.append(node("h4", "", "Cause and attribution"));
  causeSection.append(node("p", "inline-note inline-warning", `${record.cause.summary} ${record.cause.individualOrProcessCause || ""}`));
  appendCitations(causeSection, record.cause.sourceIds);
  left.append(causeSection);
  content.append(left);

  const right = node("div", "detail-stack");
  appendEvidenceColumn(right, "Claim-by-claim evidence", record.evidence);
  const timeline = (record.timeline || []).map((event) => ({ claim: `${event.at} · ${event.event}`, sourceIds: event.sourceIds }));
  appendEvidenceColumn(right, "Timeline · precision retained", timeline, true);
  appendEvidenceColumn(right, "Provider/source conflicts", record.sourceDisagreements);
  appendEvidenceColumn(right, "What this record cannot establish", record.limitations);
  content.append(right);
  details.append(content);
  article.append(details);
  return article;
}

function searchableText(record) {
  return [record.game?.date, record.game?.season, record.game?.awayTeam?.name, record.game?.homeTeam?.name,
    record.affected?.player, record.affected?.team, record.cause?.summary, record.cause?.individualOrProcessCause,
    ...(record.sourceIds || []).map((id) => sourceById.get(id)?.organization || id),
    ...(record.evidence || []).map((entry) => entry.claim)].join(" ").toLowerCase();
}

function renderRecords() {
  const list = el("#case-list");
  const leadSection = el("#lead-section");
  const leadList = el("#lead-list");
  const term = el("#record-search").value.trim().toLowerCase();
  const state = el("#evidence-filter").value;
  const team = el("#team-filter").value;
  list.replaceChildren();
  leadList.replaceChildren();

  const casesVisible = state !== "unverified";
  const filteredCases = casesVisible ? cache.cases.filter((record) => {
    const teamMatch = team === "all" || record.game.awayTeam.code === team || record.game.homeTeam.code === team;
    return teamMatch && (!term || searchableText(record).includes(term));
  }) : [];
  filteredCases.forEach((record) => list.append(renderCase(record)));

  const filteredLeads = state !== "confirmed" ? cache.leads.filter((lead) => {
    if (team !== "all") return false;
    const text = `${lead.leadAsReceived} ${lead.verification} ${lead.reportedPlayer || ""} ${lead.reportedGameDate || ""} ${lead.values?.reportedByOneSource ?? ""} ${lead.values?.reportedByAnotherSource ?? ""} ${(lead.sourceIds || []).map((id) => sourceById.get(id)?.organization || id).join(" ")}`.toLowerCase();
    return !term || text.includes(term);
  }) : [];
  filteredLeads.forEach((lead) => leadList.append(renderLead(lead)));
  leadSection.hidden = filteredLeads.length === 0;

  const message = filteredCases.length ? `${filteredCases.length} confirmed record${filteredCases.length === 1 ? "" : "s"} shown` : (state === "unverified" ? "No confirmed records in this filter; see the separately labelled lead below." : "No confirmed records match these filters.");
  el("#results-count").textContent = message;
  if (!filteredCases.length) list.append(node("p", "empty-state", state === "unverified" ? "Unverified leads are shown separately below and are never mixed into confirmed-case statistics." : "Try a different team or search term."));
}

function renderLead(lead) {
  const article = node("article", "lead-card");
  const copy = node("div");
  copy.append(node("p", "", lead.leadAsReceived));
  copy.append(node("p", "", lead.verification));
  const values = lead.values?.reportedByOneSource !== undefined && lead.values?.reportedByAnotherSource !== undefined
    ? node("span", "lead-values", `${lead.values.reportedByOneSource} ↔ ${lead.values.reportedByAnotherSource}`)
    : null;
  article.append(copy);
  if (values) article.append(values);
  (lead.sourceIds || []).forEach((id) => {
    const link = sourceLink(id, `Source lead: ${sourceById.get(id)?.organization || id}`);
    if (link) copy.append(link);
  });
  return article;
}

function renderMetrics() {
  const confirmed = cache.cases.filter((record) => record.researchStatus === "confirmed");
  const patternCount = confirmed.filter((record) => record.correctionType === "made_free_throw_recorded_missed").length;
  el("#metric-confirmed").textContent = String(confirmed.length);
  el("#metric-pattern").textContent = `${patternCount}/${confirmed.length}`;
  el("#metric-denominator").textContent = "Unknown";
  el("#metric-duration").textContent = "Unknown";
}

function renderTeamFilter() {
  const select = el("#team-filter");
  const selected = select.value;
  select.replaceChildren();
  select.append(new Option("All teams", "all"));
  const teams = new Map();
  cache.cases.forEach((item) => {
    teams.set(item.game.awayTeam.code, item.game.awayTeam.name);
    teams.set(item.game.homeTeam.code, item.game.homeTeam.name);
  });
  [...teams.entries()].sort((a, b) => a[1].localeCompare(b[1])).forEach(([code, name]) => select.append(new Option(name, code)));
  if ([...select.options].some((option) => option.value === selected)) select.value = selected;
}

function renderMonitor() {
  const monitor = cache.current || {};
  const status = monitor.status || "not_run";
  const badge = el("#monitor-state-badge");
  badge.className = "status-badge";
  if (status === "ok") { badge.classList.add("status-good"); badge.textContent = "Snapshot published"; }
  else if (status === "partial") { badge.classList.add("status-warn"); badge.textContent = "Partial source coverage"; }
  else if (status === "error") { badge.classList.add("status-error"); badge.textContent = "Feed check failed"; }
  else { badge.classList.add("status-idle"); badge.textContent = "Not polled yet"; }

  const headline = el("#monitor-headline");
  const summary = el("#monitor-summary");
  if (status === "not_run") {
    headline.textContent = "The first scheduled run is still pending";
    summary.textContent = "No current score values are presented as if they were checked. The deployed workflow creates the first snapshot.";
  } else if (status === "ok") {
    headline.textContent = "Latest poll completed";
    summary.textContent = `${monitor.games?.length || 0} NBA game comparison${monitor.games?.length === 1 ? "" : "s"} published. A score mismatch is a review flag, not a verdict.`;
  } else if (status === "partial") {
    headline.textContent = "Only part of the comparison is available";
    summary.textContent = "At least one feed or date query was incomplete. Missing data is not interpreted as a score of zero.";
  } else {
    headline.textContent = "The latest poll could not compare both feeds";
    summary.textContent = "The endpoint error is shown below. A failed check does not close or resolve an existing candidate.";
  }

  const health = el("#source-health");
  health.replaceChildren();
  const providers = [
    ["nba_official", "NBA public scoreboard feed"],
    ["espn_secondary", "ESPN public scoreboard feed"]
  ];
  providers.forEach(([key, label]) => {
    const source = monitor.sourceStatus?.[key] || {};
    const row = node("div", "health-row");
    const left = node("span", "health-label");
    const dot = node("span", `health-dot ${source.ok ? "is-up" : "is-down"}`);
    dot.setAttribute("aria-hidden", "true");
    left.append(dot, document.createTextNode(label));
    row.append(left);
    const healthText = source.ok
      ? `${source.eventCount ?? "OK"} event${source.eventCount === 1 ? "" : "s"}${source.warnings?.length ? " · partial date queries" : ""}`
      : (source.error || "Not checked");
    row.append(node("span", "health-state", healthText));
    health.append(row);
  });
  const generatedAt = monitor.generatedAt;
  el("#snapshot-time").textContent = generatedAt ? `Snapshot time (UTC): ${generatedAt} · schedule: every ${monitor.pollIntervalMinutes || 15} minutes; GitHub may delay runs.` : "Snapshot time: not yet available.";

  const games = el("#live-games");
  games.replaceChildren();
  const rows = monitor.games || [];
  if (!rows.length) {
    games.append(node("p", "muted", status === "not_run" ? "No published game comparison yet." : "No matched game comparisons in this snapshot."));
  } else {
    rows.slice(0, 12).forEach((game) => games.append(renderLiveGame(game)));
    if (rows.length > 12) games.append(node("p", "muted", `${rows.length - 12} additional game comparisons are available in the snapshot data.`));
  }
  const flagArea = el("#active-flags");
  flagArea.replaceChildren();
  const flags = monitor.activeDiscrepancies || [];
  if (flags.length) {
    flags.forEach((flag) => {
      flagArea.append(node("p", "flag-note", `Unverified source divergence: ${flag.matchup || flag.nbaGameId}. NBA feed ${displayPair(flag.nbaScore)}; ESPN ${displayPair(flag.espnScore)}. Source lag or provider error is possible.`));
    });
  } else if (status !== "not_run" && status !== "error" && status !== "partial") {
    flagArea.append(node("p", "muted", "No score divergence was observed in this published snapshot. This is not proof that no discrepancy occurred between polls."));
  }
  renderCandidates();
}

function displayPair(score) {
  if (!score || score.away === null || score.home === null) return "not available";
  return `${score.away}–${score.home}`;
}

function renderLiveGame(game) {
  const row = node("div", `live-game-row${game.scoreMismatch ? " is-mismatch" : ""}`);
  const names = game.matchup || `${game.awayTeam?.code || "?"} @ ${game.homeTeam?.code || "?"}`;
  row.append(node("span", "live-matchup", names));
  row.append(node("span", "live-score", `NBA ${displayPair(game.nbaScore)}`));
  row.append(node("span", "live-score", `ESPN ${displayPair(game.espnScore)}`));
  row.append(node("span", "live-state", game.statusText || game.matchStatus || "Status n/a"));
  return row;
}

function renderCandidates() {
  const list = el("#candidate-list");
  list.replaceChildren();
  const candidates = cache.candidates || [];
  el("#candidate-count").textContent = `${candidates.length} candidate${candidates.length === 1 ? "" : "s"}`;
  if (!candidates.length) {
    list.append(node("p", "empty-state", "No automated divergence candidates have been recorded. A clean or unavailable feed is not counted as an error."));
    return;
  }
  candidates.slice().sort((a, b) => String(b.firstDetectedAt || "").localeCompare(String(a.firstDetectedAt || ""))).forEach((candidate) => {
    const article = node("article", "candidate-card");
    const latest = candidate.episodes?.[candidate.episodes.length - 1];
    const active = candidate.monitorStatus === "active_source_divergence";
    article.append(node("h4", "", `${candidate.matchup || candidate.nbaGameId} · ${active ? "active feed divergence" : "feeds later converged"}`));
    article.append(node("p", "", `First detected: ${candidate.firstDetectedAt || "unknown"} · research status: ${candidate.reviewStatus || "unverified"} · investigation: ${candidate.investigationStatus || "needs_review"}. ${candidate.monitorNote || "No source has been declared wrong; manual evidence review is still required."}`));
    const meta = node("p", "candidate-meta", `Latest recorded transition: ${candidate.latestObservationAt || "not established"} · game ${candidate.nbaGameId || "ID unavailable"}`);
    article.append(meta);
    if (latest?.observations?.length) {
      const details = node("details");
      details.append(node("summary", "", `Show ${latest.observations.length} saved observation${latest.observations.length === 1 ? "" : "s"} in this episode`));
      const listItems = node("ul");
      latest.observations.forEach((observation) => {
        const li = node("li", "", `${observation.observedAt}: NBA ${displayPair(observation.nbaScore)} · ESPN ${displayPair(observation.espnScore)}${observation.period ? ` · Q${observation.period} ${observation.clock || ""}` : ""}`);
        listItems.append(li);
      });
      details.append(listItems);
      article.append(details);
    }
    const pbp = latest?.playByPlayContext;
    if (pbp) {
      const contextDetails = node("details");
      contextDetails.append(node("summary", "", "Nearby NBA play-by-play context · not causal proof"));
      contextDetails.append(node("p", "candidate-meta", pbp.note || "Nearby actions are context only; no cause is inferred."));
      if (pbp.retrievalError) contextDetails.append(node("p", "candidate-meta", `Context unavailable: ${pbp.retrievalError}`));
      const actions = node("ul");
      (pbp.actions || []).forEach((action) => {
        const hasScore = action.awayScore !== null && action.homeScore !== null;
        const scoreText = hasScore ? ` · feed score ${action.awayScore}–${action.homeScore}` : "";
        actions.append(node("li", "", `${action.period ? `Q${action.period} ` : ""}${action.clock || "clock unknown"} · ${action.description || "Play description unavailable"}${action.playerName ? ` · ${action.playerName}` : ""}${scoreText}`));
      });
      if (actions.childElementCount) contextDetails.append(actions);
      if (/^https:\/\//i.test(pbp.url || "")) {
        const link = node("a", "", "Open this game's public NBA play-by-play feed");
        link.href = pbp.url;
        link.target = "_blank";
        link.rel = "noopener noreferrer";
        contextDetails.append(link);
      }
      article.append(contextDetails);
    }
    list.append(article);
  });
}

function renderSources() {
  const register = el("#source-register");
  register.replaceChildren();
  const featured = cache.sources.filter((source) => [
    "nba-warriors-release", "nba-warriors-official-x", "nbc-warriors", "nba-cavs-official-x", "athletic-cavs", "hoopswire-cavs", "nba-live-scoreboard-feed", "espn-live-scoreboard-feed", "nba-live-pbp-feed", "nba-api-live-pbp-doc", "nba-rule-2", "nba-rule-5"
  ].includes(source.id));
  featured.forEach((source) => {
    const article = node("article", "source-entry");
    const anchor = sourceLink(source.id, `${source.organization} ↗`);
    if (anchor) article.append(anchor);
    else article.append(node("span", "source-title", `${source.organization} · endpoint pattern`));
    article.append(node("p", "source-role", source.claimRole || source.kind));
    if (source.accessNote) article.append(node("p", "", source.accessNote));
    register.append(article);
  });
}

async function fetchJson(path) {
  const response = await fetch(path, { cache: "no-store" });
  if (!response.ok) throw new Error(`${path}: HTTP ${response.status}`);
  return response.json();
}

async function init() {
  try {
    const [cases, leads, sources, current, candidates] = await Promise.all(Object.entries(DATA_PATHS).map(([, path]) => fetchJson(path)));
    cache.cases = cases.cases || [];
    cache.leads = leads.leads || [];
    cache.sources = sources.sources || [];
    cache.current = current || {};
    cache.candidates = candidates.candidates || [];
    cache.sources.forEach((source) => sourceById.set(source.id, source));
    renderMetrics();
    renderTeamFilter();
    renderRecords();
    renderMonitor();
    renderSources();
    el("#record-search").addEventListener("input", renderRecords);
    el("#evidence-filter").addEventListener("change", renderRecords);
    el("#team-filter").addEventListener("change", renderRecords);
  } catch (error) {
    const message = `Research data could not be loaded: ${error.message}. Serve the site from the repository root or check the published data files.`;
    el("#case-list").replaceChildren(node("p", "empty-state", message));
    el("#live-games").replaceChildren(node("p", "empty-state", message));
    el("#results-count").textContent = "Data unavailable";
  }
}

init();
