(() => {
  "use strict";

  const DATA_FILES = {
    cases: "data/cases.json",
    leads: "data/leads.json",
    feed: "data/live-feed.json",
    state: "data/monitor-state.json",
  };

  const $ = (selector) => document.querySelector(selector);
  const escapeHtml = (value) => String(value ?? "").replace(/[&<>"']/g, (char) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  })[char]);

  const formatDate = (value) => {
    if (!value) return "Date not established";
    const date = new Date(`${value.slice(0, 10)}T12:00:00Z`);
    if (Number.isNaN(date.getTime())) return escapeHtml(value);
    return new Intl.DateTimeFormat(undefined, { year: "numeric", month: "short", day: "numeric", timeZone: "UTC" }).format(date);
  };

  const formatTimestamp = (value) => {
    if (!value) return "No successful snapshot has been published";
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return escapeHtml(value);
    return new Intl.DateTimeFormat(undefined, {
      year: "numeric", month: "short", day: "numeric", hour: "numeric", minute: "2-digit", timeZoneName: "short",
    }).format(date);
  };

  const scoreLine = (score, awayAbbr, homeAbbr) => {
    if (!score || score.away == null || score.home == null) return "Not reported";
    return `${awayAbbr} ${score.away} – ${score.home} ${homeAbbr}`;
  };

  const scoreTotal = (score) => {
    if (!score || score.total == null) return "Not established";
    return `${score.total}`;
  };

  const safeExternalUrl = (value) => {
    try {
      const url = new URL(value);
      return url.protocol === "https:" ? url.href : null;
    } catch {
      return null;
    }
  };

  const sourceMapFor = (item) => new Map((item.sources || []).map((source) => [source.id, source]));

  const sourceLinks = (ids, sourceMap) => {
    const links = (ids || []).map((id) => {
      const source = sourceMap.get(id);
      const url = source && safeExternalUrl(source.url);
      if (!source || !url) return "";
      return `<a class="source-ref" href="${escapeHtml(url)}" target="_blank" rel="noopener noreferrer">${escapeHtml(source.title)} ↗</a>`;
    }).filter(Boolean);
    return links.length ? `<span class="inline-citations">Evidence: ${links.join(" · ")}</span>` : `<span class="inline-citations citation-missing">No linked source supplied</span>`;
  };

  const evidenceText = (evidence) => {
    if (!evidence) return "Not captured";
    const away = evidence.away;
    const home = evidence.home;
    if (away == null || home == null) return "Not captured";
    return `${away} – ${home}`;
  };

  const eventScoreCard = (label, evidence, awayAbbr, homeAbbr, sourceMap) => {
    if (!evidence) return "";
    const derivation = evidence.derivation
      ? `<p class="evidence-caption">${escapeHtml(evidence.derivation)}</p>`
      : "";
    return `<div class="score-snapshot">
      <span>${escapeHtml(label)}</span>
      <strong>${escapeHtml(awayAbbr)} ${escapeHtml(evidence.away)} – ${escapeHtml(evidence.home)} ${escapeHtml(homeAbbr)}</strong>
      <p class="evidence-caption">${escapeHtml((evidence.evidence_kind || "").replaceAll("_", " "))}</p>
      ${derivation}
      ${sourceLinks(evidence.source_ids, sourceMap)}
    </div>`;
  };

  const timelineMarkup = (timeline, sourceMap) => {
    if (!Array.isArray(timeline) || timeline.length === 0) return `<p class="muted-text">No sourced timeline entries.</p>`;
    return `<ol class="timeline-list">${timeline.map((item) => `
      <li class="timeline-item"><strong>${escapeHtml(formatDate(item.date))}</strong>${escapeHtml(item.event || "Event detail not supplied.")}
      <div>${sourceLinks(item.source_ids, sourceMap)}</div>
      ${item.timestamp ? `<span class="timeline-time">Recorded timestamp: ${escapeHtml(item.timestamp)}${item.timestamp_precision ? ` · ${escapeHtml(item.timestamp_precision)}` : ""}</span>` : `<span class="timeline-time">${escapeHtml(item.timestamp_precision || "Exact time not established")}</span>`}</li>`).join("")}</ol>`;
  };

  const sourcesMarkup = (sources) => {
    if (!Array.isArray(sources) || sources.length === 0) return `<p class="muted-text">No source links are attached.</p>`;
    return `<div class="source-list">${sources.map((source) => {
      const url = safeExternalUrl(source.url);
      const addl = (source.additional_urls || []).map((item) => safeExternalUrl(item)).filter(Boolean);
      return `<article class="source-card">
        ${url ? `<a href="${escapeHtml(url)}" target="_blank" rel="noopener noreferrer">${escapeHtml(source.title)} ↗</a>` : `<span>${escapeHtml(source.title)}</span>`}
        <p class="source-publisher">${escapeHtml(source.publisher)} · ${escapeHtml((source.source_type || "").replaceAll("_", " "))}</p>
        ${source.supports?.length ? `<p class="source-supports">Supports: ${escapeHtml(source.supports.join("; "))}</p>` : ""}
        ${source.accessed_on ? `<p class="source-access">Reviewed ${escapeHtml(formatDate(source.accessed_on))}</p>` : ""}
        ${addl.map((extra, index) => `<a class="source-extra" href="${escapeHtml(extra)}" target="_blank" rel="noopener noreferrer">Additional source ${index + 1} ↗</a>`).join("")}
      </article>`;
    }).join("")}</div>`;
  };

  const sourceObservationMarkup = (observations, sourceMap) => {
    if (!Array.isArray(observations) || observations.length === 0) return "";
    return `<h4 class="case-subheading">What the sources showed</h4><div class="source-observations">${observations.map((item) => {
      const source = sourceMap.get(item.source_id);
      const url = source && safeExternalUrl(source.url);
      return `<div class="source-observation">
        <div><strong>${url ? `<a href="${escapeHtml(url)}" target="_blank" rel="noopener noreferrer">${escapeHtml(source.title)} ↗</a>` : escapeHtml(item.source_id)}</strong>
        <p>${escapeHtml(item.observation)}</p>${item.role ? `<span class="source-role">${escapeHtml(item.role)}</span>` : ""}</div>
        <span class="observation-date">${escapeHtml(item.observed_at || "Date not established")}${item.timestamp_precision ? `<br>${escapeHtml(item.timestamp_precision)}` : ""}</span>
      </div>`;
    }).join("")}</div>`;
  };

  const renderCase = (item) => {
    const game = item.game || {};
    const away = game.away_team || {};
    const home = game.home_team || {};
    const scores = item.scores || {};
    const sourceMap = sourceMapFor(item);
    const event = item.event || {};
    const scoreEvents = [
      ["Before play", event.score_before],
      ["Original entry", event.immediately_after_original_entry],
      ["After corrected entry", event.immediately_after_corrected_entry],
    ].filter(([, entry]) => entry);
    const original = scores.originally_reported_final || {};
    const corrected = scores.corrected_final || {};
    const official = scores.final_official || {};
    const playerImpact = item.impact?.player_points;
    const playerPointsLine = playerImpact
      ? `${playerImpact.originally_reported ?? "Unknown"} → ${playerImpact.corrected ?? "Unknown"}`
      : item.impact?.player_points_after_correction != null
        ? `${item.impact.player_points_before_correction ?? "Unknown"} → ${item.impact.player_points_after_correction}`
        : "Not established";
    const teamPointsDelta = item.impact?.team_points_delta ?? item.impact?.final_total_delta;
    const filterText = JSON.stringify(item).toLowerCase();
    const statusLabel = item.official_record_status === "nba_record_corrected" ? "NBA record corrected" : "Verified case";
    const sourceCount = (item.sources || []).length;

    return `<details class="case-card" data-type="${escapeHtml(item.incident_type || "other")}" data-verification="${escapeHtml(item.verification_status || "unverified")}" data-search="${escapeHtml(filterText)}">
      <summary class="case-summary">
        <span class="case-date">${escapeHtml(formatDate(game.date))}<br>${escapeHtml(game.game_id || "Game ID unavailable")}</span>
        <div class="case-headline"><h3>${escapeHtml(item.title || "Untitled case")}</h3><p>${escapeHtml(item.summary || "No summary supplied.")}</p><span class="case-badge-row"><span class="case-badge">${escapeHtml(statusLabel)}</span><span class="case-badge badge-muted">${escapeHtml((item.incident_type || "case").replaceAll("_", " "))}</span>${item.correction_stage ? `<span class="case-badge badge-muted">${escapeHtml(item.correction_stage.replaceAll("_", " "))}</span>` : ""}</span></div>
        <span class="case-mini-score">${escapeHtml(away.abbreviation || "Away")} ${escapeHtml(original.away ?? "?")}–${escapeHtml(original.home ?? "?")} ${escapeHtml(home.abbreviation || "Home")} <span aria-hidden="true">→</span> <strong>${escapeHtml(official.away ?? "?")}–${escapeHtml(official.home ?? "?")}</strong></span>
        <span class="case-chevron" aria-hidden="true">⌄</span>
      </summary>
      <div class="case-body">
        <p>${escapeHtml(item.summary || "")}</p>
        <div class="case-overview">
          <section class="case-detail-box" aria-label="Game and scoring play details">
            <p class="detail-label">Game &amp; scoring play</p>
            <p class="case-event-text"><strong>${escapeHtml(away.name || "Away team")} at ${escapeHtml(home.name || "Home team")}</strong> · ${escapeHtml(game.competition || "Competition not identified")}<br>${escapeHtml(event.play || "Scoring play not established.")}</p>
            <div class="case-event-meta">
              <span class="meta-chip">${event.period ? `Q${escapeHtml(event.period)}` : "Period unknown"}${event.clock ? ` · ${escapeHtml(event.clock)}` : ""}</span>
              ${event.player ? `<span class="meta-chip">${escapeHtml(event.player)}</span>` : ""}
              ${event.team ? `<span class="meta-chip">${escapeHtml(event.team)}</span>` : ""}
              ${event.clock_precision ? `<span class="meta-chip">${escapeHtml(event.clock_precision)}</span>` : ""}
            </div>
            ${scoreEvents.length ? `<div class="score-before-after">${scoreEvents.map(([label, evidence]) => eventScoreCard(label, evidence, away.abbreviation || "AWY", home.abbreviation || "HOM", sourceMap)).join("")}</div>` : "<p class='muted-text'>Event-local score sequence not documented.</p>"}
          </section>
          <section class="case-detail-box" aria-label="Cause and investigation status">
            <p class="detail-label">What changed · cause</p>
            <div class="case-cause"><strong>${escapeHtml((item.cause?.status || "Unverified").replaceAll("_", " "))}.</strong> ${escapeHtml(item.cause?.description || "Cause not established.")}</div>
            <div class="case-impact">
              <div class="impact-item"><span>Affected player</span><strong>${escapeHtml(item.impact?.affected_player || event.player || "Not stated")}</strong></div>
              <div class="impact-item"><span>Affected team</span><strong>${escapeHtml(item.impact?.affected_team || item.impact?.team || event.team || "Not stated")}</strong></div>
              <div class="impact-item"><span>Player points · reported → corrected</span><strong>${escapeHtml(playerPointsLine)}</strong></div>
              <div class="impact-item"><span>Team-score change</span><strong>${teamPointsDelta == null ? "Not established" : `+${escapeHtml(teamPointsDelta)} point`}</strong></div>
            </div>
            ${sourceLinks(item.cause?.source_ids, sourceMap)}
          </section>
        </div>

        <section class="final-score-compare" aria-label="Original, corrected, and final official scores">
          <h4>Final score history · away–home ordering</h4>
          <div class="score-grid">
            <div class="score-col-head">Record</div><div class="score-col-head">${escapeHtml(away.abbreviation || "Away")}</div><div class="score-col-head">${escapeHtml(home.abbreviation || "Home")}</div><div class="score-col-head">Game total</div>
            <div class="score-row-label">Originally reported</div><div class="score-value">${escapeHtml(original.away ?? "—")}</div><div class="score-value">${escapeHtml(original.home ?? "—")}</div><div class="score-value">${escapeHtml(scoreTotal(original))}</div>
            <div class="score-row-label">Corrected value</div><div class="score-value corrected">${escapeHtml(corrected.away ?? "—")}</div><div class="score-value corrected">${escapeHtml(corrected.home ?? "—")}</div><div class="score-value corrected">${escapeHtml(scoreTotal(corrected))}</div>
            <div class="score-row-label">Final official</div><div class="score-value">${escapeHtml(official.away ?? "—")}</div><div class="score-value">${escapeHtml(official.home ?? "—")}</div><div class="score-value">${escapeHtml(scoreTotal(official))}</div>
          </div>
        </section>
        <div class="score-citations">
          <p class="score-citation-row"><strong>Original:</strong> ${sourceLinks(original.source_ids, sourceMap)}</p>
          <p class="score-citation-row"><strong>Correction:</strong> ${sourceLinks(corrected.source_ids, sourceMap)}</p>
          <p class="score-citation-row"><strong>Final official:</strong> ${sourceLinks(official.source_ids, sourceMap)}</p>
          <p class="muted-text">${escapeHtml(scores.total_calculation_note || "Totals are not calculated unless the source values are available.")}</p>
        </div>

        ${sourceObservationMarkup(item.source_observations, sourceMap)}
        <h4 class="case-subheading">Change timeline</h4>
        ${timelineMarkup(item.timeline, sourceMap)}
        <h4 class="case-subheading">What remains unknown</h4>
        ${Array.isArray(item.unknowns) && item.unknowns.length ? `<ul class="case-unknowns">${item.unknowns.map((unknown) => `<li>${escapeHtml(unknown)}</li>`).join("")}</ul>` : `<p class="muted-text">No unknowns listed; check the sources before interpreting this record.</p>`}
        <div class="duration-note"><strong>Correction duration:</strong> ${item.duration?.seconds == null ? "Not calculated." : `${escapeHtml(item.duration.seconds)} seconds.`} ${escapeHtml(item.duration?.note || "Exact timing not established.")}</div>
        <h4 class="case-subheading">Sources for independent review <span class="source-count">${sourceCount}</span></h4>
        ${sourcesMarkup(item.sources)}
      </div>
    </details>`;
  };

  const renderStatistics = (cases, leads, coverageNote) => {
    const verified = cases.length;
    const finalChanged = cases.filter((item) => {
      const first = item.scores?.originally_reported_final;
      const final = item.scores?.final_official;
      return first && final && (first.away !== final.away || first.home !== final.home);
    }).length;
    const openLeads = leads.filter((lead) => lead.status !== "resolved").length;
    $("#heroVerifiedCount").textContent = String(verified);
    $("#heroOpenLeadCount").textContent = String(openLeads);
    $("#statCases").textContent = String(verified);
    $("#statFinalScore").textContent = `${finalChanged} / ${verified || 0}`;
    $("#ledgerCount").textContent = String(verified);
    $("#coverageNote").textContent = coverageNote || "This is an initial evidence-backed sample, not a comprehensive historical database. Do not interpret the current count as the number of scoring corrections in NBA history.";
    const typeCounts = new Map();
    for (const item of cases) {
      const type = item.incident_type || "unclassified";
      typeCounts.set(type, (typeCounts.get(type) || 0) + 1);
    }
    const breakdown = $("#typeBreakdown");
    breakdown.innerHTML = typeCounts.size
      ? [...typeCounts.entries()].sort((a, b) => b[1] - a[1]).map(([type, count]) => `<span class="type-stat"><strong>${count}</strong><span>${escapeHtml(type.replaceAll("_", " "))}</span></span>`).join("")
      : `<span class="muted-text">No verified incident types yet.</span>`;
  };

  const renderFilters = (cases) => {
    const select = $("#typeFilter");
    const types = [...new Set(cases.map((item) => item.incident_type).filter(Boolean))].sort();
    for (const type of types) {
      const option = document.createElement("option");
      option.value = type;
      option.textContent = type.replaceAll("_", " ");
      select.append(option);
    }
  };

  const applyCaseFilters = () => {
    const query = $("#caseSearch").value.trim().toLowerCase();
    const type = $("#typeFilter").value;
    const verification = $("#verificationFilter").value;
    let shown = 0;
    document.querySelectorAll(".case-card").forEach((card) => {
      const matchesText = !query || card.dataset.search.includes(query);
      const matchesType = type === "all" || card.dataset.type === type;
      const matchesVerification = verification === "all" || card.dataset.verification.includes("confirmed");
      const visible = matchesText && matchesType && matchesVerification;
      card.hidden = !visible;
      if (visible) shown += 1;
    });
    $("#noCasesMessage").hidden = shown !== 0;
  };

  const renderCases = (cases) => {
    const container = $("#caseList");
    container.innerHTML = cases.length
      ? cases.map(renderCase).join("")
      : `<div class="empty-state"><span class="empty-state-mark" aria-hidden="true">∅</span><p>No verified case records are published yet.</p></div>`;
    renderFilters(cases);
    $("#caseSearch").addEventListener("input", applyCaseFilters);
    $("#typeFilter").addEventListener("change", applyCaseFilters);
    $("#verificationFilter").addEventListener("change", applyCaseFilters);
  };

  const teamLine = (team) => `<div class="game-team-line"><span class="team-abbr" title="${escapeHtml(team?.name || "Team name unavailable")}">${escapeHtml(team?.abbreviation || "—")}</span></div>`;

  const renderCurrentGames = (feed) => {
    const container = $("#currentGames");
    const games = Array.isArray(feed.games) ? feed.games : [];
    if (games.length === 0) {
      const message = feed.status === "healthy"
        ? "Both feeds returned successfully, but no games were included in the saved snapshot. That does not establish that no scoring discrepancy exists outside those responses."
        : feed.status === "degraded"
          ? "A source is unavailable. No current game list can be verified from this snapshot; this is not a clean bill of health."
          : "Waiting for the first published source snapshot. The absence of a feed is not evidence of no discrepancies.";
      container.innerHTML = `<div class="empty-state"><span class="empty-state-mark" aria-hidden="true">◷</span><p>${escapeHtml(message)}</p></div>`;
      return;
    }
    container.innerHTML = `<div class="game-table-wrap"><table class="game-table">
      <thead><tr><th scope="col">Matchup</th><th scope="col">NBA feed</th><th scope="col">ESPN feed</th><th scope="col">Comparison</th><th scope="col">Snapshot</th><th scope="col">NBA PBP context · not attribution</th></tr></thead>
      <tbody>${games.map((game) => {
        const scores = game.scores || {};
        const nba = scores.nba || {};
        const espn = scores.espn || {};
        const isMismatch = game.score_mismatch === true;
        const noComparison = game.score_mismatch == null;
        const pbpUrl = safeExternalUrl(game.play_by_play_source_url);
        const scoringPlay = game.latest_official_scoring_play;
        const statusText = game.status_text || game.status || "Status not supplied";
        return `<tr>
          <td><div class="game-matchup">${teamLine(game.away_team)}${teamLine(game.home_team)}<span class="game-clock">${escapeHtml(statusText)}${game.period ? ` · Q${escapeHtml(game.period)}` : ""}${game.clock ? ` · ${escapeHtml(game.clock)}` : ""}</span></div></td>
          <td>${escapeHtml(nba.away ?? "—")}–${escapeHtml(nba.home ?? "—")}</td>
          <td>${espn.away == null || espn.home == null ? "Unavailable" : `${escapeHtml(espn.away)}–${escapeHtml(espn.home)}`}</td>
          <td>${isMismatch ? `<span class="diff-chip">Potential difference</span>` : noComparison ? `<span class="muted-text">Not compared</span>` : `<span class="match-chip">Feeds agree</span>`}</td>
          <td><span class="game-clock">${escapeHtml(formatTimestamp(game.observed_at))}${game.stale ? " · stale" : ""}</span></td>
          <td class="source-url-cell">${pbpUrl ? `<a href="${escapeHtml(pbpUrl)}" target="_blank" rel="noopener noreferrer">Open PBP ↗</a>` : "—"}${scoringPlay?.description ? `<span class="pbp-context">Context only · ${scoringPlay.period ? `Q${escapeHtml(scoringPlay.period)} ` : ""}${escapeHtml(scoringPlay.clock || "")} · ${escapeHtml(scoringPlay.description)}</span>` : ""}</td>
        </tr>`;
      }).join("")}</tbody></table></div>`;
  };

  const scorePair = (score) => score && score.away != null && score.home != null
    ? `${score.away}–${score.home}`
    : "not available";

  const investigationObservationTime = (first, latest) => {
    const firstAt = first.observed_at;
    const latestAt = latest.observed_at;
    if (!firstAt && !latestAt) return null;
    if (firstAt && latestAt && firstAt !== latestAt) {
      return `Monitor poll timestamps · first ${formatTimestamp(firstAt)} · latest ${formatTimestamp(latestAt)}`;
    }
    return `Monitor poll timestamp · ${formatTimestamp(firstAt || latestAt)}`;
  };

  const sourceHeaderTimes = (observation) => {
    const metadata = observation.source_metadata || {};
    const values = Object.entries(metadata)
      .filter(([, source]) => source?.last_modified)
      .map(([key, source]) => `${key.replaceAll("_", " ")}: ${source.last_modified}`);
    return values.length
      ? `HTTP Last-Modified (not necessarily source publication time) · ${values.join(" · ")}`
      : null;
  };

  const investigationDetails = (item) => {
    const first = item.first_observation || {};
    const latest = item.latest_observation || first;
    const firstDetails = item.first_details || {};
    if (item.detection_type === "cross_source_score_mismatch") {
      const nba = firstDetails.nba_score || first.scores?.nba;
      const espn = firstDetails.espn_score || first.scores?.espn;
      const play = latest.latest_official_scoring_play;
      return {
        text: `First saved values: NBA ${scorePair(nba)} / ESPN ${scorePair(espn)} · ${item.observation_count || 1} saved observation${item.observation_count === 1 ? "" : "s"}.`,
        play: play?.description ? `${play.description}${play.clock ? ` · ${play.clock}` : ""}` : null,
        links: firstDetails.source_urls || {},
        time: investigationObservationTime(first, latest),
        sourceTime: sourceHeaderTimes(latest),
        resolution: item.resolution?.note || null,
      };
    }
    if (item.detection_type === "nba_final_feed_revision") {
      return {
        text: `NBA scoreboard feed changed from ${scorePair(item.previous_nba_feed_score)} to ${scorePair(item.current_nba_feed_score)} · exact record-change time unknown.`,
        play: null,
        links: { nba: firstDetails.nba_scoreboard_source_url },
        time: investigationObservationTime(first, latest),
        sourceTime: sourceHeaderTimes(latest),
        resolution: item.resolution?.note || firstDetails.warning || null,
      };
    }
    return {
      text: `${String(item.detection_type || "candidate").replaceAll("_", " ")} · ${item.observation_count || 1} saved observation${item.observation_count === 1 ? "" : "s"}.`,
      play: null,
      links: {},
      time: investigationObservationTime(first, latest),
      sourceTime: sourceHeaderTimes(latest),
      resolution: item.resolution?.note || null,
    };
  };

  const renderMonitor = (feed, state) => {
    const status = feed?.status || "not_started";
    const pill = $("#monitorStatus");
    const potentialDifference = (Array.isArray(feed?.games) && feed.games.some((game) => game.score_mismatch === true))
      || Number(feed?.active_investigation_count || 0) > 0;
    const labels = {
      healthy: potentialDifference ? ["status-warning", "Review candidate"] : ["status-good", "Feeds available"],
      degraded: ["status-warning", "Feed degraded"],
      not_started: ["status-neutral", "Not yet active"],
    };
    const [className, label] = labels[status] || labels.not_started;
    pill.className = `status-pill ${className}`;
    pill.innerHTML = `<span class="status-light"></span>${escapeHtml(label)}`;
    $("#feedTimestamp").textContent = feed?.last_updated_at
      ? `Latest published observation · ${formatTimestamp(feed.last_updated_at)}`
      : "No successful poll has been published.";
    const notice = $("#feedNotice");
    notice.textContent = feed?.note || "No live-feed status is available.";
    notice.className = "feed-notice";
    if (status === "degraded") notice.classList.add("notice-degraded");
    else if (potentialDifference) notice.classList.add("notice-mismatch");

    const health = feed?.source_health || {};
    $("#sourceHealth").innerHTML = ["nba", "espn"].map((key) => {
      const source = health[key] || {};
      const sourceStatus = source.status || "not_checked";
      const good = sourceStatus === "ok";
      const labelText = key === "nba" ? "NBA primary" : "ESPN secondary";
      return `<span class="health-chip ${good ? "ok" : sourceStatus === "not_checked" ? "" : "down"}" title="${escapeHtml(sourceStatus)}">${escapeHtml(labelText)} · ${escapeHtml(sourceStatus.replaceAll("_", " "))}</span>`;
    }).join("");
    renderCurrentGames(feed || { status: "not_started", games: [] });

    const investigations = Array.isArray(state?.investigations) ? [...state.investigations].reverse() : [];
    const openCount = investigations.filter((item) => item.status !== "resolved").length;
    const resolvedCount = investigations.length - openCount;
    const panel = $("#investigationsPanel");
    if (investigations.length) {
      panel.hidden = false;
      $("#investigationsTitle").textContent = `${openCount} open · ${resolvedCount} resolved`;
      $("#investigationsList").innerHTML = investigations.map((item) => {
        const detail = investigationDetails(item);
        const matchup = `${item.away_team?.abbreviation || "Away"} @ ${item.home_team?.abbreviation || "Home"}`;
        const nbaUrl = safeExternalUrl(detail.links?.nba);
        const espnUrl = safeExternalUrl(detail.links?.espn);
        const playUrl = safeExternalUrl(item.latest_observation?.play_by_play_source_url || item.first_observation?.play_by_play_source_url);
        const status = item.status || "detected";
        return `<div class="investigation-row ${status === "resolved" ? "investigation-resolved" : ""}">
          <div class="investigation-copy">
            <strong>${escapeHtml(matchup)} · ${escapeHtml(formatDate(item.game_date))}</strong>
            <span>${escapeHtml(detail.text)}</span>
            ${detail.time ? `<span class="investigation-time">${escapeHtml(detail.time)}</span>` : ""}
            ${detail.sourceTime ? `<span class="investigation-time">${escapeHtml(detail.sourceTime)}</span>` : ""}
            ${detail.play ? `<span class="investigation-play">NBA PBP context: ${escapeHtml(detail.play)}</span>` : ""}
            ${detail.resolution ? `<span class="investigation-resolution">${escapeHtml(detail.resolution)}</span>` : ""}
            <span class="investigation-links">${nbaUrl ? `<a href="${escapeHtml(nbaUrl)}" target="_blank" rel="noopener noreferrer">NBA source ↗</a>` : ""}${espnUrl ? `<a href="${escapeHtml(espnUrl)}" target="_blank" rel="noopener noreferrer">ESPN source ↗</a>` : ""}${playUrl ? `<a href="${escapeHtml(playUrl)}" target="_blank" rel="noopener noreferrer">Official PBP ↗</a>` : ""}</span>
          </div>
          <span class="investigation-status ${status === "resolved" ? "status-resolved" : ""}">${escapeHtml(status.replaceAll("_", " "))} · unverified</span>
        </div>`;
      }).join("");
    } else {
      panel.hidden = true;
      $("#investigationsList").innerHTML = "";
    }
  };

  const renderLeads = (leads) => {
    const container = $("#leadDetails");
    if (!Array.isArray(leads) || !leads.length) {
      container.innerHTML = `<span>No additional lead records</span>`;
      return;
    }
    container.innerHTML = leads.map((lead) => {
      const details = [
        lead.known_details?.game_date ? `Date ${lead.known_details.game_date}` : "Game date not supplied",
        lead.known_details?.teams ? lead.known_details.teams.join(" / ") : "Teams not supplied",
        lead.known_details?.source_a || lead.known_details?.source_b ? "Source details supplied" : "Sources not supplied",
      ];
      return `${details.map((detail) => `<span>${escapeHtml(detail)}</span>`).join("")}<p class="lead-next">${escapeHtml(lead.research_note || "No research note supplied.")}</p>`;
    }).join("");
  };

  const loadJson = async (path) => {
    const response = await fetch(path, { cache: "no-store" });
    if (!response.ok) throw new Error(`${path} returned HTTP ${response.status}`);
    return response.json();
  };

  const loadApp = async () => {
    const results = await Promise.allSettled(Object.entries(DATA_FILES).map(async ([key, path]) => [key, await loadJson(path)]));
    const docs = {};
    for (const result of results) {
      if (result.status === "fulfilled") {
        const [key, value] = result.value;
        docs[key] = value;
      } else {
        console.error("Unable to load research data", result.reason);
      }
    }

    const cases = docs.cases?.cases || [];
    const leads = docs.leads?.leads || [];
    renderStatistics(cases, leads, docs.cases?.coverage_note);
    renderCases(cases);
    renderLeads(leads);
    renderMonitor(docs.feed || { status: "not_started", games: [], source_health: {} }, docs.state || { investigations: [] });

    if (!docs.cases) {
      $("#caseList").innerHTML = `<div class="empty-state"><span class="empty-state-mark" aria-hidden="true">!</span><p>Case data could not be loaded. Review the repository data file or try reloading.</p></div>`;
    }
    if (!docs.feed) {
      $("#feedNotice").textContent = "The published feed file could not be loaded. This is not evidence of no games or discrepancies.";
      $("#feedNotice").classList.add("notice-degraded");
    }
  };

  loadApp().catch((error) => {
    console.error("Dashboard initialization failed", error);
    const message = $("#feedNotice");
    if (message) {
      message.textContent = "The research dashboard could not load its saved data. Check the repository JSON files and reload.";
      message.classList.add("notice-degraded");
    }
  });
})();
