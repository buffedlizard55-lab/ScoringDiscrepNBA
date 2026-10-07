# NBA Scoring Discrepancies — Verified Research & Live Monitor

> **Session-start rule: read this README first, every time we work on the project.**
> It holds the founding brief, the operating values, and the no-hallucination policy.
> Build, research, suggest, and implement against it. Own the outcome end to end.

**GitHub Pages URL:** [`https://buffedlizard55-lab.github.io/ScoringDiscrepNBA/`](https://buffedlizard55-lab.github.io/ScoringDiscrepNBA/).
The Pages site is deployed from `main`; the most recent scheduled run visible during this review was [run 37616762038](https://github.com/buffedlizard55-lab/ScoringDiscrepNBA/actions/runs/37616762038), which completed but published a **degraded** snapshot at `2026-10-07T11:50:09Z`: ESPN was `ok`, the NBA scoreboard request was unavailable (`HTTPError`), and the game list was empty. A successful workflow job is not proof that both sources were available; an empty degraded feed is not evidence that no games or discrepancies exist. Read the live snapshot and source-health fields before describing current monitoring as healthy. The historical catalog remains available under `docs/` and is included in the Pages artifact.

---

## 1. Founding brief (the mission — do not drift)

### NBA Scoring Discrepancy Research

Build this project as a comprehensive, continuously updated database and monitoring system for
**NBA scoring discrepancies, scoring corrections, and conflicting score data**. The original use
case is an incident where one source showed a **213-point final total while another showed 214**,
so the system must be capable of finding, documenting, and explaining events like this rather than
simply displaying the current final score. Research both historical and current NBA games and
identify every verifiable case possible where the official score, play-by-play, box score,
scoreboard, official scorer record, or third-party data feed was incorrect, temporarily different,
or later corrected.

For every case, capture the **game, date, teams, period/game clock, relevant scoring play, score
before and after the event, originally reported value, corrected value, final official value,
affected player/team, sources that disagreed, timestamps when available, what changed, when it
changed, and the confirmed or suspected cause**. Preserve the original observation and correction
rather than overwriting historical data. Most importantly, determine whether the **NBA's official
record itself was incorrect** or whether only a secondary source/data provider was incorrect or
delayed. Every factual claim must be traceable to a reliable source with a direct link for
independent review. Never infer missing information or present an assumption as fact; clearly label
anything unverified, disputed, or requiring further investigation.

The system must continuously monitor current NBA games and automatically detect potential
discrepancies between authoritative and secondary sources, create an investigation record, and track
it through detection, investigation, correction, and resolution. The website should make the entire
research collection easy for someone unfamiliar with the project to understand, search, filter,
compare, and independently verify. Include historical statistics showing **how often scoring
discrepancies/corrections occur, what types are most common, how long they typically last, how
often they affect the final score/total, and how rare incidents like the 213/214 discrepancy
are**. The final product should allow a new person with no knowledge of this conversation to
understand exactly what happened in each case, reproduce the research from the cited evidence, and
see the difference between the original data, the correction, and the final official result.

It should solve the problem of having to manually check everything ourselves and having an up to
date current feed.

### Core values (kept as a focal point for every decision)

- **Maximize P(Win)** — “Maximize the Probability of Winning”: our decision-making framework. In
  every decision, we weigh tradeoffs, assess risk, and choose the path that maximizes the
  probability of success. We set aside emotion and make tough calls to maximize P(Win).
- **Own the Outcome** — We own results end to end, not just our slice. When problems arise and we
  have the means to act, we act without waiting for permission or assignment. We treat failure and
  success as signals and use them to improve. We stay accountable to the final outcome.

### Operating rules (binding on every session)

1. **Work line by line, verifying from official, verified, trusted sources. Provide links for
   manual review.** No manual input is required from the user; work autonomously to completion.
2. **Flag any irregularities for review. No hallucinations. Verify no hallucinations.**
3. The goal is a **full list that follows the requirements above — verified line by line**.
4. **Run every task through multiple passes:** Pass 1 implement + verify → Pass 2 hunt bugs, gaps,
   wrong assumptions, edge cases, fix all → Pass 3 re-check against this brief, improve accuracy /
   reliability / completeness / quality. Never stop after Pass 1.

---

## 2. What exists today

| Piece | Location | Status |
|---|---|---|
| Earlier historical collection (12 verified-partial records + 2 unverified stubs) | `data/cases/*.json` → `data/cases.json`; also `docs/` | Preserved with source/open-question caveats; collection stats are 12 of 14, not a league-wide rate |
| Current evidence-reviewed dashboard sample (2 confirmed corrections) | `data/reviewed-cases.json` | Source-linked; the exact corrected Melton player total remains disputed (11 vs 12) |
| Current unresolved research leads (213/214 and 2021 Kevin Porter Jr.) | `data/leads.json` | Both explicitly unverified; excluded from confirmed-case counts and statistics |
| Earlier case schema, validation, and collection statistics | `data/cases-schema.json`, `scripts/validate.py`, `data/stats.json` | Historical collection; 12 verified-partial records of 14 total, with explicit coverage caveats |
| Earlier historical monitor (ESPN vs NBA liveData, PBP, quarter totals) | `scripts/monitor.py`, `data/monitor/current.json` | Manual/backfill only; checked-in snapshot is intentionally `not-run` |
| Current live comparison monitor (NBA scoreboard vs ESPN + PBP context) | `monitor/`, `data/live-feed.json`, `data/monitor-state.json` | Test-covered; scheduled poll at `2026-10-07T11:50:09Z` produced `degraded` health (ESPN `ok`, NBA unavailable, empty game list); see the saved snapshot and do not infer no games |
| Root dashboard (search, filter, source comparison) | `index.html`, `assets/` | GitHub Pages is deployed from `main`; latest monitor state is prominently source-health qualified; historical catalog remains linked |
| Persistent candidate notifications | `scripts/github_alerts.js`, `.github/workflows/pages-and-monitor.yml`, `docs/ALERTING.md` | GitHub issue alert implementation is testable offline; creates issues after two consecutive complete score-mismatch comparisons (incomplete polls break the streak) or on a final NBA-feed revision; direct personal push/email is not guaranteed |
| Historical catalog / previous dashboard | `docs/` | Preserved and linked from the root dashboard |
| CI for current and retained historical monitors/dashboard | `.github/workflows/ci.yml`, `.github/workflows/validate.yml` | Current review passed 53 Python unit tests plus both Node smoke tests, data validators, monitor self-test, and JavaScript syntax checks |
| Current Pages publishing and five-minute monitor workflow | `.github/workflows/pages-and-monitor.yml` | Scheduled Actions run at [37616762038](https://github.com/buffedlizard55-lab/ScoringDiscrepNBA/actions/runs/37616762038) completed but NBA source was unavailable; updated workflow publishes each five-minute poll attempt and static snapshot, while committing only material changes |
| Earlier data validation and manual monitor workflows | `.github/workflows/validate.yml`, `.github/workflows/monitor.yml` | Retained; see runbook and limitations below |
| Verification log + methods | `VERIFICATION.md` | Retained; includes the earlier line-by-line log |
| Limitations + roadmap + three-pass review log | `ROADMAP.md`, `REVIEW_PASSES.md` | Retained; all three review passes and PR #4 integration are complete; first scheduled live-feed poll is still unverified |
| Prior-session store + tools (PR #2, preserved as leads) | `data/discrepancies.json`, `src/`, `research/` | Preserved, audit-flagged (see §7) |
| Prior-session site (PR #2, byte-identical archive) | `archive/session-7b4d64dc-site/` | Archived, standalone |

**Originating 213-vs-214 report:** tracked as `0000-00-00-originating-213-vs-214-report`
with status `unverified`. The game is unidentified — it must not be cited as fact until the
checklist in that record is satisfied. The Kevin Porter Jr. 2021 item is likewise a lead only;
its game, stat change, and source history remain unknown.

## 3. Quick start

```bash
# current monitor + dashboard checks (standard library only)
python3 -m unittest discover -s tests -v
python3 -m monitor --check-data
node --check assets/app.js
node --check scripts/github_alerts.js
node tests/dashboard-smoke.js
node tests/github-alerts-smoke.js

# preview the current root dashboard and its linked historical catalog
python3 -m http.server 8000

# one current live collection cycle (needs network access)
python3 -m monitor --live

# earlier historical-data validator and generated collection/site bundle
python3 scripts/validate.py
python3 scripts/compute_stats.py
python3 scripts/build_site_data.py

# earlier monitor offline self-test and manual historical backfill
python3 scripts/monitor.py --self-test
python3 scripts/monitor.py --date 20250115 --lookback 1
```

## 4. Repository map

```
├── README.md                   ← persistent brief; read first every session
├── VERIFICATION.md / ROADMAP.md / REVIEW_PASSES.md ← methods, gaps, and three-pass log
├── index.html + assets/        ← current root dashboard
├── docs/                       ← historical catalog + current investigation and alert runbooks
├── data/
│   ├── reviewed-cases.json     ← current two-case evidence-reviewed dashboard sample
│   ├── leads.json              ← unverified 213/214 + KPJ leads, excluded from case counts
│   ├── cases/*.json            ← earlier per-case historical collection; preserve nulls/open questions
│   ├── cases.json              ← generated aggregate for the earlier docs catalog (do not hand-edit)
│   ├── cases-schema.json       ← earlier case contract; `scripts/validate.py` checks this collection
│   ├── live-feed.json          ← current feed health, poll heartbeat, successful-pair time, and games
│   ├── monitor-state.json      ← current monitor's append-only investigation ledger and baselines
│   ├── statistics.json         ← superseded/audit-flagged manifest; use `stats.json` for the historical collection
│   ├── investigations.json    ← earlier monitor's investigation log
│   ├── stats.json / sources.json ← historical collection-only statistics and source tiers
│   ├── monitor/current.json    ← earlier manual monitor snapshot; current state is intentionally `not-run`
│   └── ...                     ← preserved legacy datasets, see §4 and §7
├── monitor/                    ← current stdlib live monitor + current STATE.md runbook
├── scripts/                    ← historical validators/backfill + GitHub alert and material-diff helpers
├── schemas/case.schema.json    ← schema for the current reviewed-case format
├── tests/                      ← unit, fixture, validation, dashboard, and alert smoke tests
├── archive/session-7b4d64dc-site/ ← PR #2 site + README, preserved byte-for-byte
└── .github/workflows/          ← current CI/Pages monitor plus earlier validation/manual monitor
```

## 5. How to add or change a canonical case (no-hallucination workflow)

1. Create/edit `data/cases/<YYYY-MM-DD>-<slug>.json` following `data/cases-schema.json`.
2. Every factual claim needs a `sources[]` entry with a direct `https://` link, publisher, tier,
   and `confirms` text. Unknown fields stay `null` with an `open_questions[]` entry.
3. Rule first on `classification.layer`: was the NBA's official record wrong, or only secondary?
4. Run `python3 scripts/validate.py` — it fails on placeholder URLs, illegal enums, missing
   questions, and status/source mismatches. For the current root dashboard, edit
   `data/reviewed-cases.json` only after source review and run `python3 -m monitor --check-data`.
5. Run `compute_stats.py` + `build_site_data.py` for the historical catalog, review the diff, open a PR.
6. Never promote `unverified` → `verified-partial` without dated evidence attached; never use
   `verified` unless ≥2 sources (incl. a strong tier) corroborate and zero questions remain.
7. To adopt a PR #2 lead: re-verify every fact independently (the 2017 Robinson III case is the
   template), then write a fresh `data/cases/` record. Never bulk-import `discrepancies.json`.

## 6. Verification & provenance

- Methods, tier definitions, and the line-by-line review log: **`VERIFICATION.md`**.
- Each canonical case embeds `reproduce_steps` so a stranger can re-derive it from the cited evidence.
- Statistics carry a machine-readable scope caveat: **collection-only, never league-wide rates**.
- See **`ROADMAP.md`** for limitations, known gaps, and the suggested next-session plan.

## 7. Prior-session implementation (PR #2) — preserved, not deleted

An earlier session merged a parallel implementation (PR #2). The merge kept it intact:

- **Valuable and credited:** its leads surfaced the verifiable 2017 Robinson III correction
  (now a canonical case) and the league-official “only six upheld protests” record, which
  corrected this project's own USA Today-based “3 since 1952” note. Its per-case verification
  steps are preserved verbatim in `VERIFICATION.md` Appendix A.
- **Audit-flagged (do not cite as fact):** `DISC-20241107-CLE-WAS-001` carries a wrong year
  (2024 vs demonstrated 2025); `research/` lists 12 files but ships 1; legacy stats predate
  the audit. Full findings: `VERIFICATION.md` §6.
- **Tooling:** `src/` needs API keys for live use (per its own README). The current scheduled
  keyless monitor is `monitor/`; `scripts/monitor.py` is retained for deliberate historical/backfill
  checks only. Harmonization notes: `ROADMAP.md` §5.

## 8. Current root dashboard and monitor integration

This Arena review adds the current root dashboard (`index.html` + `assets/`), a separate evidence-reviewed seed file at `data/reviewed-cases.json`, and a tested monitor package in `monitor/`. The root dashboard deliberately uses that two-case seed rather than silently importing or reclassifying the 12-record historical collection in `data/cases.json` and `docs/`. The older collection and its published interface are preserved and linked as the **Historical catalog**. This integration updated the 2024 and 2025 source trails and the two unverified stubs, but did not re-audit every historical case; their partial status and open questions must remain visible. The 2017 Robinson III correction remains a strong source-backed record in that preserved catalog.

The current seed includes the 2024 Warriors–Trail Blazers and 2025 Cavaliers–Wizards postgame free-throw corrections. The 2024 team-score change is confirmed, but Melton’s exact corrected player total remains unresolved: NBC Sports Bay Area and ESPN report/show 11, while FanSided reports 12; no corrected official NBA player-line snapshot was recovered. The 2025 NBA Official X post and NBA Gamebook are linked; The Athletic’s separate “human error” explanation remains attributed to that secondary report. For Tre Johnson, no contemporaneous pre-correction player total was verified; a later CBS component showing 18 is not presented as the game-night value. Both the unidentified 213/214 report and the 2021 Kevin Porter Jr. item remain explicitly unverified leads, with unknown facts left null and both excluded from all confirmed-case counts/statistics. See direct citations in `data/reviewed-cases.json`, `data/leads.json`, and the historical case files.

The current monitor polls the NBA public scoreboard and ESPN scoreboard every five minutes via GitHub Actions, records source health and score comparisons, retrieves NBA play-by-play for mismatches, and stores mismatch/final-feed-revision investigation records without deciding which feed is correct. UTC poll/observation timestamps are not provider publication times. HTTP `ETag`, `Last-Modified`, and SHA-256 response metadata are retained with discrepancy observations when available. ESPN explains that its own feed corrections can be delayed and are distinct from official NBA post-game changes ([ESPN stat-corrections guidance](https://support.espn.com/hc/en-us/articles/360056679592-Stat-corrections)); therefore, a mismatch remains an unverified candidate rather than proof of an NBA record error.

The scheduled workflow now publishes a fresh static artifact each five-minute run so the dashboard can show the latest poll attempt, successful paired-feed time, current clock, and source health even when the score has not changed. `scripts/monitor_diff.py` excludes heartbeat/clock-only values from Git commits; material score, health, or investigation changes are still preserved in repository history. The workflow ignores bot pushes that modify only monitor data to avoid a duplicate Pages deployment. Scheduled tasks and Pages are best-effort, not a real-time service guarantee.

Persistent score mismatches (two consecutive comparable polls; any incomplete poll breaks the streak) and post-final NBA-feed revisions generate deduplicated GitHub issue alerts through the built-in workflow token. Issue creation is best-effort and does not block monitor-state persistence or Pages publishing. Feed convergence updates an alert but is not a human explanation. GitHub issue delivery depends on repository watchers/subscriptions; there is no guaranteed personal email, SMS, or closed-browser push channel. See [`docs/ALERTING.md`](docs/ALERTING.md) and [`docs/INVESTIGATION_WORKFLOW.md`](docs/INVESTIGATION_WORKFLOW.md).

During this review, [scheduled run 37616762038](https://github.com/buffedlizard55-lab/ScoringDiscrepNBA/actions/runs/37616762038) completed at `2026-10-07T11:50:23Z`, but its saved feed state at `2026-10-07T11:50:09Z` was `degraded`: ESPN returned successfully, the NBA scoreboard request returned an opaque `HTTPError`, and no games were listed. The current branch improves HTTP diagnostics and poll heartbeats, but a successful workflow status still does not mean both feeds are healthy. Confirm the next published `last_poll_attempt_at`, `last_successful_comparison_at`, and both source-health values before describing the monitor as operationally healthy. The retained `data/monitor/current.json` is the historical monitor's intentional `not-run` baseline; it is separate from the current feed.

This review passed 53 offline Python unit tests; the dashboard and GitHub alert Node smoke tests; active/historical data validators; the retained monitor self-test; Python compilation; JavaScript syntax checks; and PyYAML parsing of the updated Pages and CI workflow files. Deterministic statistics/site-data generation made no unexpected changes. The public Pages site and historical catalog were previously fetched after deployment, but the code in this branch has not yet been deployed. The unidentified 213/214 and Kevin Porter Jr. leads remain unresolved and excluded from confirmed-case statistics.
