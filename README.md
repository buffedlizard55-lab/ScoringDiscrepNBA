# NBA Scoring Discrepancies — Verified Research & Live Monitor

> **Session-start rule: read this README first, every time we work on the project.**
> §0 is the founding brief, copied verbatim. §1 states how we read it. §8 states
> exactly what is and is not working today. Build, research, suggest, and
> implement against these; own the outcome end to end.

**GitHub Pages URL:** [`https://buffedlizard55-lab.github.io/ScoringDiscrepNBA/`](https://buffedlizard55-lab.github.io/ScoringDiscrepNBA/).
**Alerting scope, limitations, and verification steps:** [`ALERTING.md`](ALERTING.md).

---

## 0. Founding brief (verbatim — the source of truth)

> ### NBA Scoring Discrepancy Research
>
> Build this project as a comprehensive, continuously updated database and monitoring system for **NBA scoring discrepancies, scoring corrections, and conflicting score data**. The original use case is an incident where one source showed a **213-point final total while another showed 214**, so the system must be capable of finding, documenting, and explaining events like this rather than simply displaying the current final score. Research both historical and current NBA games and identify every verifiable case possible where the official score, play-by-play, box score, scoreboard, official scorer record, or third-party data feed was incorrect, temporarily different, or later corrected.
>
> For every case, capture the **game, date, teams, period/game clock, relevant scoring play, score before and after the event, originally reported value, corrected value, final official value, affected player/team, sources that disagreed, timestamps when available, what changed, when it changed, and the confirmed or suspected cause**. Preserve the original observation and correction rather than overwriting historical data. Most importantly, determine whether the **NBA's official record itself was incorrect** or whether only a secondary source/data provider was incorrect or delayed. Every factual claim must be traceable to a reliable source with a direct link for independent review. Never infer missing information or present an assumption as fact; clearly label anything unverified, disputed, or requiring further investigation.
>
> The system must continuously monitor current NBA games and automatically detect potential discrepancies between authoritative and secondary sources, create an investigation record, and track it through detection, investigation, correction, and resolution. The website should make the entire research collection easy for someone unfamiliar with the project to understand, search, filter, compare, and independently verify. Include historical statistics showing **how often scoring discrepancies/corrections occur, what types are most common, how long they typically last, how often they affect the final score/total, and how rare incidents like the 213/214 discrepancy are**. The final product should allow a new person with no knowledge of this conversation to understand exactly what happened in each case, reproduce the research from the cited evidence, and see the difference between the original data, the correction, and the final official result.
>
> Put this prompt into the repo readme and read it everytime we work on the project as a starting point to make sure we are building what we are aiming for and have a strong base to continue building and improving on making something useful for everyday use. It should solve the problem of having to manually check everything ourselves and having an up to date current feed.
>
> ### Our Core Values
>
> **Maximize P(Win)** — “Maximize the Probability of Winning”: our decision making framework. In every decision, we weigh tradeoffs, assess risk, and choose the path that maximizes the probability that Arena succeeds. We set aside our emotions and make tough decisions in order to maximize P(Win). “Maximize P(Win)” frees us from constraints and clarifies that we must put Arena first.
>
> **Own the Outcome** — We own results end to end — not just our individual slice of the work. When problems arise and we have the means to act, we do so without waiting for permission or assignment. We treat failure and success as signals and use them to improve. At Arena, we stay accountable to the final outcome.
>
> Work line by line verifying from official verified trusted sources, provide links for manual review. There should be no manual input, work on your own to complete tasks. Flag any irregularities for review. No hallucinations.
>
> Verify no hallucinations.
>
> The goal of this project is to get a full list that follow our requirements. No hallucinations. Verify line by line.
>
> ### Site creation
>
> Create a github page for this repo that has clean ui, user friendly, simple and easy to use.
>
> It should be organized and clean. It should include all relevant information in an easy to read format with official verified links as sources for review. Work line by line verify everything no hallucinations.
>
> Go ahead and create a pull request and then merge the pull request onto the main. Make suggestions for what work still needs to be done and any limitations that is in the way of a successful project. It should be worked on in this next session or the next session. Work line by line verify everything no hallucinations.
>
> Run this task through multiple passes.
>
> Pass 1: Implement the task completely and verify the result.
>
> Pass 2: Review your work for bugs, missing requirements, incorrect assumptions, and edge cases. Fix everything you find.
>
> Pass 3: Re-check the entire implementation against the original request. Improve accuracy, reliability, completeness, and code quality. Fix any remaining issues.
>
> Do not stop after the first pass. Each pass must build on the previous one. Before finishing, verify that the final result fully satisfies the original request. Work line by line verify everything no hallucinations.
>
> We should also look into if we can build a alert detection notification system that can detect scoring discrepancies. Tell me the limitations and if it's even possible to do that.

## 1. How we read the brief

1. **A mismatch is not a correction.** Two numbers disagreeing is a *candidate*.
   Only evidence outside the monitor (a league statement, a ruling, a documented
   box-score change) can move a record toward `verified`.
2. **Preserve, never overwrite.** The first observed value, the source that
   showed it, the poll time, and every later value stay in the ledger.
3. **No inference.** Unknown fields stay `null` with an `open_questions[]` entry;
   derived values carry their derivation and are labelled as derived.
4. **State the blind spots.** A source outage is published as a coverage gap; an
   empty alert list is never presented as a clean bill of health
   (see [`ALERTING.md`](ALERTING.md) §3.6).
5. **Label the layer.** Every case records whether the *NBA's official record*
   was wrong, or only a secondary source.

---

## 2. What exists today

| Piece | Location | Status |
|---|---|---|
| Founding brief + operating rules | this README §0/§1 | Verbatim brief retained; read at the start of every session |
| Alert detection + notification system | `monitor/alerts.py`, `monitor/dispatch.py`, `monitor/consistency.py`, `data/alerts.json`, `.github/workflows/pages-and-monitor.yml` | Implemented and offline-verified (76 tests); **first live dispatch has not been observed yet** — see §8 |
| Alerting feasibility, limitations, verification | `ALERTING.md` | New in this session; every claim links to a source or a repository file |
| Current live comparison monitor (NBA liveData vs ESPN + PBP context + final-game box-score arithmetic) | `monitor/`, `data/live-feed.json`, `data/monitor-state.json` | Test-covered; the NBA CDN feed is currently **unreachable from the runner**, so the published rows come from ESPN alone and only the single-provider checks fire today (§8) |
| Current evidence-reviewed dashboard sample (2 confirmed corrections) | `data/reviewed-cases.json` | Source-linked; Melton's exact corrected player total remains disputed (11 vs 12) |
| Unresolved research leads (213/214 and 2021 Kevin Porter Jr.) | `data/leads.json` | Explicitly unverified; excluded from all confirmed counts and statistics |
| Earlier historical collection (12 verified-partial records + 2 unverified stubs) | `data/cases/*.json` → `data/cases.json`; published at `docs/` | Preserved with source and open-question caveats; collection statistics are 12 of 14, never league-wide rates |
| Earlier case schema, validation, and collection statistics | `data/cases-schema.json`, `scripts/validate.py`, `data/stats.json` | Historical collection tools, retained |
| Earlier historical monitor (manual/backfill only) | `scripts/monitor.py`, `monitor/STATE.md`, `data/monitor/current.json` | Snapshot intentionally `not-run` |
| Root dashboard (search, filter, source comparison, alerts, detector status, coverage gaps) | `index.html`, `assets/` | Published by GitHub Pages; smoke-tested against the committed data |
| Historical catalog | `docs/` | Preserved and linked from the root dashboard |
| CI | `.github/workflows/ci.yml`, `.github/workflows/validate.yml` | Python unit tests, JavaScript syntax check, dashboard smoke test, data validation, historical validators + generated-data drift check |
| Pages publishing + five-minute monitor + alert dispatch | `.github/workflows/pages-and-monitor.yml` | Requests `*/5` and re-verifies its own machine-written data before committing (§8) |
| Prior-session store + tools (PR #2) | `data/discrepancies.json`, `src/`, `research/`, `archive/session-7b4d64dc-site/` | Preserved, audit-flagged in `VERIFICATION.md` §6 |

**Originating 213-vs-214 report:** tracked as `0000-00-00-originating-213-vs-214-report`
with status `unverified`. The game is unidentified; it must not be cited as fact
until its checklist is satisfied. The Kevin Porter Jr. 2021 item is likewise a
lead only.

## 3. Quick start

```bash
# Offline gates (standard library only; no network)
python3 -m unittest discover -s tests -v
python3 -m monitor --check-data
node --check assets/app.js
node tests/dashboard-smoke.js

# Preview the dashboard locally
python3 -m http.server 8000

# One live collection cycle (needs network access)
python3 -m monitor --live

# Alerts: inspect the plan, then deliver it (the workflow calls the second form)
python3 -m monitor --dispatch-alerts
python3 -m monitor --dispatch-alerts --apply

# Close an alert by hand after a review, recording the reason
python3 -m monitor --resolve-alert ALR-source_unavailable-nba --note "Endpoint checked from a browser; 403 from the runner only."

# Historical collection tools
python3 scripts/validate.py
python3 scripts/compute_stats.py
python3 scripts/build_site_data.py
python3 scripts/monitor.py --self-test
```

## 4. Repository map

```
├── README.md                   ← persistent brief; read first every session
├── ALERTING.md                 ← alert detection: what works, what cannot, how to verify
├── VERIFICATION.md / ROADMAP.md / REVIEW_PASSES.md ← methods, gaps, multi-pass logs
├── index.html + assets/        ← current dashboard (monitor, alerts, ledger, limits)
├── docs/                       ← preserved historical catalog, linked from the root site
├── data/
│   ├── reviewed-cases.json     ← evidence-reviewed case records
│   ├── leads.json              ← unverified leads, excluded from counts
│   ├── cases/*.json, cases.json, cases-schema.json, stats.json ← historical collection
│   ├── live-feed.json          ← published snapshot + source health + source diagnostics
│   ├── monitor-state.json      ← investigation ledger, per-source final baselines, coverage gaps
│   ├── alerts.json             ← alert ledger (lifecycle, evidence, arithmetic, delivery state)
│   ├── alert-dispatch-log.json ← append-only delivery log (created on first dispatch)
│   └── ...                     ← preserved legacy datasets (see §2 and VERIFICATION.md)
├── monitor/                    ← active stdlib monitor: feeds, engine, consistency, alerts, dispatch
├── scripts/                    ← historical validation, generation, manual monitor tools
├── schemas/case.schema.json    ← schema for the current reviewed-case format
├── tests/                      ← unit, fixture, validation, delivery, and dashboard smoke tests
└── .github/workflows/          ← CI, Pages + monitor + alert dispatch, retained historical jobs
```

## 5. How to add or change a canonical case (no-hallucination workflow)

1. Create/edit `data/cases/<YYYY-MM-DD>-<slug>.json` following `data/cases-schema.json`.
2. Every factual claim needs a `sources[]` entry with a direct `https://` link, publisher, tier,
   and `confirms` text. Unknown fields stay `null` with an `open_questions[]` entry.
3. Rule first on `classification.layer`: was the NBA's official record wrong, or only secondary?
4. Run `python3 scripts/validate.py`; for the current root dashboard edit
   `data/reviewed-cases.json` only after source review and run `python3 -m monitor --check-data`.
5. Run `compute_stats.py` + `build_site_data.py` for the historical catalog, review the diff, open a PR.
6. Never promote `unverified` → `verified-partial` without dated evidence; never use `verified`
   unless ≥2 sources (including a strong tier) corroborate and zero questions remain.
7. Automated alerts are **leads**. To turn one into a case, follow the alert's
   `review_steps`, then write a fresh record; never cite an alert as proof.

## 6. Verification & provenance

- Line-by-line review log and methods: **`VERIFICATION.md`**.
- Each canonical case embeds `reproduce_steps` so a stranger can re-derive it from the cited evidence.
- Statistics carry a machine-readable scope caveat: **collection-only, never league-wide rates**.
- Monitor claims are backed by published artifacts: `source_diagnostics` in
  `data/live-feed.json` (per-attempt profile, outcome, HTTP status), response
  hashes (`ETag`, `Last-Modified`, SHA-256) on observations, and
  `data/alert-dispatch-log.json` for delivery.
- Known gaps and next steps: **`ROADMAP.md`**; multi-pass results: **`REVIEW_PASSES.md`**.

## 7. Prior-session implementation (PR #2) — preserved, not deleted

- **Valuable and credited:** its leads surfaced the verifiable 2017 Robinson III
  correction (now a canonical case) and the league-official “only six upheld
  protests” record. Its per-case verification steps are preserved in
  `VERIFICATION.md` Appendix A.
- **Audit-flagged (do not cite as fact):** `DISC-20241107-CLE-WAS-001` carries a
  wrong year (2024 vs demonstrated 2025); `research/` lists 12 files but ships 1.
  Full findings: `VERIFICATION.md` §6.
- **Tooling:** `src/` needs API keys for live use. The scheduled keyless monitor
  is `monitor/`; `scripts/monitor.py` is retained for deliberate historical/backfill checks.

## 8. Current status, honestly stated

**Monitor.** The scheduled workflow polls the NBA liveData scoreboard and the
ESPN scoreboard, records source health and every fetch attempt, retrieves NBA
play-by-play for mismatching games, and — for finished games it has not yet
checked — retrieves the ESPN summary box score to recompute
`2 × (FGM − 3PM) + 3 × 3PM + FTM` against that same provider's final score. UTC
observation time is the monitor poll time; it is not a provider publication
time.

**Observed blocker (not an assumption).** `cdn.nba.com` is currently
unreachable from the scheduled runner: run
[37616762038](https://github.com/buffedlizard55-lab/ScoringDiscrepNBA/actions/runs/37616762038)
saved `nba: unavailable (HTTPError)` while ESPN was `ok`
([commit `99cae832`](https://github.com/buffedlizard55-lab/ScoringDiscrepNBA/commit/99cae8322239b52486fe26777fa70f33565f3959)).
Independent probes during this review returned an S3 `AccessDenied` document at
`https://cdn.nba.com/robots.txt` and HTTP 500 for the scoreboard object. The
monitor now retries with a browser-like header profile and publishes each
attempt under `source_diagnostics`, so the next run records the exact status
code. Until the primary feed answers, cross-source comparison cannot run and the
dashboard says so instead of implying a clean result.

**Alerts.** Detections become alert records with severity, lifecycle, evidence
links, review steps, and delivery state; critical/high alerts are delivered as
GitHub issues by `python3 -m monitor --dispatch-alerts --apply`, and an optional
webhook (`SCORING_DISCREPANCY_WEBHOOK_URL`) can mirror them. Offline evidence:
76 unit tests (rules, lifecycle, dedupe, arithmetic, delivery with a stubbed
`gh`, webhook receipt, coverage gaps) plus a deterministic end-to-end fixture
run that opens a critical alert and plans its notification while the primary
feed is down. **The first live dispatch has not been observed yet**; do not
describe notifications as proven until `data/alert-dispatch-log.json` contains a
`sent` entry and `data/alerts.json` shows a delivered `issue_url`.

**Single-source operation (fixed this session).** The published game list used
to be built entirely from the primary NBA feed, so that feed failing produced
`games: []` even while ESPN was healthy — and the single-provider arithmetic
check, the detector designed exactly for this situation, silently never ran.
Rows are now the union of every source that answered: each row records which
sources published it, a row with one source is marked `Not compared`, and a
`final_score_internal_inconsistency` alert can still fire. Locks:
`tests/test_runner.py::test_failed_primary_feed_still_publishes_the_reachable_source`
and `::test_single_provider_arithmetic_check_runs_while_nba_feed_is_down`.

**Scheduler reality.** The workflow requests `*/5 * * * *`, but GitHub documents
that scheduled runs can be delayed and that queued jobs may be dropped under
load ([docs](https://docs.github.com/actions/using-workflows/events-that-trigger-workflows)).
During this review the run history showed a single scheduled run in roughly ten
hours. Treat the cadence as best-effort, not real-time. The scheduled job also
now re-runs the unit tests, the JavaScript syntax check, and the dashboard smoke
test after the poll and before committing, because data written with the
repository's `GITHUB_TOKEN` does not start a new workflow run of its own.

**Integrity fix from this session.** GitHub does not start new workflow runs for
pushes made with the repository's `GITHUB_TOKEN`
([docs](https://docs.github.com/en/actions/security-guides/automatic-token-authentication)),
so the previous session's scheduled commit changed machine-written data with no
check ever running on it — the dashboard smoke test was broken on `main` for
that reason. The scheduled job now runs the unit tests, the JavaScript syntax
check, and the dashboard smoke test **after** the poll and **before** committing.

**Historical catalog.** The 12-record collection and its published interface in
`docs/` are preserved unchanged, with their partial status and open questions
visible. Their statistics remain collection-scoped, never league-wide rates.
