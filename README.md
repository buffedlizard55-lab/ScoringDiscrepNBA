# NBA Scoring Discrepancies — Verified Research & Live Monitor

> **Session-start rule: read this README first, every time we work on the project.**
> It holds the founding brief, the operating values, and the no-hallucination policy.
> Build, research, suggest, and implement against it. Own the outcome end to end.

**GitHub Pages URL:** `https://buffedlizard55-lab.github.io/ScoringDiscrepNBA/`.
The `pages-and-monitor.yml` deployment for merged commit `4e3360a` completed successfully (workflow run [37575179479](https://github.com/buffedlizard55-lab/ScoringDiscrepNBA/actions/runs/37575179479); Pages API status: `built`). The sandbox did not fetch the external page itself. The earlier historical catalog remains available under `docs/` and is copied into the same Pages artifact.

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
| Earlier historical collection (12 partial case records + 1 unverified stub) | `data/cases/*.json` → `data/cases.json`; also `docs/` | Preserved; not re-audited in this pass |
| Current evidence-reviewed dashboard sample (2 confirmed corrections) | `data/reviewed-cases.json` | Source-linked; intentionally a small sample |
| Current unresolved 213/214 lead | `data/leads.json` | Unidentified; excluded from confirmed-case counts |
| Earlier case schema, validation, and collection statistics | `data/cases-schema.json`, `scripts/validate.py`, `data/stats.json` | Retained with source caveats |
| Earlier historical monitor (ESPN vs NBA liveData, PBP, quarter totals) | `scripts/monitor.py`, `monitor/STATE.md` | Retained for manual/backfill use; its old schedule is disabled |
| Current live comparison monitor (NBA scoreboard vs ESPN + PBP context) | `monitor/`, `data/live-feed.json`, `data/monitor-state.json` | Test-covered; no successful live run observed yet |
| Current root dashboard (search, filter, source comparison) | `index.html`, `assets/` | Pages workflow succeeded after PR #5; external page content was not fetched in this sandbox |
| Historical catalog / previous dashboard | `docs/` | Preserved and linked from the root dashboard |
| New CI for the current monitor/dashboard | `.github/workflows/ci.yml` | 22 offline tests plus data and JavaScript checks |
| Current Pages publishing and five-minute monitor workflow | `.github/workflows/pages-and-monitor.yml` | Configured; requires successful run and Pages permissions |
| Earlier data validation and manual monitor workflows | `.github/workflows/validate.yml`, `.github/workflows/monitor.yml` | Retained; see runbook and limitations below |
| Verification log + methods | `VERIFICATION.md` | Retained; includes the earlier line-by-line log |
| Limitations + roadmap | `ROADMAP.md` | Retained |
| Prior-session store + tools (PR #2, preserved as leads) | `data/discrepancies.json`, `src/`, `research/` | Preserved, audit-flagged (see §7) |
| Prior-session site (PR #2, byte-identical archive) | `archive/session-7b4d64dc-site/` | Archived, standalone |

**Originating 213-vs-214 report:** tracked as `0000-00-00-originating-213-vs-214-report`
with status `unverified`. The game is unidentified — it must not be cited as fact until the
checklist in that record is satisfied.

## 3. Quick start

```bash
# current monitor + dashboard checks (standard library only)
python3 -m unittest discover -s tests -v
python3 -m monitor --check-data
node --check assets/app.js
node tests/dashboard-smoke.js

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
├── VERIFICATION.md / ROADMAP.md ← earlier research log, methods, limitations, and next work
├── index.html + assets/        ← current root dashboard
├── docs/                       ← preserved earlier historical catalog, linked from the root site
├── data/
│   ├── reviewed-cases.json     ← current two-case evidence-reviewed dashboard sample
│   ├── leads.json              ← unresolved 213/214 lead, excluded from case counts
│   ├── cases/*.json            ← earlier per-case historical collection; preserve nulls/open questions
│   ├── cases.json              ← generated aggregate for the earlier docs catalog (do not hand-edit)
│   ├── cases-schema.json       ← earlier case contract; `scripts/validate.py` checks this collection
│   ├── live-feed.json          ← current monitor's published scoreboard snapshot
│   ├── monitor-state.json      ← current monitor's append-only investigation ledger and baselines
│   ├── investigations.json    ← earlier monitor's investigation log
│   ├── stats.json / sources.json ← earlier collection-only statistics and source tiers
│   └── ...                     ← preserved legacy datasets, see §4 and §7
├── monitor/                    ← current stdlib monitor package + earlier STATE.md runbook
├── scripts/                    ← earlier validation, data generation, and historical monitor tools
├── schemas/case.schema.json    ← schema for the current reviewed-case format
├── tests/                      ← current unit, fixture, validation, and dashboard smoke tests
├── archive/session-7b4d64dc-site/ ← PR #2 site + README, preserved byte-for-byte
└── .github/workflows/          ← current CI/Pages monitor plus earlier validation/manual monitor
```

## 5. How to add or change a canonical case (no-hallucination workflow)

1. Create/edit `data/cases/<YYYY-MM-DD>-<slug>.json` following `data/cases-schema.json`.
2. Every factual claim needs a `sources[]` entry with a direct `https://` link, publisher, tier,
   and `confirms` text. Unknown fields stay `null` with an `open_questions[]` entry.
3. Rule first on `classification.layer`: was the NBA's official record wrong, or only secondary?
4. Run `python3 scripts/validate.py` — it fails on placeholder URLs, illegal enums, missing
   questions, and status/source mismatches.
5. Run `compute_stats.py` + `build_site_data.py`, review the diff, open a PR.
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
- **Tooling:** `src/` needs API keys for live use (per its own README); the canonical CI monitor
  is the keyless `scripts/monitor.py`. Harmonization plan: `ROADMAP.md` §5.

## 8. Current root dashboard and monitor integration

This Arena review adds the current root dashboard (`index.html` + `assets/`), a separate evidence-reviewed seed file at `data/reviewed-cases.json`, and a tested monitor package in `monitor/`. The root dashboard deliberately uses that two-case seed rather than silently importing or reclassifying the older 12-record historical collection in `data/cases.json` and `docs/`. The older collection and its published interface are preserved and linked as the **Historical catalog**; those partial records were not re-audited in this pass and must not be treated as equivalent to the current evidence-reviewed seed. The 2017 Robinson III correction remains a strong source-backed record in that preserved catalog.

The current seed includes the 2024 Warriors–Trail Blazers and 2025 Cavaliers–Wizards postgame free-throw corrections. For Tre Johnson, the pre-correction player total is unknown in the reviewed game-night source; a later CBS page component showing 18 is retained only as a later observation with unknown update history, not asserted as his original total. The 213/214 report remains an unidentified lead and is not assigned a game or counted. See each case’s direct citations in `data/reviewed-cases.json`.

The current monitor polls the NBA scoreboard and ESPN scoreboard, records source health and score comparisons, retrieves NBA play-by-play for mismatches, and stores mismatch/final-feed-revision investigation records without deciding which feed is correct. UTC observation time is the monitor poll time; it is not a provider publication time. HTTP `ETag`, `Last-Modified`, and SHA-256 response metadata are retained with discrepancy observations when available. ESPN documents that its own feed corrections can be delayed and are distinct from official NBA post-game changes ([ESPN stat-corrections guidance](https://support.espn.com/hc/en-us/articles/360056679592-Stat-corrections)), so a mismatch remains a candidate rather than proof of an NBA record error.

`.github/workflows/pages-and-monitor.yml` is configured to check current feeds every five minutes and publish the root dashboard plus the preserved `docs/` catalog to GitHub Pages. The earlier `scripts/monitor.py` stays available for manual historical/backfill checks; its automated schedule is disabled to avoid two overlapping scheduled monitors. The old `pages.yml` deployment was replaced by the current combined workflow. A successful CI test run does **not** establish that a live source poll has succeeded. The post-merge Pages deployment did complete successfully, but check the Actions run, Pages environment/permissions, live-feed timestamp, and source health before describing automated monitoring as active.

The current offline review passed 22 unit tests, the repository-data checks (2 reviewed current cases and 1 explicitly unverified lead), Python compilation, JavaScript syntax checks, the Node dashboard smoke test, generated-data drift checks, and local HTTP checks for the root dashboard and preserved catalog. The post-merge Pages workflow completed successfully and the Pages API reports `built` for commit `4e3360a`; the external site content itself was not fetched here. No live NBA/ESPN poll has been verified. Next: audit and reconcile the preserved historical collection into the current interface without losing its open questions, identify the 213/214 source pair, and verify the first scheduled live run end to end.
