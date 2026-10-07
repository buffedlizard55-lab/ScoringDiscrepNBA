# Limitations, known gaps & roadmap

Honest accounting of what this project cannot yet do, and what the next session(s) should do.
Ordered by P(Win): highest-evidence-value first.

## 1. Current limitations (do not over-claim)

1. **Sample, not census.** 11 verified-partial cases + 1 unverified stub. All shares are
   collection-only (caveat is machine-readable in `stats.json` and shown on the site).
2. **No case is fully `verified` yet.** Every record still has open questions — mostly missing
   *primary* NBA statements (2019 denial, 2014 denial, 2008 ruling, 1982 ruling, 2025 correction
   notice) and box-score corroboration of a few finals.
3. **Originating 213-vs-214 game is unidentified.** Until recovered, the project's headline
   rarity question (“how rare are 213/214 incidents?”) cannot be quantified beyond the two
   verified one-point total corrections (2024: 243→244; 2025: 262→263).
4. **Pre-2000s coverage is one case.** The Nets–76ers upheld protest (3rd of 3 since 1952 per
   USA Today; exact date not captured in this pass — do not assert a decade) is a known gap;
   newspaper-archive research is needed.
5. **Monitor blind spots:** arena scoreboards / TV bugs are invisible to feed comparison;
   transient live-feed lag is expected noise; ESPN/NBA endpoints can change without notice.
6. **No archived snapshots yet.** Cases cite live URLs; pre/post-correction box-score snapshots
   (web archives) are not yet attached as evidence.
7. **Duration analysis is thin.** “How long do discrepancies last?” currently has only coarse
   answers (in-game minutes vs next-day); per-case detection→correction timestamps need work.
8. **Schema v1 approximations:** the 1982 rules-misapplication replay is typed
   `official-scorer-book-error` for lack of a better enum; propose `rules-misapplication-replay`
   in schema v2.

## 2. Suggested next session (concrete, ordered)

- [ ] **A. Recover the 213/214 game.** Search bettor/social reports, odds-total anomalies, and
      next-day box-score diffs for 1-point total moves; follow the stub's resolution rule.
- [ ] **B. Primary-source hunt.** Locate NBA.com/@NBAOfficial/AP-issued texts for: Nov 2025
      Johnson correction; Dec 9 2019 denial; Nov 28 2014 denial; Jan 11 2008 ruling; Dec 1982
      ruling. Attach URLs, re-run validation.
- [ ] **C. Box-score corroboration.** Confirm on official box scores / Basketball-Reference:
      post-replay 114-111 (2008) and 117-114 (1983); Melton's corrected points (resolves the
      11-vs-12 dispute); Finals G6 2019 final + venue (fills deliberate nulls).
- [ ] **D. Nets–76ers upheld-protest case.** Archive research (USA Today 2014 refs as the lead; confirm date/teams from newspaper archives); new case file.
- [ ] **E. Evidence snapshots.** Add `evidence/` with archived pre/post-correction box scores for
      the 2024 + 2025 FT cases; link from records.
- [ ] **F. Monitor hardening.** Real-world soak test during a live game window; tune live-vs-final
      handling; add quarter-line drift detection; alert on `feed-unavailable` streaks.
- [ ] **G. Duration + rarity analytics.** Add per-case detection→correction lag fields where
      timestamps exist; expand stats with lag distribution (still caveated).
- [ ] **H. Schema v2.** Add `rules-misapplication-replay` type; migrate 1982 case; keep validator green.

## 3. Standing research backlog (candidate leads — NOT facts)

These are *leads to investigate*, not findings. Each needs the full verification workflow before
becoming a record.

- L2M-report-era scoring controversies (post-2015) with verifiable score impact.
- Google/ESPN box-score display glitches reported by users (e.g. swapped columns) — secondary-only class.
- Sportsbook void/correction incidents tied to an NBA stat change (settlement-policy evidence).
- In-season tournament / point-differential computation disputes, if any were officially corrected.
- G League / Summer League one-free-throw-era scoring anomalies (out of scope unless NBA-rulebook-relevant).

## 4. Definition of done for “next session”

- `validate.py`, `compute_stats.py`, `build_site_data.py`, `monitor.py --self-test` all green.
- At least 2 open questions closed with primary evidence (or explicitly re-scoped with a dated note).
- The 213/214 stub either identified or reclassified with a decision log (no silent drift).
- PR merged to `main`; site redeployed; this file updated.
