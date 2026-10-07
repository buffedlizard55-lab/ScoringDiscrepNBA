# Limitations, known gaps & roadmap

Honest accounting of what this project cannot yet do, and what the next session(s) should do.
Ordered by P(Win): highest-evidence-value first.

## 1. Current limitations (do not over-claim)

1. **Sample, not census.** The historical catalog contains 12 verified-partial records and 2
   unverified stubs (213/214 and the 2021 Kevin Porter Jr. lead). Its 12-of-14 collection count
   is not a league-wide rate. The active root dashboard is a separate two-confirmed-case seed.
2. **Historical records remain partial.** No historical case is promoted to fully `verified`;
   open questions remain, including primary rulings (2019 denial, 2014 denial, 2008 ruling, 1982
   ruling) and original/final box-score snapshots. The 2025 NBA Official X correction post is now
   linked, but the explanation of “human error” remains attributed to The Athletic.
3. **Unverified leads stay out of statistics.** The originating 213-vs-214 game and the 2021
   Kevin Porter Jr. correction lead remain unidentified/unverified. No game, changed player statistic,
   or source history is inferred. The rarity question cannot be quantified beyond the small,
   explicitly scoped collection; no league-wide denominator exists.
4. **Pre-2000s coverage is thin.** Per the league's best-available records only 6 protests
   have ever been upheld (NBA.com) — this collection documents 2 (1982-83, 2007-08). The other
   4 (reportedly incl. a 1978 Nets–76ers game plus 1952/1969/1971 games per the PR #2 session's
   leads) are known gaps requiring independent per-case verification.
5. **Monitor blind spots (partly mitigated, still real):** arena scoreboards / TV bugs are
   invisible to feed comparison; transient live-feed lag is expected noise; provider endpoints
   can change without notice. Since the 2026-10-07 session the monitor no longer blanks out when
   the primary feed fails: it publishes the games every reachable source reported, marks the row
   `Not compared`, records the outage as a coverage gap, and runs the single-provider arithmetic
   check (`2*(FGM-3PM)+3*3PM+FTM` from the provider's own box score). An error propagated
   identically into both views of one provider is still invisible, and there is still no second
   reachable comparator while the NBA CDN feed returns HTTP 500 to the runner.
5b. **Alert delivery is not yet proven in production.** The ledger, lifecycle, dedupe, severity,
   review steps, and GitHub-issue/webhook dispatch are implemented and offline-tested (82 tests,
   stubbed `gh`, local webhook receiver), but no scheduled run has produced an alert that was
   delivered: the only scheduled poll so far had the NBA feed down and no games. Until
   `data/alert-dispatch-log.json` contains a `sent` entry with an issue URL, describe the
   notification system as implemented and verified offline, never as observed working in
   production.
5c. **Scheduler cadence is best-effort.** The workflow requests `*/5`, but GitHub documents
   delays and dropped queue entries under load, and the run history during this review showed far
   fewer runs than requested. Detection latency cannot be promised below that.
6. **Original-state snapshots are incomplete.** Current NBA pages and an NBA Gamebook corroborate
   some corrected values, but pre-correction game-night box-score snapshots and the exact record-update
   times are not preserved for the 2024/2025 examples.
7. **Duration analysis is day-granularity.** Game→correction/ruling lags are computed where
   timelines allow (see `resolution_lag_days`); intraday detection→correction timestamps and
   transient display-error durations still need work.
8. **Schema v1 approximations:** the 1982 rules-misapplication replay is typed
   `official-scorer-book-error` for lack of a better enum; the 7-day-later 2017 correction
   reuses `corrected-next-day`. Schema v2 should add `rules-misapplication-replay` and
   `corrected-later`.

## 2. Suggested next session (concrete, ordered)

- [ ] **A. Recover the 213/214 game.** Search bettor/social reports, odds-total anomalies, and
      next-day box-score diffs for 1-point total moves; follow the stub's resolution rule.
- [ ] **B. Primary-source hunt.** Locate NBA.com/@NBAOfficial/AP-issued texts for: Nov 2025
      Johnson correction beyond the linked NBA Official post; Dec 9 2019 denial; Nov 28 2014 denial;
      Jan 11 2008 ruling; Dec 1982 ruling. Attach URLs, re-run validation.
- [ ] **C. Box-score corroboration.** Confirm on official box scores / Basketball-Reference:
      post-replay 114-111 (2008) and 117-114 (1983); Melton's exact corrected player total (the
      11-vs-12 disagreement is explicitly unresolved); Finals G6 2019 final + venue (fills deliberate
      nulls); original 108-96 line for the 2017 case (currently derived).
- [ ] **D. Historical-protest verification.** Independently verify the PR #2 session's four
      pre-1982 upheld-protest leads (1952 MIL@PHI, 1969 ATL@CHI, 1971 CLE@BUF, 1978 NJN@PHI)
      from newspaper archives + the league's protest records; promote each to `data/cases/`
      only with fresh sources. Start from `data/discrepancies.json` IDs DISC-19521128-*,
      DISC-19691106-*, DISC-19711203-*, DISC-19781108-* (treat as LEADS, not facts).
- [ ] **E. Scorebug + Porter leads.** Verify the 2026 NBC/Amazon scorebug reports and investigate
      the 2021 Porter Jr. lead using the URLs in `data/discrepancies.json` (DISC-20260420-*,
      DISC-20260415-*, DISC-20211022-*). Keep the KPJ record unverified and excluded unless primary
      or independently corroborated evidence identifies the game and the exact change.
