# NBA Scoring Discrepancies — Verified Research & Live Monitor

> **Session-start rule: read this README first, every time we work on the project.**
> It holds the founding brief, the operating values, and the no-hallucination policy.
> Build, research, suggest, and implement against it. Own the outcome end to end.

**Live site (GitHub Pages):** `https://buffedlizard55-lab.github.io/ScoringDiscrepNBA/`
*(enable Pages: repo Settings → Pages → Source “GitHub Actions”, then the `Deploy site` workflow publishes `docs/`)*

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
| Canonical case database (12 verified-partial + 1 unverified stub) | `data/cases/*.json` → `data/cases.json` | ✅ Live |
| Canonical record schema + validation | `data/cases-schema.json`, `scripts/validate.py` | ✅ Live |
| Collection statistics (regenerated, caveated) | `data/stats.json` via `scripts/compute_stats.py` | ✅ Live |
| Source reliability tiers | `data/sources.json` | ✅ Live |
| Continuous monitor (ESPN vs NBA liveData + PBP) | `scripts/monitor.py`, `monitor/STATE.md` | ✅ Live (runs in CI; self-test passes offline) |
| Investigation log / live feed | `data/investigations.json` | ✅ Live (empty = no open detections) |
| Public website (search, filter, compare, verify) | `docs/` → GitHub Pages | ✅ Live |
| CI: validate on push/PR | `.github/workflows/validate.yml` | ✅ Live |
| CI: scheduled monitoring | `.github/workflows/monitor.yml` | ✅ Live (active after merge to `main`) |
| CI: Pages deploy | `.github/workflows/pages.yml` | ✅ Live (needs Pages → GitHub Actions enabled once) |
| Verification log + methods | `VERIFICATION.md` | ✅ Live |
| Limitations + roadmap | `ROADMAP.md` | ✅ Live |
| Prior-session store + tools (PR #2, preserved as leads) | `data/discrepancies.json`, `src/`, `research/` | ⚠️ Preserved, audit-flagged (see §7) |
| Prior-session site (PR #2, byte-identical archive) | `archive/session-7b4d64dc-site/` | 📦 Archived, standalone |

**Originating 213-vs-214 report:** tracked as `0000-00-00-originating-213-vs-214-report`
with status `unverified`. The game is unidentified — it must not be cited as fact until the
checklist in that record is satisfied.

## 3. Quick start

```bash
# validate every canonical case (anti-hallucination rules enforced)
python3 scripts/validate.py

# recompute statistics + rebuild the site data bundle
python3 scripts/compute_stats.py
python3 scripts/build_site_data.py

# offline monitor self-test (no network; uses synthetic 213-vs-214 fixture)
python3 scripts/monitor.py --self-test

# live monitor (needs internet: ESPN + NBA CDN)
python3 scripts/monitor.py --date 20250115 --lookback 1

# preview the site
cd docs && python3 -m http.server 8080
```

## 4. Repository map

```
├── README.md                  ← you are here (read first, every session)
├── VERIFICATION.md            ← methods, source hierarchy, line-by-line log (+ PR #2 appendix)
├── ROADMAP.md                 ← limitations, next-session work, harmonization plan
├── CONTRIBUTING.md            ← prior-session contribution guide (references data/schema.json)
├── index.html                 ← root redirect to docs/ (prior session, still valid)
├── data/
│   ├── cases-schema.json      ← canonical record contract (required fields, enums, rules)
│   ├── cases/*.json           ← canonical store: one file per case; null = unknown, never guessed
│   ├── cases.json             ← generated aggregate (do not hand-edit)
│   ├── stats.json             ← generated stats (caveated: collection-only)
│   ├── sources.json           ← reliability tiers + authoritative references
│   ├── investigations.json    ← monitor's open/resolved detection log
│   ├── schema.json            ← LEGACY schema for discrepancies.json (PR #2; kept for its tooling)
│   ├── discrepancies.json     ← LEGACY store (PR #2; leads pending re-verification)
│   ├── statistics.json        ← LEGACY stats (PR #2; see audit flags before citing)
│   ├── latest_check.json      ← LEGACY monitor output (PR #2)
│   └── live_alerts.json       ← LEGACY alerts (PR #2)
├── scripts/                   ← canonical tooling (stdlib only): validate, compute_stats,
│                                build_site_data, monitor (+ fixtures/)
├── src/                       ← LEGACY tooling (PR #2; needs API keys; manual runs only)
├── research/                  ← LEGACY case notes (PR #2; 1 of 12 listed files present)
├── monitor/STATE.md           ← how canonical monitoring works, lifecycle, runbook
├── archive/session-7b4d64dc-site/ ← PR #2 site + README, byte-identical, standalone
├── docs/                      ← canonical GitHub Pages site (index.html, app.js, styles.css, data/)
└── .github/workflows/         ← validate.yml, monitor.yml, pages.yml
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
