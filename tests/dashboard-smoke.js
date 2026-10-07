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
  assert.equal(elements.get("statFinalScore").textContent, "2 / 2");
  assert.match(elements.get("caseList").innerHTML, /Tre Johnson/);
  assert.match(elements.get("caseList").innerHTML, /After corrected entry/);
  assert.match(elements.get("caseList").innerHTML, /Player points · reported → corrected/);
  assert.match(elements.get("caseList").innerHTML, /official NBA Gamebook/);
  assert.match(elements.get("caseList").innerHTML, /boxscore\/NBA_20251107_CLE@WAS/);
  assert.match(elements.get("typeBreakdown").innerHTML, /made free throw recorded as miss/);
  assert.equal(elements.get("typeFilter").children.length, 1);
  assert.match(html, /href="docs\/index\.html"/, "root dashboard must link to the preserved historical catalog");
  assert.match(elements.get("leadDetails").innerHTML, /not counted/);
  assert.match(elements.get("monitorStatus").innerHTML, /Not yet active/);
  assert.equal(elements.get("investigationsPanel").hidden, true);
  assert.doesNotMatch(elements.get("caseList").innerHTML, /\[object Object\]/);

  console.log(`Dashboard smoke test passed (${new Set(selectors).size} DOM selectors, linked seed records, filters, lead, and not-started monitor state).`);
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