- [ ] **F. Evidence snapshots.** Add `evidence/` with archived pre/post-correction box scores
      for the 2017 + 2024 + 2025 correction cases; link from records.
- [x] **G. Monitor hardening — alerting layer.** *(2026-10-07 session)* Alert ledger
      (`data/alerts.json`), lifecycle with occurrence milestones, severity policy, coverage gaps
      for outages, GitHub-issue + optional webhook dispatch with an append-only delivery log,
      dashboard alert panel, and `ALERTING.md` (feasibility + limitations). See
      `REVIEW_PASSES.md` "2026-10-07 alerting session".
- [ ] **G2. Reach a second live comparator.** The NBA CDN feed answers the scheduled runner with
      HTTP errors, so cross-source comparison cannot run. Observed this session: the NBA CDN
      scoreboard object returned HTTP 500 and `robots.txt` returned an S3 `AccessDenied` document;
      Yahoo's editorial scoreboard (`https://api-secure.sports.yahoo.com/v1/editorial/s/scoreboard?leagues=nba&date=YYYY-MM-DD`)
      answered HTTP 200 with per-game `total_away_points`/`total_home_points`, `status_type`, and
      `home_team_id`/`away_team_id` (e.g. `nba.t.11`), but its team-id → abbreviation island has
      **not** been verified yet, so no Yahoo parser was written. Verify that island, add the
      adapter plus a fixture, then re-check the source-role policy before treating Yahoo as a
      comparator.
- [ ] **G3. Corrections watcher.** Watch league statement channels (newsroom RSS / official
      account) and open an investigation automatically when a correction is published — the
      missing half of the loop, which is why detection is currently after-the-fact.
- [ ] **G4. Live-window soak test.** Exercise the alert path during real games; measure how often
      a first-poll disagreement clears on its own (it should stay unalerted below two consecutive
      polls) and tune `MAX_SUMMARY_FETCHES`/re-check intervals from observed volume.
- [ ] **H. Schema v2.** Add `rules-misapplication-replay` type and `corrected-later` outcome;
      migrate the 1982 and 2017 cases; keep validator green.

## 3. Standing research backlog (candidate leads — NOT facts)

These are *leads to investigate*, not findings. Each needs the full verification workflow before
becoming a record.

- L2M-report-era scoring controversies (post-2015) with verifiable score impact.
- Google/ESPN box-score display glitches reported by users (e.g. swapped columns) — secondary-only class.
- Sportsbook void/correction incidents tied to an NBA stat change (settlement-policy evidence).
- In-season tournament / point-differential computation disputes, if any were officially corrected.
- G League / Summer League one-free-throw-era scoring anomalies (out of scope unless NBA-rulebook-relevant).
- PR #2's Yahoo-fantasy-stat-corrections and ESPN-corrections-page monitoring ideas (see its README in `archive/`).

## 4. Definition of done for “next session”

- `validate.py`, `compute_stats.py`, `build_site_data.py`, `monitor.py --self-test` all green.
- At least 2 open questions closed with primary evidence (or explicitly re-scoped with a dated note).
- The 213/214 stub either identified or reclassified with a decision log (no silent drift).
- [x] PR #4 merged to `main` after GitHub confirmed success; post-merge validation, verification,
  and Pages deployment succeeded; public site was fetched and checked.
- [x] PR #7 merged; the scheduled workflow published its first real snapshot
  (`data/live-feed.json` = `degraded`, ESPN `ok`, NBA unavailable with an HTTP error, published
  timestamp `2026-10-07T11:50:09Z`). The `not_started` placeholder is gone; the honest status is
  now "running, primary feed blocked".
- [ ] No alert has been delivered by a scheduled run yet (see limitation 5b).

## 5. Current architecture and retained earlier layers

The root dashboard/monitor (PR #5/#6) is the active published interface. The older historical
catalog and monitor remain available for their distinct purposes; they must not be conflated.

| Concern | Active root dashboard / monitor | Historical or retained layer |
|---|---|---|
| Root case sample | `data/reviewed-cases.json` (2 evidence-reviewed cases) | `data/cases/*.json` → `data/cases.json` and the linked `docs/` catalog (12 partial cases + 2 unverified stubs) |
| Open leads | `data/leads.json` (213/214 and KPJ; excluded from counts) | `data/discrepancies.json` — legacy leads, audit-flagged |
| Current monitor | `monitor/` package; `data/live-feed.json` + `data/monitor-state.json` | `scripts/monitor.py` and `data/monitor/current.json` for manual/backfill; current snapshot is `not-run` |
| Site | Root `index.html` + `assets/`; `.github/workflows/pages-and-monitor.yml` | `docs/` historical catalog, included in Pages artifact |
| Validation | `python3 -m monitor --check-data`; `.github/workflows/ci.yml` | `scripts/validate.py`, `compute_stats.py`, `build_site_data.py`; manual `monitor.yml` |
| Statistics | Root seed counts are descriptive only; no NBA-wide rates | `data/stats.json` is collection-only; `data/statistics.json` is a superseded/audit-flagged manifest; old numeric archive remains historical |
| Legacy tooling | — | `src/` may require API keys; do not treat as the scheduled monitor |

Harmonization rules: do not bulk-import legacy leads or historical partial records into the root
seed. Re-verify each factual claim, preserve nulls and open questions, retain original and corrected
observations, and keep feed convergence distinct from human-confirmed resolution. The prior-session
audit is recorded in `VERIFICATION.md` §6.
