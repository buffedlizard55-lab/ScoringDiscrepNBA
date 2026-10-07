(() => {
  "use strict";

  const DATA_FILES = {
    cases: "data/reviewed-cases.json",
    leads: "data/leads.json",
    feed: "data/live-feed.json",
    state: "data/monitor-state.json",
    alerts: "data/alerts.json",
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
    const disputedPlayerValues = playerImpact?.status === "disputed_unresolved"
      && Array.isArray(playerImpact.reported_values)
      ? playerImpact.reported_values
      : [];
    const playerPointsLine = disputedPlayerValues.length
      ? `${disputedPlayerValues.map((entry) => entry.value).join(" vs ")} · unresolved`
      : playerImpact
        ? `${playerImpact.originally_reported ?? "Unknown"} → ${playerImpact.corrected ?? "Unknown"}`
        : item.impact?.player_points_after_correction != null
          ? `${item.impact.player_points_before_correction ?? "Unknown"} → ${item.impact.player_points_after_correction}`
          : "Not established";
    const playerPointsLabel = disputedPlayerValues.length
      ? "Conflicting player-point reports"
      : "Player points · reported → corrected";
    const playerPointsNote = playerImpact?.note
      ? `<p class="impact-note">${escapeHtml(playerImpact.note)}</p>`
      : "";
    const playerPointsEvidence = disputedPlayerValues.length
      ? `<div class="player-point-positions">${disputedPlayerValues.map((entry) => `<p><strong>${escapeHtml(entry.value)} reported by:</strong> ${sourceLinks(entry.source_ids, sourceMap)}</p>`).join("")}</div>`
      : "";
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
              <div class="impact-item"><span>${escapeHtml(playerPointsLabel)}</span><strong>${escapeHtml(playerPointsLine)}</strong>${playerPointsNote}${playerPointsEvidence}</div>
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
        ? "Every configured source returned successfully, but no games were included in the saved snapshot. That does not establish that no scoring discrepancy exists outside those responses."
        : feed.status === "degraded"
          ? "A source is unavailable and no game rows could be built from the source(s) that answered. This snapshot cannot be read as a clean bill of health."
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
        const publishedBy = Array.isArray(game.score_sources) && game.score_sources.length
          ? game.score_sources
          : Object.keys(scores).filter((key) => scores[key] && scores[key].away != null && scores[key].home != null);
        const sideScore = (score) => (score.away == null || score.home == null ? `<span class="muted-text">Not published</span>` : `${escapeHtml(score.away)}–${escapeHtml(score.home)}`);
        const publishedNote = publishedBy.length === 1
          ? `Only ${escapeHtml(publishedBy[0].toUpperCase())} published this game in the saved snapshot; nothing could be compared.`
          : "";
        const pbpUrl = safeExternalUrl(game.play_by_play_source_url);
        const scoringPlay = game.latest_official_scoring_play;
        const statusText = game.status_text || game.status || "Status not supplied";
        return `<tr>
          <td><div class="game-matchup">${teamLine(game.away_team)}${teamLine(game.home_team)}<span class="game-clock">${escapeHtml(statusText)}${game.period ? ` · Q${escapeHtml(game.period)}` : ""}${game.clock ? ` · ${escapeHtml(game.clock)}` : ""}</span></div></td>
          <td>${sideScore(nba)}</td>
          <td>${sideScore(espn)}</td>
          <td>${isMismatch ? `<span class="diff-chip">Potential difference</span>` : noComparison ? `<span class="muted-text">Not compared</span>` : `<span class="match-chip">Feeds agree</span>`}${publishedNote ? `<span class="pbp-context">${publishedNote}</span>` : ""}</td>
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
      healthy: potentialDifference
        ? ["status-warning", "Review candidate in snapshot"]
        : ["status-good", "Snapshot: feeds available"],
      degraded: ["status-warning", "Snapshot: degraded"],
      not_started: ["status-neutral", "Not yet active"],
    };
    const [className, label] = labels[status] || labels.not_started;
    pill.className = `status-pill ${className}`;
    pill.innerHTML = `<span class="status-light"></span>${escapeHtml(label)}`;
    $("#feedTimestamp").textContent = feed?.last_updated_at
      ? `Last material snapshot change (UTC) · ${formatTimestamp(feed.last_updated_at)} · not a poll heartbeat`
      : "No saved material-snapshot timestamp is recorded.";
    const notice = $("#feedNotice");
    const freshnessNote = status === "not_started"
      ? null
      : "This snapshot does not store a per-poll heartbeat, so it may be stale. Check workflow run history for the latest attempt.";
    notice.textContent = [feed?.note || "No live-feed status is available.", freshnessNote].filter(Boolean).join(" ");
    notice.className = "feed-notice";
    if (status === "degraded") {
      notice.classList.add("notice-degraded");
    } else if (potentialDifference) notice.classList.add("notice-mismatch");

    const health = feed?.source_health || {};
    const SOURCE_LABELS = { nba: "NBA primary", espn: "ESPN secondary" };
    const healthKeys = Object.keys(health);
    const sourceKeys = healthKeys.length ? healthKeys : ["nba", "espn"];
    $("#sourceHealth").innerHTML = sourceKeys.map((key) => {
      const source = health[key] || {};
      const sourceStatus = source.status || "not_checked";
      const good = sourceStatus === "ok";
      const labelText = SOURCE_LABELS[key] || key.toUpperCase();
      const title = `${sourceStatus}${source.error ? ` · ${source.error}` : ""}`;
      return `<span class="health-chip ${good ? "ok" : sourceStatus === "not_checked" ? "" : "down"}" title="${escapeHtml(title)}">${escapeHtml(labelText)} · ${escapeHtml(sourceStatus.replaceAll("_", " "))}</span>`;
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


  const SEVERITY_LABEL = { critical: "Critical", high: "High", medium: "Medium", info: "Info" };

  const renderAlertEvidence = (alert) => {
    const entries = Array.isArray(alert.evidence) ? alert.evidence : [];
    if (entries.length === 0) return `<p class="muted-text">No evidence link was attached to this alert. Treat it as incomplete.</p>`;
    return `<ul class="alert-evidence">${entries.map((entry) => {
      const url = safeExternalUrl(entry.url);
      const label = escapeHtml(entry.label || "Source");
      const value = entry.value ? ` — ${escapeHtml(entry.value)}` : "";
      return `<li>${url ? `<a href="${escapeHtml(url)}" target="_blank" rel="noopener noreferrer">${label} ↗</a>` : label}${value}</li>`;
    }).join("")}</ul>`;
  };

  const renderAlertArithmetic = (alert) => {
    const checks = Array.isArray(alert.arithmetic) ? alert.arithmetic : [];
    if (!checks.length) return "";
    return `<details class="alert-arithmetic"><summary>The arithmetic behind this alert</summary>
      <div class="game-table-wrap"><table class="game-table">
        <thead><tr><th scope="col">Side</th><th scope="col">Team</th><th scope="col">Provider final</th><th scope="col">Derived points</th><th scope="col">Difference</th><th scope="col">FG</th><th scope="col">3PT</th><th scope="col">FT</th></tr></thead>
        <tbody>${checks.map((check) => {
          const components = check.components || {};
          const cell = (key) => Array.isArray(components[key]) ? components[key].join("-") : "—";
          return `<tr><td>${escapeHtml(check.side || "—")}</td><td>${escapeHtml(check.team || "—")}</td><td>${escapeHtml(check.provider_reported_final ?? "—")}</td><td>${escapeHtml(check.derived_points ?? "—")}</td><td>${escapeHtml(check.difference ?? "—")}</td><td>${escapeHtml(cell("fieldGoalsMade-attempted"))}</td><td>${escapeHtml(cell("threePointersMade-attempted"))}</td><td>${escapeHtml(cell("freeThrowsMade-attempted"))}</td></tr>`;
        }).join("")}</tbody></table></div>
      <p class="evidence-caption">${escapeHtml(alert.method || "Derived from the provider's own published components.")}</p></details>`;
  };

  const renderAlertDispatch = (alert) => {
    const dispatch = alert.dispatch || {};
    const issueUrl = safeExternalUrl(dispatch.issue_url);
    const stateLabels = {
      pending: "Queued for notification",
      sent: "Notification delivered",
      failed: "Notification failed",
      skipped: "Notification skipped",
      not_required: "Site-only (no notification)",
    };
    const parts = [stateLabels[dispatch.status] || "Notification state unknown"];
    if (dispatch.reason) parts.push(dispatch.reason);
    if (issueUrl) parts.push(`<a href="${escapeHtml(issueUrl)}" target="_blank" rel="noopener noreferrer">Open the delivered alert ↗</a>`);
    if (Array.isArray(dispatch.attempts) && dispatch.attempts.length) parts.push(`${dispatch.attempts.length} delivery attempt(s) recorded`);
    if (dispatch.webhook_status) parts.push(`webhook: ${escapeHtml(dispatch.webhook_status)}`);
    return `<p class="alert-dispatch">${parts.join(" · ")}</p>`;
  };

  const renderAlertCard = (alert) => {
    const severity = String(alert.severity || "info");
    const resolved = alert.status === "resolved";
    const steps = Array.isArray(alert.review_steps) ? alert.review_steps : [];
    const game = alert.game || {};
    return `<article class="alert-card alert-${escapeHtml(severity)}${resolved ? " alert-resolved" : ""}">
      <div class="alert-card-head">
        <span class="alert-severity">${escapeHtml(SEVERITY_LABEL[severity] || severity)}</span>
        <span class="alert-state">${escapeHtml(resolved ? "Resolved" : "Open")}</span>
        <span class="alert-type">${escapeHtml(String(alert.type || "alert").replaceAll("_", " "))}</span>
        ${game.matchup ? `<span class="alert-matchup">${escapeHtml(game.matchup)}${game.game_date ? ` · ${escapeHtml(formatDate(game.game_date))}` : ""}</span>` : ""}
      </div>
      <h3>${escapeHtml(alert.title || "Untitled alert")}</h3>
      <p>${escapeHtml(alert.summary || "No summary supplied.")}</p>
      <p class="alert-times">Observed by this project: first ${escapeHtml(formatTimestamp(alert.first_seen_at))} · latest ${escapeHtml(formatTimestamp(alert.last_seen_at))} · ${escapeHtml(alert.occurrences ?? "?")} saved observation(s). Poll times are when this project looked, not when any provider changed a value.</p>
      ${renderAlertEvidence(alert)}
      ${renderAlertArithmetic(alert)}
      ${steps.length ? `<details class="alert-steps"><summary>How to check this by hand</summary><ol>${steps.map((step) => `<li>${escapeHtml(step)}</li>`).join("")}</ol></details>` : ""}
      ${resolved && alert.resolution?.note ? `<p class="alert-resolution"><strong>Closure:</strong> ${escapeHtml(alert.resolution.note)}</p>` : ""}
      ${renderAlertDispatch(alert)}
      <p class="alert-disclaimer">${escapeHtml(alert.disclaimer || "Automated candidate detection only; this is not a statement about the NBA's official record.")}</p>
      <p class="alert-id">Alert id ${escapeHtml(alert.id || "unknown")} · ${escapeHtml(alert.verification_status || "unverified")}</p>
    </article>`;
  };

  const renderDetectorStatus = (alertsDoc, feed) => {
    const container = $("#detectorStatus");
    if (!container) return;
    const status = alertsDoc?.detector_status || {};
    const comparison = status.cross_source_comparison || {};
    const arithmetic = status.single_provider_arithmetic_checks || {};
    const revisions = status.final_score_revision_tracking || {};
    const rows = [
      {
        label: "Cross-source score comparison",
        value: comparison.available
          ? `Running against ${(comparison.sources_ok || []).join(", ") || "the reachable sources"}`
          : `Not running — ${comparison.blocked_reason || "fewer than two reachable sources"}`,
        ok: Boolean(comparison.available),
      },
      {
        label: "Post-final score change tracking",
        value: (revisions.sources_tracked || []).length
          ? `Tracking ${revisions.sources_tracked.join(", ")} (${revisions.baselines || 0} baselines)`
          : "No final scores recorded yet",
        ok: (revisions.baselines || 0) > 0,
      },
      {
        label: "Single-provider arithmetic check",
        value: `${arithmetic.games_checked || 0} finished game(s) checked · ${escapeHtml(arithmetic.method || "")}`,
        ok: (arithmetic.games_checked || 0) > 0,
      },
    ];
    container.innerHTML = rows.map((row) => `<div class="detector-row"><span class="detector-light ${row.ok ? "ok" : "off"}"></span><div><strong>${escapeHtml(row.label)}</strong><span>${row.value}</span></div></div>`).join("");
  };

  const renderCoverageGaps = (alertsDoc) => {
    const container = $("#coverageGaps");
    if (!container) return;
    const gaps = Array.isArray(alertsDoc?.coverage_gaps) ? alertsDoc.coverage_gaps : [];
    if (!gaps.length) {
      container.innerHTML = `<p class="muted-text">No coverage gaps recorded yet.</p>`;
      return;
    }
    container.innerHTML = gaps.slice().reverse().map((gap) => `<div class="coverage-gap">
      <strong>${escapeHtml(String(gap.source_key || "source").toUpperCase())} · ${escapeHtml(gap.role || "source")} unavailable</strong>
      <span>${escapeHtml(formatTimestamp(gap.from))} → ${escapeHtml(formatTimestamp(gap.to))}${gap.unavailable_minutes != null ? ` · about ${escapeHtml(gap.unavailable_minutes)} minutes` : ""}</span>
      <span>${escapeHtml(gap.impact || "")}</span>
    </div>`).join("");
  };

  const renderAlerts = (alertsDoc) => {
    const list = $("#alertsList");
    const summary = $("#alertSummary");
    if (!list || !summary) return;
    if (!alertsDoc) {
      summary.className = "status-pill status-warning";
      summary.innerHTML = `<span class="status-light"></span>Alert ledger unavailable`;
      list.innerHTML = `<div class="empty-state"><span class="empty-state-mark" aria-hidden="true">!</span><p>The alert ledger could not be loaded. An unreadable ledger is not evidence that nothing was detected.</p></div>`;
      return;
    }
    const alerts = Array.isArray(alertsDoc.alerts) ? alertsDoc.alerts : [];
    const counts = alertsDoc.counts || {};
    const open = counts.open || 0;
    const bySeverity = counts.open_by_severity || {};
    const pending = counts.pending_dispatch || 0;
    summary.className = `status-pill ${open === 0 ? "status-good" : "status-warning"}`;
    summary.innerHTML = `<span class="status-light"></span>${open === 0 ? "No open alerts" : `${open} open alert${open === 1 ? "" : "s"}`} · ${pending} queued for notification`;
    if (alerts.length === 0) {
      list.innerHTML = `<div class="empty-state"><span class="empty-state-mark" aria-hidden="true">✓</span><p>No alerts have been recorded yet.${alertsDoc.detector_status?.cross_source_comparison?.available ? "" : " Cross-source comparison is not currently able to run, so this is not a clean bill of health."}</p></div>`;
    } else {
      list.innerHTML = alerts.map(renderAlertCard).join("");
    }
    const severityNote = bySeverity.critical || bySeverity.high
      ? ` Open severities: ${["critical", "high", "medium", "info"].filter((key) => bySeverity[key]).map((key) => `${bySeverity[key]} ${key}`).join(", ")}.`
      : "";
    const note = document.createElement("p");
    note.className = "alerts-footnote";
    note.textContent = `${alertsDoc.note || ""}${severityNote}`;
    list.append(note);
    renderDetectorStatus(alertsDoc);
    renderCoverageGaps(alertsDoc);
  };

  const renderLeads = (leads) => {
    const container = $("#leadList");
    if (!Array.isArray(leads) || !leads.length) {
      container.innerHTML = `<div class="empty-state"><span class="empty-state-mark" aria-hidden="true">∅</span><p>No unverified lead records are published.</p></div>`;
      return;
    }
    container.innerHTML = leads.map((lead) => {
      const details = lead.known_details || {};
      const totals = Array.isArray(details.reported_totals) ? details.reported_totals : [];
      const year = details.reported_year;
      const player = details.player_named_in_lead;
      const marker = totals.length
        ? totals.map((value) => `<span>${escapeHtml(value)}</span>`).join('<i aria-hidden="true">↔</i>')
        : `<span>${escapeHtml([year ? `${year} ·` : "", player || "?"].filter(Boolean).join(" "))}</span>`;
      const detailChips = [];
      if (player) detailChips.push(`Player named in lead: ${player}`);
      if (year) detailChips.push(`Year stated in lead: ${year} (unverified)`);
      if (totals.length) detailChips.push(`Reported totals: ${totals.join(" and ")} (unverified)`);
      if (details.game_date) detailChips.push(`Game date: ${details.game_date}`);
      else detailChips.push("Game date not established");
      const teams = Array.isArray(details.teams) ? details.teams : null;
      if (teams?.length) detailChips.push(`Teams: ${teams.join(" / ")}`);
      else detailChips.push("Teams not established");
      const hasSources = Array.isArray(lead.source_ids) && lead.source_ids.length > 0;
      detailChips.push(hasSources ? "Source references supplied; not verified" : "No independently verified source pair supplied");
      const nextEvidence = Array.isArray(lead.next_evidence_needed) ? lead.next_evidence_needed : [];
      return `<article class="lead-card" data-lead="${escapeHtml(lead.id || "")}">
        <div class="lead-number-pair" aria-label="Unverified lead details">${marker}</div>
        <div class="lead-copy">
          <h3 class="lead-title">${escapeHtml(lead.title || "Unverified research lead")}</h3>
          <p>${escapeHtml(lead.origin || "Origin of this lead was not recorded.")}</p>
          <p class="muted-text">${escapeHtml((lead.status || "unverified_lead").replaceAll("_", " "))} · excluded from confirmed-case statistics.</p>
          <div class="lead-details">${detailChips.map((detail) => `<span>${escapeHtml(detail)}</span>`).join("")}</div>
          <p class="lead-next">${escapeHtml(lead.research_note || "No research note supplied.")}</p>
          ${nextEvidence.length ? `<details class="lead-evidence"><summary>Evidence needed to investigate</summary><ul>${nextEvidence.map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ul></details>` : ""}
        </div>
        <span class="lead-mark" aria-hidden="true">?</span>
      </article>`;
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
    renderAlerts(docs.alerts || null);
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
