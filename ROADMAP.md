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
5. **Monitor blind spots:** arena scoreboards / TV bugs are invisible to feed comparison;
   transient live-feed lag is expected noise; ESPN/NBA endpoints can change without notice.
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
- [ ] **G. Monitor hardening.** Real-world soak test during a live game window; tune
      live-vs-final handling; add quarter-line drift detection; alert on
      `feed-unavailable` streaks. Decide whether to adopt PR #2's auto-issue idea (spam-safe?).
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
- PR #4 merged to `main` only after GitHub confirms success; post-merge CI/Pages checked; live feed
  status described honestly; this file updated.

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
