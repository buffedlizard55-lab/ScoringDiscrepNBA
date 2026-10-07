"use strict";

const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const root = path.resolve(__dirname, "..");
const html = fs.readFileSync(path.join(root, "index.html"), "utf8");
const script = fs.readFileSync(path.join(root, "assets", "app.js"), "utf8");
const ids = [...html.matchAll(/\bid="([^"]+)"/g)].map((match) => match[1]);
const elements = new Map();

for (const id of ids) {
  elements.set(id, {
    id,
    value: "",
    textContent: "",
    innerHTML: "",
    hidden: false,
    children: [],
    events: {},
    dataset: {},
    className: "",
    classList: { add() {}, remove() {}, contains() { return false; } },
    addEventListener(name, handler) { this.events[name] = handler; },
    append(child) { this.children.push(child); },
  });
}

const selectors = [...script.matchAll(/\$\("#([^"]+)"\)/g)].map((match) => match[1]);
const feed = JSON.parse(fs.readFileSync(path.join(root, "data", "live-feed.json"), "utf8"));
const alertsDoc = JSON.parse(fs.readFileSync(path.join(root, "data", "alerts.json"), "utf8"));
const missing = [...new Set(selectors)].filter((id) => !elements.has(id));
assert.deepEqual(missing, [], "every JavaScript ID selector must exist in index.html");

const context = {
  document: {
    querySelector(selector) { return elements.get(selector.slice(1)) || null; },
    querySelectorAll() { return []; },
    createElement(tag) { return { tag, value: "", textContent: "" }; },
  },
  fetch: async (relativePath) => ({
    ok: true,
    status: 200,
    json: async () => JSON.parse(fs.readFileSync(path.join(root, relativePath), "utf8")),
  }),
  URL,
  Intl,
  console,
  Promise,
  Map,
  Set,
  String,
  Number,
  Array,
  JSON,
};

async function main() {
  vm.runInNewContext(script, context, { filename: "assets/app.js" });
  await new Promise((resolve) => setImmediate(resolve));

  assert.equal(elements.get("heroVerifiedCount").textContent, "2");
  assert.equal(elements.get("heroOpenLeadCount").textContent, "2");
  assert.equal(elements.get("statFinalScore").textContent, "2 / 2");
  assert.match(elements.get("caseList").innerHTML, /Tre Johnson/);
  assert.match(elements.get("caseList").innerHTML, /After corrected entry/);
  assert.match(elements.get("caseList").innerHTML, /Conflicting player-point reports/);
  assert.match(elements.get("caseList").innerHTML, /11 vs 12 · unresolved/);
  assert.match(elements.get("caseList").innerHTML, /No corrected official NBA player-line snapshot was recovered/);
  assert.match(elements.get("caseList").innerHTML, /FanSided/);
  assert.match(elements.get("caseList").innerHTML, /NBA Official post on the Cavaliers–Wizards score correction/);
  assert.match(elements.get("caseList").innerHTML, /official NBA Gamebook/);
  assert.match(elements.get("caseList").innerHTML, /boxscore\/NBA_20251107_CLE@WAS/);
  assert.match(elements.get("typeBreakdown").innerHTML, /made free throw recorded as miss/);
  assert.equal(elements.get("typeFilter").children.length, 1);
  assert.match(html, /href="docs\/index\.html"/, "root dashboard must link to the preserved historical catalog");
  assert.match(
    html,
    /href="https:\/\/github\.com\/buffedlizard55-lab\/ScoringDiscrepNBA\/issues\?q=is%3Aissue\+in%3Atitle\+score-alert"/,
    "monitor alert link must match the generated issue title prefix",
  );
  assert.equal((elements.get("leadList").innerHTML.match(/class="lead-card"/g) || []).length, 2);
  assert.match(elements.get("leadList").innerHTML, /213/);
  assert.match(elements.get("leadList").innerHTML, /214/);
  assert.match(elements.get("leadList").innerHTML, /Kevin Porter Jr\./);
  assert.match(elements.get("leadList").innerHTML, /Year stated in lead: 2021 \(unverified\)/);
  assert.match(elements.get("leadList").innerHTML, /excluded from confirmed-case statistics/);
  // The monitor pill must reflect the committed snapshot, whatever state it is
  // in. The previous hard-coded expectation passed only while no live poll had
  // ever been published, so the first successful scheduled poll silently broke it.
  const expectedPill = feed.status === "healthy"
    ? /Snapshot: feeds available|Review candidate in snapshot/
    : feed.status === "degraded"
      ? /Snapshot: degraded/
      : /Not yet active/;
  assert.match(elements.get("monitorStatus").innerHTML, expectedPill);
  assert.equal(elements.get("investigationsPanel").hidden, true);
  if (feed.last_updated_at) {
    assert.match(elements.get("feedTimestamp").textContent, /Last material snapshot change/);
    assert.match(elements.get("feedTimestamp").textContent, /not a poll heartbeat/);
  }
  assert.match(elements.get("feedNotice").textContent, /observation|not evidence|stale|snapshot|discrepanc/i);
  if (feed.status !== "not_started") {
    assert.match(elements.get("feedNotice").textContent, /does not store a per-poll heartbeat/);
  }
  assert.match(elements.get("sourceHealth").innerHTML, /NBA primary/, "source health chips must render every configured source");
  assert.match(elements.get("sourceHealth").innerHTML, /ESPN secondary/);
  assert.doesNotMatch(elements.get("caseList").innerHTML, /\[object Object\]/);

  // Alert ledger: the committed file must be renderable, and the alert card
  // renderer must show evidence, arithmetic, review steps, and delivery state.
  assert.match(elements.get("alertSummary").innerHTML, /open alert|No open alerts/);
  assert.ok(elements.get("alertsList").innerHTML.length > 0, "the alert ledger must always render an explanation");
  assert.match(elements.get("detectorStatus").innerHTML, /Cross-source score comparison/);
  assert.match(elements.get("detectorStatus").innerHTML, /arithmetic/i);
  assert.match(elements.get("coverageGaps").innerHTML, /coverage gap|No coverage gaps/i);

  const synthetic = {
    ...alertsDoc,
    alerts: [
      {
        id: "ALR-synthetic-smoke-test",
        type: "final_score_internal_inconsistency",
        severity: "critical",
        status: "open",
        title: "Synthetic alert used only by this smoke test",
        summary: "Provider final 115 does not follow from the components it publishes.",
        first_seen_at: "2026-10-07T04:00:00Z",
        last_seen_at: "2026-10-07T04:05:00Z",
        occurrences: 2,
        verification_status: "unverified",
        disclaimer: "Automated candidate detection only.",
        method: "2 * (FGM - 3PM) + 3 * 3PM + FTM",
        game: { game_key: "x", game_id: "1", game_date: "2025-11-07", matchup: "CLE @ WAS" },
        evidence: [
          { label: "Provider game data", url: "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/summary?event=401809511", value: "148-115" },
        ],
        arithmetic: [
          {
            side: "home",
            team: "WSH",
            provider_reported_final: 115,
            derived_points: 114,
            difference: -1,
            components: {
              "fieldGoalsMade-attempted": [41, 91],
              "threePointersMade-attempted": [15, 41],
              "freeThrowsMade-attempted": [17, 23],
            },
          },
        ],
        review_steps: ["Recompute the derived points by hand."],
        dispatch: { status: "pending", reason: "critical severity", issue_url: null, attempts: [] },
      },
    ],
    counts: { open: 1, open_by_severity: { critical: 1 }, pending_dispatch: 1, resolved: 0, total: 1 },
  };
  const syntheticContext = { ...context, fetch: async (relativePath) => ({
    ok: true,
    status: 200,
    json: async () => (relativePath.endsWith("alerts.json")
      ? synthetic
      : JSON.parse(fs.readFileSync(path.join(root, relativePath), "utf8"))),
  }) };
  vm.runInNewContext(script, syntheticContext, { filename: "assets/app.js" });
  await new Promise((resolve) => setImmediate(resolve));
  const ledger = elements.get("alertsList").innerHTML;
  assert.match(ledger, /Synthetic alert used only by this smoke test/);
  assert.match(ledger, /Critical/);
  assert.match(ledger, /Provider final/);
  assert.match(ledger, /114/);
  assert.match(ledger, /Recompute the derived points by hand/);
  assert.match(ledger, /Queued for notification/);
  assert.match(ledger, /Automated candidate detection only/);
  assert.match(elements.get("alertSummary").innerHTML, /1 open alert/);
  assert.doesNotMatch(ledger, /\[object Object\]/);

  console.log(`Dashboard smoke test passed (${new Set(selectors).size} DOM selectors, linked seed records, unresolved player-line conflict, two excluded leads, filters, feed status "${feed.status}", and alert ledger rendering).`);
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
