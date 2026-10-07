"use strict";

const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const root = path.resolve(__dirname, "..");
const html = fs.readFileSync(path.join(root, "index.html"), "utf8");
const script = fs.readFileSync(path.join(root, "assets", "app.js"), "utf8");
const savedFeed = JSON.parse(fs.readFileSync(path.join(root, "data", "live-feed.json"), "utf8"));
const savedState = JSON.parse(fs.readFileSync(path.join(root, "data", "monitor-state.json"), "utf8"));
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
  assert.equal((elements.get("leadList").innerHTML.match(/class="lead-card"/g) || []).length, 2);
  assert.match(elements.get("leadList").innerHTML, /213/);
  assert.match(elements.get("leadList").innerHTML, /214/);
  assert.match(elements.get("leadList").innerHTML, /Kevin Porter Jr\./);
  assert.match(elements.get("leadList").innerHTML, /Year stated in lead: 2021 \(unverified\)/);
  assert.match(elements.get("leadList").innerHTML, /excluded from confirmed-case statistics/);
  const attemptTime = Date.parse(savedFeed.last_poll_attempt_at || "");
  const hasPollHeartbeat = Number.isFinite(attemptTime);
  const pollIsStale = hasPollHeartbeat && Date.now() - attemptTime > 15 * 60 * 1000;
  const pollTimeIsFuture = hasPollHeartbeat && attemptTime - Date.now() > 60 * 1000;
  const expectedStatusLabel = pollIsStale
    ? savedFeed.status === "degraded" ? "Feed degraded · stale" : "Snapshot stale"
    : pollTimeIsFuture
      ? "Poll time anomaly"
      : savedFeed.status === "healthy" && !hasPollHeartbeat
        ? "Freshness unknown"
        : {
            healthy: savedFeed.games?.some((game) => game.score_mismatch === true)
              || Number(savedFeed.active_investigation_count || 0) > 0 ? "Review candidate" : "Feeds available",
            degraded: "Feed degraded",
            not_started: "Not yet active",
          }[savedFeed.status] || "Not yet active";
  assert.match(elements.get("monitorStatus").innerHTML, new RegExp(expectedStatusLabel));
  if (pollIsStale) {
    assert.match(elements.get("feedNotice").textContent, /more than 15 minutes old/);
  } else if (!hasPollHeartbeat && savedFeed.status !== "not_started") {
    assert.match(elements.get("feedNotice").textContent, /freshness cannot be verified/);
  }
  assert.match(elements.get("sourceHealth").innerHTML, /NBA primary/);
  assert.match(elements.get("sourceHealth").innerHTML, /ESPN secondary/);
  if (savedFeed.last_poll_attempt_at) {
    assert.match(elements.get("feedTimestamp").textContent, /Latest poll attempt/);
  } else {
    assert.match(elements.get("feedTimestamp").textContent, /Heartbeat not recorded|No poll-attempt timestamp/);
  }
  if (savedFeed.last_successful_comparison_at) {
    assert.match(elements.get("feedTimestamp").textContent, /Last poll with both feeds parsed/);
  } else {
    assert.match(elements.get("feedTimestamp").textContent, /No both-feed successful-poll time/);
  }
  assert.equal(
    elements.get("investigationsPanel").hidden,
    !Array.isArray(savedState.investigations) || savedState.investigations.length === 0,
    "the monitor investigation panel must reflect the checked-in investigation ledger",
  );
  assert.doesNotMatch(elements.get("caseList").innerHTML, /\[object Object\]/);

  console.log(`Dashboard smoke test passed (${new Set(selectors).size} DOM selectors, linked seed records, unresolved player-line conflict, two excluded leads, filters, and published monitor status: ${savedFeed.status}).`);
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
