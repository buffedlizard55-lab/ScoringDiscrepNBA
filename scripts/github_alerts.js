"use strict";

const crypto = require("node:crypto");
const fs = require("node:fs");
const path = require("node:path");

const STATE_PATH = path.join(process.cwd(), "data", "monitor-state.json");
const REPOSITORY_URL = "https://github.com/buffedlizard55-lab/ScoringDiscrepNBA";
const DASHBOARD_URL = "https://buffedlizard55-lab.github.io/ScoringDiscrepNBA/#monitor";
const ALERTS_URL = `${REPOSITORY_URL}/issues?q=is%3Aissue+in%3Atitle+SDNBAALERT`;

function readMonitorState(filePath = STATE_PATH) {
  const parsed = JSON.parse(fs.readFileSync(filePath, "utf8"));
  if (!parsed || typeof parsed !== "object" || !Array.isArray(parsed.investigations)) {
    throw new Error("data/monitor-state.json must contain an investigations array");
  }
  return parsed;
}

function sortKeysDeep(value) {
  if (Array.isArray(value)) return value.map(sortKeysDeep);
  if (!value || typeof value !== "object") return value;
  return Object.fromEntries(
    Object.keys(value).sort().map((key) => [key, sortKeysDeep(value[key])])
  );
}

function writeMonitorState(filePath, state) {
  const destination = path.resolve(filePath);
  const temporary = `${destination}.tmp-${process.pid}`;
  fs.writeFileSync(temporary, `${JSON.stringify(sortKeysDeep(state), null, 2)}\n`, "utf8");
  fs.renameSync(temporary, destination);
}

function sha256(value) {
  return crypto.createHash("sha256").update(String(value)).digest("hex");
}

function hasTwoConsecutiveMismatches(item) {
  let consecutive = 0;
  const history = Array.isArray(item.comparison_checks)
    ? item.comparison_checks
    : Array.isArray(item.observations) ? item.observations : [];
  for (const observation of history) {
    if (observation?.result === "mismatch" || observation?.score_mismatch === true) {
      consecutive += 1;
      if (consecutive >= 2) return true;
    } else {
      // A matching poll, incomplete comparison, or unknown row breaks the window.
      consecutive = 0;
    }
  }
  return false;
}

function selectAlerts(state) {
  const investigations = Array.isArray(state?.investigations) ? state.investigations : [];
  return investigations.filter((item) => {
    if (!item || typeof item !== "object") return false;
    if (item.detection_type === "nba_final_feed_revision") return true;
    return item.detection_type === "cross_source_score_mismatch" && hasTwoConsecutiveMismatches(item);
  });
}

function alertTag(item) {
  const identifier = String(item?.id || "unknown-investigation");
  const digest = crypto.createHash("sha256").update(identifier).digest("hex").slice(0, 16);
  return `SDNBAALERT${digest}`;
}

function oneLine(value, fallback = "not established", maxLength = 300) {
  if (value === null || value === undefined || value === "") return fallback;
  return String(value).replace(/[\r\n\t]+/g, " ").trim().slice(0, maxLength) || fallback;
}

