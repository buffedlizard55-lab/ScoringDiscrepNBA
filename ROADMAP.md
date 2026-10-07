# Limitations, known gaps & roadmap

Honest accounting of what this project cannot yet do, and what the next session(s) should do.
Ordered by P(Win): highest-evidence-value first.

## 1. Current limitations (do not over-claim)

1. **Sample, not census.** 12 verified-partial cases + 1 unverified stub. All shares are
   collection-only (caveat is machine-readable in `stats.json` and shown on the site).
2. **No case is fully `verified` yet.** Every record still has open questions — mostly missing
   *primary* NBA statements (2019 denial, 2014 denial, 2008 ruling, 1982 ruling, 2025 correction
   notice) and box-score corroboration of a few finals.
3. **Originating 213-vs-214 game is unidentified.** Until recovered, the project's headline
   rarity question (“how rare are 213/214 incidents?”) cannot be quantified beyond the three
   verified one-point total corrections (2017: 204→203; 2024: 243→244; 2025: 262→263).
4. **Pre-2000s coverage is thin.** Per the league's best-available records only 6 protests
   have ever been upheld (NBA.com) — this collection documents 2 (1982-83, 2007-08). The other
   4 (reportedly incl. a 1978 Nets–76ers game plus 1952/1969/1971 games per the PR #2 session's
   leads) are known gaps requiring independent per-case verification.
5. **Monitor blind spots:** arena scoreboards / TV bugs are invisible to feed comparison;
   transient live-feed lag is expected noise; ESPN/NBA endpoints can change without notice.
6. **No archived snapshots yet.** Cases cite live URLs; pre/post-correction box-score snapshots
   (web archives) are not yet attached as evidence.
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
      Johnson correction; Dec 9 2019 denial; Nov 28 2014 denial; Jan 11 2008 ruling; Dec 1982
      ruling. Attach URLs, re-run validation.
- [ ] **C. Box-score corroboration.** Confirm on official box scores / Basketball-Reference:
      post-replay 114-111 (2008) and 117-114 (1983); Melton's corrected points (resolves the
      11-vs-12 dispute); Finals G6 2019 final + venue (fills deliberate nulls); original
      108-96 line for the 2017 case (currently derived).
- [ ] **D. Historical-protest verification.** Independently verify the PR #2 session's four
      pre-1982 upheld-protest leads (1952 MIL@PHI, 1969 ATL@CHI, 1971 CLE@BUF, 1978 NJN@PHI)
      from newspaper archives + the league's protest records; promote each to `data/cases/`
      only with fresh sources. Start from `data/discrepancies.json` IDs DISC-19521128-*,
      DISC-19691106-*, DISC-19711203-*, DISC-19781108-* (treat as LEADS, not facts).
- [ ] **E. Scorebug + Porter leads.** Verify the 2026 NBC/Amazon scorebug reports and the 2021
      Porter Jr. stat correction from the cited outlets (URLs in `data/discrepancies.json`
      DISC-20260420-*, DISC-20260415-*, DISC-20211022-*); promote or reject with a decision log.
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
- PR merged to `main`; site redeployed; this file updated.

## 5. Cross-session harmonization (PR #2 ↔ PR #3)

Two sessions built parallel implementations; the merge kept both. Canonical vs legacy:

| Concern | Canonical (PR #3, served + CI-enforced) | Legacy (PR #2, preserved) |
|---|---|---|
| Case store | `data/cases/*.json` → `data/cases.json` (schema: `data/cases-schema.json`) | `data/discrepancies.json` (schema: `data/schema.json`) — leads, audit-flagged |
| Verification log | `VERIFICATION.md` §§1-6 | Preserved verbatim as Appendix A; original session README in `archive/` |
| Monitor in CI | `scripts/monitor.py` (stdlib, keyless) | `src/monitor.py` (manual runs; needs API keys per its README) |
| Served site | `docs/` (reads `docs/data/`) | `archive/session-7b4d64dc-site/` (standalone) |
| Stats | `data/stats.json` (caveated) | `data/statistics.json` (see audit flags before citing) |

Harmonization rules: promote legacy leads into `data/cases/` only with fresh independent
verification (the 2017 Robinson III case is the template — lead from PR #2, re-verified here).
Never bulk-import. The audit findings live in `VERIFICATION.md` §6.
