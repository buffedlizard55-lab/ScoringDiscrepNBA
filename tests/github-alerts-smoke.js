"use strict";

const assert = require("node:assert/strict");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const {
  alertTag,
  hasTwoConsecutiveMismatches,
  makeIssueBody,
  makeIssueTitle,
  notifyAlerts,
  selectAlerts,
} = require("../scripts/github_alerts.js");

function observation(at, mismatch, awayScore = 100, homeScore = 98) {
  return {
    observed_at: at,
    game_id: "0022600001",
    game_date: "2026-10-07",
    status: "final",
    score_mismatch: mismatch,
    away_team: { abbreviation: "AAA", name: "Away Club" },
    home_team: { abbreviation: "BBB", name: "Home Club" },
    scores: {
      nba: { away: awayScore, home: homeScore, source_url: "https://nba.example/scoreboard" },
      espn: { away: awayScore, home: homeScore - (mismatch ? 1 : 0), source_url: "https://espn.example/scoreboard" },
    },
    latest_official_scoring_play: {
      period: 4,
      clock: "00:12.0",
      player: "Example Player",
      description: "Makes free throw",
    },
    play_by_play_source_url: "https://nba.example/pbp/0022600001",
  };
}

function mismatchInvestigation(status = "investigating") {
  const first = observation("2026-10-07T04:00:00Z", true, 100, 98);
  const latest = observation("2026-10-07T04:05:00Z", true, 100, 98);
  return {
    id: "0022600001:cross_source_score_mismatch:1",
    game_id: "0022600001",
    game_date: "2026-10-07",
    away_team: first.away_team,
    home_team: first.home_team,
    detection_type: "cross_source_score_mismatch",
    status,
    verification_status: "unverified",
    detected_at: first.observed_at,
    last_seen_at: latest.observed_at,
    resolved_at: status === "resolved" ? "2026-10-07T04:15:00Z" : null,
    observation_count: status === "resolved" ? 4 : 2,
    first_observation: first,
    latest_observation: latest,
    observations: [
      first,
      latest,
      ...(status === "resolved"
        ? [observation("2026-10-07T04:10:00Z", false), observation("2026-10-07T04:15:00Z", false)]
        : []),
    ],
    previous_nba_feed_score: null,
    current_nba_feed_score: null,
    resolution: status === "resolved"
      ? {
          type: "feeds_converged",
          at: "2026-10-07T04:15:00Z",
          note: "The feeds converged; this does not establish cause.",
        }
      : null,
  };
}

function githubStub(existingIssue = null) {
  const calls = { search: [], get: [], create: [], update: [], listComments: [], comments: [] };
  const github = {
    rest: {
      search: {
        issuesAndPullRequests: async (parameters) => {
          calls.search.push(parameters);
          return { data: { items: existingIssue ? [existingIssue] : [] } };
        },
      },
      issues: {
        get: async (parameters) => {
          calls.get.push(parameters);
          return { data: { ...existingIssue, number: parameters.issue_number } };
        },
        create: async (parameters) => {
          calls.create.push(parameters);
          return { data: { number: 17, ...parameters } };
        },
        update: async (parameters) => {
          calls.update.push(parameters);
          if (existingIssue) {
            existingIssue.title = parameters.title;
            existingIssue.body = parameters.body;
          }
          return { data: existingIssue || parameters };
        },
        listComments: async (parameters) => {
          calls.listComments.push(parameters);
          return { data: calls.comments };
        },
        createComment: async (parameters) => {
          calls.comments.push({ body: parameters.body });
          return { data: parameters };
        },
      },
    },
  };
  return { github, calls };
}