function escapeMarkdown(value, fallback) {
  return oneLine(value, fallback)
    .replace(/[\\`*_{}\[\]()#+\-.!|]/g, "\\$&")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/@/g, "@\u200b");
}

function scoreText(score) {
  if (!score || !Number.isInteger(score.away) || !Number.isInteger(score.home)) {
    return "not available";
  }
  return `${score.away}–${score.home} (combined total ${score.away + score.home})`;
}

function scoreLink(label, rawUrl) {
  if (typeof rawUrl !== "string") return null;
  try {
    const url = new URL(rawUrl);
    if (url.protocol !== "https:") return null;
    const safeUrl = url.href.replace(/[<>]/g, "");
    return `[${escapeMarkdown(label)}](<${safeUrl}>)`;
  } catch {
    return null;
  }
}

function teamsText(item) {
  const away = item?.away_team?.abbreviation || item?.away_team?.name || "Away team";
  const home = item?.home_team?.abbreviation || item?.home_team?.name || "Home team";
  return `${oneLine(away, "Away team", 40)} @ ${oneLine(home, "Home team", 40)}`;
}

function makeIssueTitle(item) {
  const tag = alertTag(item);
  const kind = item.detection_type === "nba_final_feed_revision"
    ? "NBA final-feed revision"
    : "persistent score-feed mismatch";
  const date = oneLine(item.game_date, "date unknown", 20);
  return `${tag} · ${teamsText(item)} · ${kind} · ${date}`.slice(0, 240);
}

function makeIssueBody(item) {
  const tag = alertTag(item);
  const first = item.first_observation || {};
  const latest = item.latest_observation || first;
  const scores = latest.scores || {};
  const status = oneLine(item.status, "detected", 60);
  const nbaScore = scores.nba || {};
  const espnScore = scores.espn || {};
  const firstAt = oneLine(first.observed_at, "not recorded", 40);
  const gameDate = oneLine(item.game_date || latest.game_date, "not established", 20);
  const lines = [
    `<!-- sdnba-alert:${tag} -->`,
    `<!-- sdnba-alert-status:${status} -->`,
    "## Automated NBA scoring-monitor alert",
    "",
    "> **Unverified source observation.** This alert does not determine which feed is correct and does not establish that the NBA's official record was wrong.",
    "",
    `- **Game:** ${escapeMarkdown(teamsText(item))} · ${escapeMarkdown(gameDate)}`,
    `- **Monitor status:** ${escapeMarkdown(status)} · unverified`,
    `- **First observed by this monitor (UTC):** ${escapeMarkdown(firstAt)}`,
    "- **Latest values in the saved monitor observation (not provider publication times):**",
    `  - NBA scoreboard feed: ${escapeMarkdown(scoreText(nbaScore))}`,
    `  - ESPN scoreboard feed: ${escapeMarkdown(scoreText(espnScore))}`,
  ];

  if (item.detection_type === "nba_final_feed_revision") {
    lines.push(
      `- **Prior NBA-feed final value:** ${escapeMarkdown(scoreText(item.previous_nba_feed_score))}`,
      `- **New NBA-feed final value:** ${escapeMarkdown(scoreText(item.current_nba_feed_score))}`,
      "- **Meaning:** the monitored NBA feed changed after a final score was first saved; the exact internal record-change time and cause are not established by this observation."
    );
  } else {
    lines.push(
      "- **Meaning:** two consecutive saved polls showed different NBA and ESPN scoreboard values. A persistent mismatch is an investigation candidate, not a confirmed scoring correction."
    );
  }

  const play = latest.latest_official_scoring_play;
  if (play && typeof play === "object") {
    const playDetails = [
      play.period ? `period ${play.period}` : null,
      play.clock ? `clock ${play.clock}` : null,
      play.player || null,
      play.description || null,
    ].filter(Boolean).map((value) => escapeMarkdown(value)).join(" · ");
    if (playDetails) lines.push(`- **Latest NBA play-by-play context (not causal evidence):** ${playDetails}`);
  }

  const links = [
    scoreLink("NBA scoreboard response", nbaScore.source_url),
    scoreLink("ESPN scoreboard response", espnScore.source_url),
    scoreLink("NBA play-by-play response", latest.play_by_play_source_url),
    scoreLink("Published monitor dashboard", DASHBOARD_URL),
    scoreLink("Saved monitor investigation ledger", `${REPOSITORY_URL}/blob/main/data/monitor-state.json`),
    scoreLink("All monitor alert issues", ALERTS_URL),
  ].filter(Boolean);
  lines.push("", "### Review links", "", ...links.map((link) => `- ${link}`));
  if (item.status === "resolved") {
    lines.push(
      "",
      "**Current monitor state:** the two scoreboard feeds converged for two consecutive polls. This closes the observed mismatch window only; it does not prove which earlier value was correct, explain the difference, or confirm an NBA-record correction. Keep this issue open until a reviewer records an evidence-based disposition."
    );
  }
  lines.push(
    "",
    "This issue is created and refreshed by the scheduled monitor. Preserve the original observations; do not promote this candidate into a verified research case without linked, independent evidence."
  );
  return lines.join("\n");
}

function resolutionComment(item, tag) {
  const at = oneLine(item.resolved_at || item.resolution?.at, "time not recorded", 40);
  return [
    `<!-- sdnba-alert-resolution:${tag} -->`,
    `The monitor observed feed agreement at ${escapeMarkdown(at)} after the mismatch window. This is operational convergence only; it does **not** establish which earlier value was correct, why the feeds differed, or whether the NBA record changed. Please review the linked observations before closing this issue.`,
  ].join("\n");
}

async function findAlertIssue(github, owner, repo, tag) {
  const result = await github.rest.search.issuesAndPullRequests({
    q: `repo:${owner}/${repo} is:issue in:title ${tag}`,
    per_page: 10,
  });
  return (result.data.items || []).find((issue) =>
    !issue.pull_request && typeof issue.title === "string" && issue.title.includes(tag)
  ) || null;
}

async function notifyAlerts({ github, context, state, statePath = STATE_PATH, logger = console }) {
  if (!github?.rest?.search?.issuesAndPullRequests || !github?.rest?.issues) {
    throw new Error("GitHub REST client with issue and search APIs is required");
  }
  const owner = context?.repo?.owner;
  const repo = context?.repo?.repo;
  if (!owner || !repo) throw new Error("GitHub repository context is missing");

  // The workflow lets this function read/write the checked-out monitor ledger.
  // Tests may pass an in-memory state object and never touch repository files.
  const shouldPersist = state === undefined;
  const workingState = state || readMonitorState(statePath);
  const alerts = selectAlerts(workingState);
  let created = 0;
  let updated = 0;
  let skippedClosed = 0;
  let metadataChanged = false;

  for (const item of alerts) {
    const tag = alertTag(item);
    const title = makeIssueTitle(item);
    const body = makeIssueBody(item);
    const bodyHash = sha256(body);
    const currentStatus = oneLine(item.status, "detected", 60);
    const previousNotification = item.notification || {};

    if (previousNotification.human_closed === true) {
      skippedClosed += 1;
      continue;
    }
    // Once the current issue text is synced, a five-minute run needs no search
    // or API call. This also prevents historical resolved items from consuming
    // GitHub search quota forever.
    if (previousNotification.issue_number
        && previousNotification.last_body_sha256 === bodyHash
        && previousNotification.last_status === currentStatus) {
      continue;
    }

    let existing = null;
    if (Number.isInteger(previousNotification.issue_number)) {
      try {
        const response = await github.rest.issues.get({
          owner,
          repo,
          issue_number: previousNotification.issue_number,
        });
        existing = response.data;
      } catch (error) {
        if (error?.status !== 404) throw error;
        // Recover if a prior issue was deleted; the stable title tag prevents
        // duplication if search can still find a retained/renamed issue.
        item.notification = undefined;
      }
    }
    if (!existing) existing = await findAlertIssue(github, owner, repo, tag);
    const bodyMarker = `<!-- sdnba-alert:${tag} -->`;
    if (existing
        && !existing.title?.includes(tag)
        && !existing.body?.includes(bodyMarker)) {
      logger.info?.(`Stored issue reference for ${tag} did not match its stable marker; refusing to edit it.`);
      item.notification = undefined;
      existing = await findAlertIssue(github, owner, repo, tag);
    }

    if (!existing) {
      const response = await github.rest.issues.create({ owner, repo, title, body });
      const number = response.data.number;
      item.notification = {
        channel: "github-issue",
        issue_number: number,
        tag,
        last_body_sha256: bodyHash,
        last_status: currentStatus,
      };
      metadataChanged = true;
      created += 1;
      logger.info?.(`Opened monitor alert issue #${number} (${tag}).`);
      continue;
    }

    // Respect a human's explicit closure; never reopen or edit a dismissed alert.
    if (existing.state === "closed") {
      item.notification = {
        channel: "github-issue",
        issue_number: existing.number,
        tag,
        last_body_sha256: bodyHash,
        last_status: currentStatus,
        human_closed: true,
      };
      metadataChanged = true;
      skippedClosed += 1;
      logger.info?.(`Alert ${tag} is already closed; leaving the human disposition unchanged.`);
      continue;
    }

    const previousStatus = existing.body?.match(/<!-- sdnba-alert-status:([^>]+) -->/)?.[1]
      || previousNotification.last_status
      || null;
    if (item.status === "resolved" && previousStatus !== "resolved") {
      const comments = await github.rest.issues.listComments({ owner, repo, issue_number: existing.number, per_page: 100 });
      const marker = `<!-- sdnba-alert-resolution:${tag} -->`;
      const alreadyCommented = (comments.data || []).some((comment) => comment.body?.includes(marker));
      if (!alreadyCommented) {
        await github.rest.issues.createComment({
          owner,
          repo,
          issue_number: existing.number,
          body: resolutionComment(item, tag),
        });
      }
    }

    if (existing.title !== title || existing.body !== body) {
      await github.rest.issues.update({
        owner,
        repo,
        issue_number: existing.number,
        title,
        body,
      });
      updated += 1;
    }
    const nextNotification = {
      channel: "github-issue",
      issue_number: existing.number,
      tag,
      last_body_sha256: bodyHash,
      last_status: currentStatus,
    };
    if (JSON.stringify(previousNotification) !== JSON.stringify(nextNotification)) {
      item.notification = nextNotification;
      metadataChanged = true;
    }
    if (previousStatus !== currentStatus) {
      logger.info?.(`Refreshed monitor alert issue #${existing.number} (${tag}): ${currentStatus}.`);
    }
  }

  if (shouldPersist && metadataChanged) writeMonitorState(statePath, workingState);
  logger.info?.(`Monitor alert pass complete: ${created} created, ${updated} refreshed, ${skippedClosed} human-closed issue(s) left unchanged.`);
  return { created, updated, skippedClosed, eligible: alerts.length, metadataChanged };
}

module.exports = {
  alertTag,
  hasTwoConsecutiveMismatches,
  makeIssueBody,
  makeIssueTitle,
  notifyAlerts,
  readMonitorState,
  selectAlerts,
};