async function main() {
  const item = mismatchInvestigation();
  assert.equal(hasTwoConsecutiveMismatches(item), true);
  assert.equal(hasTwoConsecutiveMismatches({ observations: [
    observation("2026-10-07T04:00:00Z", true),
    observation("2026-10-07T04:05:00Z", false),
    observation("2026-10-07T04:10:00Z", true),
  ] }), false, "agreement must break the consecutive-mismatch window");
  assert.equal(hasTwoConsecutiveMismatches({ comparison_checks: [
    { observed_at: "2026-10-07T04:00:00Z", result: "mismatch" },
    { observed_at: "2026-10-07T04:05:00Z", result: "incomplete", reason: "source_unavailable_or_invalid" },
    { observed_at: "2026-10-07T04:10:00Z", result: "mismatch" },
  ] }), false, "a failed, missing, or uncomparable poll must break the alert threshold");
  assert.equal(hasTwoConsecutiveMismatches({ comparison_checks: [
    { observed_at: "2026-10-07T04:10:00Z", result: "incomplete" },
    { observed_at: "2026-10-07T04:15:00Z", result: "mismatch" },
    { observed_at: "2026-10-07T04:20:00Z", result: "mismatch" },
  ] }), true, "two complete mismatch polls after an incomplete poll become alertable");
  assert.equal(selectAlerts({ investigations: [
    { ...item, status: "detected", observations: [item.observations[0]] },
    item,
    { ...item, id: "final-revision", detection_type: "nba_final_feed_revision" },
    { ...item, id: "feed-outage", detection_type: "feed_unavailable" },
  ] }).length, 2, "only persistent score mismatches and final-feed revisions are alertable");

  const body = makeIssueBody(item);
  const finalRevision = {
    ...item,
    id: "0022600001:nba_final_feed_revision:1",
    detection_type: "nba_final_feed_revision",
    status: "change_observed_unverified",
    previous_nba_feed_score: { away: 100, home: 98 },
    current_nba_feed_score: { away: 101, home: 98 },
  };
  assert.match(makeIssueBody(finalRevision), /Prior NBA-feed final value/);
  assert.match(makeIssueBody(finalRevision), /New NBA-feed final value/);
  assert.match(body, /Unverified source observation/);
  assert.match(body, /two consecutive saved polls/);
  assert.match(body, /not causal evidence/);
  assert.match(body, /https:\/\/nba\.example\/scoreboard/);
  assert.doesNotMatch(body, /javascript:/);
  const mentionTest = mismatchInvestigation();
  mentionTest.latest_observation.latest_official_scoring_play = { description: "@someone score bug" };
  assert.doesNotMatch(makeIssueBody(mentionTest), /@someone/, "feed text must not create an unintended GitHub mention");
  mentionTest.latest_observation.latest_official_scoring_play.description = "<img src=x onerror=alert(1)>";
  assert.doesNotMatch(makeIssueBody(mentionTest), /<img/, "feed text must not inject raw HTML into issue content");
  assert.match(alertTag(item), /^SDNBAALERT[0-9a-f]{16}$/);

  const context = { repo: { owner: "example-owner", repo: "example-repo" } };
  const transient = { ...item, id: "transient", observations: [item.observations[0]], status: "detected" };
  const quiet = githubStub();
  const quietResult = await notifyAlerts({
    github: quiet.github,
    context,
    state: { investigations: [transient] },
    logger: { info() {} },
  });
  assert.equal(quietResult.eligible, 0);
  assert.equal(quiet.calls.search.length, 0, "transient one-poll differences do not create notifications");

  const created = githubStub();
  const createdResult = await notifyAlerts({
    github: created.github,
    context,
    state: { investigations: [item] },
    logger: { info() {} },
  });
  assert.equal(createdResult.created, 1);
  assert.equal(item.notification.issue_number, 17, "the issue number is retained to avoid repeated repository searches");
  assert.match(created.calls.create[0].title, /SDNBAALERT/);
  assert.match(created.calls.create[0].body, /does not determine which feed is correct/);

  const unchangedPass = githubStub();
  const unchangedResult = await notifyAlerts({
    github: unchangedPass.github,
    context,
    state: { investigations: [item] },
    logger: { info() {} },
  });
  assert.equal(unchangedResult.eligible, 1);
  assert.equal(unchangedPass.calls.search.length, 0, "saved issue metadata prevents repeated search calls");
  assert.equal(unchangedPass.calls.get.length, 0, "unchanged alerts need no repository API request");

  const currentIssue = {
    number: 17,
    title: created.calls.create[0].title,
    body: created.calls.create[0].body,
    state: "open",
  };
  item.latest_observation.scores.nba.away = 101;
  const refreshedStub = githubStub(currentIssue);
  const refreshedResult = await notifyAlerts({
    github: refreshedStub.github,
    context,
    state: { investigations: [item] },
    logger: { info() {} },
  });
  assert.equal(refreshedResult.updated, 1, "a material score change refreshes the linked issue");
  assert.equal(refreshedStub.calls.get.length, 1);
  assert.equal(refreshedStub.calls.search.length, 0);

  const existing = {
    number: 17,
    title: makeIssueTitle(item),
    body,
    state: "open",
  };
  const resumed = { ...mismatchInvestigation("resolved") };
  const resolved = githubStub(existing);
  const result = await notifyAlerts({
    github: resolved.github,
    context,
    state: { investigations: [resumed] },
    logger: { info() {} },
  });
  assert.equal(result.updated, 1);
  assert.equal(resolved.calls.comments.length, 1);
  assert.match(resolved.calls.comments[0].body, /operational convergence only/);
  assert.equal(existing.state, "open", "feed convergence must not auto-close a human review issue");
  assert.match(existing.body, /<!-- sdnba-alert-status:resolved -->/);

  const closedCandidate = mismatchInvestigation();
  const humanClosed = {
    number: 18,
    title: makeIssueTitle(closedCandidate),
    body: makeIssueBody(closedCandidate),
    state: "closed",
  };
  const closedStub = githubStub(humanClosed);
  const closedResult = await notifyAlerts({
    github: closedStub.github,
    context,
    state: { investigations: [closedCandidate] },
    logger: { info() {} },
  });
  assert.equal(closedResult.skippedClosed, 1);
  assert.equal(closedStub.calls.update.length, 0, "the monitor must respect a human-closed issue");
  assert.equal(closedStub.calls.create.length, 0);

  const corruptedReference = mismatchInvestigation();
  corruptedReference.notification = {
    issue_number: 5,
    last_body_sha256: "outdated-hash",
    last_status: "investigating",
  };
  const unrelatedIssue = { number: 5, title: "unrelated issue", body: "unrelated body", state: "open" };
  const safeReferenceStub = githubStub(unrelatedIssue);
  const safeReferenceResult = await notifyAlerts({
    github: safeReferenceStub.github,
    context,
    state: { investigations: [corruptedReference] },
    logger: { info() {} },
  });
  assert.equal(safeReferenceResult.created, 1);
  assert.equal(safeReferenceStub.calls.update.length, 0, "a stale issue number must never overwrite an unrelated issue");

  // A repeated scheduled run sees the saved resolved status and the comment marker,
  // so it does not send a duplicate resolution notification.
  delete resumed.notification;
  const repeated = githubStub(existing);
  repeated.calls.comments.push(...resolved.calls.comments);
  const repeatedResult = await notifyAlerts({
    github: repeated.github,
    context,
    state: { investigations: [resumed] },
    logger: { info() {} },
  });
  assert.equal(repeatedResult.updated, 0);
  assert.equal(repeated.calls.comments.length, 1);

  const temporaryDirectory = fs.mkdtempSync(path.join(os.tmpdir(), "scoring-alert-test-"));
  try {
    const statePath = path.join(temporaryDirectory, "data", "monitor-state.json");
    fs.mkdirSync(path.dirname(statePath), { recursive: true });
    fs.writeFileSync(statePath, JSON.stringify({ investigations: [mismatchInvestigation()] }), "utf8");
    const persistedStub = githubStub();
    const persistedResult = await notifyAlerts({
      github: persistedStub.github,
      context,
      statePath,
      logger: { info() {} },
    });
    const writtenState = JSON.parse(fs.readFileSync(statePath, "utf8"));
    assert.equal(persistedResult.created, 1);
    assert.equal(writtenState.investigations[0].notification.issue_number, 17);
    assert.equal(writtenState.investigations[0].notification.channel, "github-issue");
  } finally {
    fs.rmSync(temporaryDirectory, { recursive: true, force: true });
  }

  console.log("GitHub alert smoke test passed (persistence threshold, false-positive suppression, durable deduplication, human closure, and non-causal resolution notices).");
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
