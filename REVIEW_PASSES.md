# Three-pass implementation and review log

This log enforces the requested Pass 1 → Pass 2 → Pass 3 sequence. Evidence links and test output are maintained in the repository and in the session work log; do not mark a pass complete before running its checks.

## Pass 1 — implement and verify

- [x] Reread the existing README before work and preserve the full carried-forward project brief in the expanded README.
- [x] Add a source register, two confirmed cases, and the separate unverified 213/214 and Kevin Porter Jr. leads.
- [x] Add accessible static browse/search/filter UI, evidence details, coverage notes, and live-monitor status components.
- [x] Add a dependency-free dual-feed monitor, change-history format, unverified-candidate lifecycle, optional non-causal PBP context, validator, fixtures, and CI/Pages workflows.
- [x] Run validator, all unit tests, and Pages build; review exact results — validator passed (2 confirmed/2 unverified); 17 offline unit tests passed; Pages artifact built successfully.

## Pass 2 — adversarial defect / missing-requirement review

- [x] Inspect score and source claims against the recorded primary/secondary links; distinguish official correction from provider-only inconsistency.
- [x] Review feed parsing, matching/alias logic, score-missing behavior, source outages, repeated polls, state persistence, candidate convergence/reopening, and relative-path behavior.
- [x] Check accessible labels, focus visibility, small-screen layout, search/filter behavior, and safe text/link rendering; add automated HTML-ID/control-label/selector checks.
- [x] Fix defects found and rerun the complete test suite.

**Pass 2 findings/fixes:** kept the KPJ claim as a second explicitly unverified lead; added dates and precision notes to captured provider conflicts; surfaced partial ESPN date-query failures; validated arithmetic-derived scores and source references; prevented source outages from resolving candidates; separated feed convergence from human investigation status; preserved reviewed resolutions in history when a new divergence reopens; and linked PBP context to a game-specific URL only when available. Initial Pass 2 checkpoint: 17 tests passed, data validation passed, and the Pages artifact built. During integration with the newer `main` monitor package, adversarial tests exposed a Python import collision: the historical monitor test imported `monitor` by ambiguous module name after the current `monitor/` package had loaded. The test now loads `scripts/monitor.py` explicitly by path. The integrated suite currently passes 47 tests.

## Pass 3 — full-request recheck and further improvements

- [x] Crosswalk the founding brief, source-preservation rules, historical/current scope, statistics caveats, accessibility, monitoring, and operating values against the integrated repository.
- [x] Keep both the 213/214 report and 2021 Kevin Porter Jr. item explicitly unverified and outside confirmed-case statistics; retain nulls and evidence needed.
- [x] Recheck source roles and disagreements: NBA correction vs ESPN/CBS page inconsistency; preserve Melton's exact corrected player total as unresolved (11 vs 12); add the direct NBA Official post for the 2025 correction while attributing the separate human-error explanation.
- [x] Run active + historical validators, both dashboard JavaScript syntax checks, monitor self-test, Python compilation, 47 offline tests, deterministic stats/site generation, and Pages artifact smoke checks.
- [x] Confirm honest live-monitor baselines: current monitor `not_started`, historical monitor `not-run`; no unverified poll is described as successful.
- [x] Integrate latest `origin/main` ancestry on the fixed Arena branch, push it, confirm PR CI/mergeability, and merge PR #4 after GitHub reported it ready.
- [x] Verify post-merge validation, verification, Pages publishing, Pages deployment, and the public root + historical catalog.
- [x] Preserve honest operational baselines: the push event skipped live source comparison; `data/live-feed.json` remains `not_started` and the historical monitor remains `not-run`.
- [ ] Verify the first successful scheduled NBA/ESPN poll and published timestamp. Manual `workflow_dispatch` from this session was denied by GitHub with HTTP 403 (`Resource not accessible by integration`); no live poll is claimed.

**Pass 3 implementation/review is complete.** Production deployment is confirmed, but live monitoring is **not yet proven operational** until the scheduled poll publishes a successful snapshot. Keep that distinction explicit in future updates.

---

## Current Arena session — notification and freshness hardening (2026-10-07)

### Pass 1 — implement and verify

- [x] Read the carried-forward README brief before continuing; preserve Arena's “Maximize P(Win)” and “Own the Outcome” operating values.
- [x] Add idempotent GitHub issue notifications with durable issue number/body-hash/status metadata; refresh material changes, skip unchanged issues, leave human-closed issues untouched, and keep convergence non-causal/non-auto-closing.
- [x] Order workflow notification before material-diff detection so notifier metadata is committed with monitor state; keep issue API failures warning-only so feed publication continues.
- [x] Add poll-attempt and paired-feed timestamps, material-only commit comparison, stale/unknown dashboard freshness messaging, and better HTTP status diagnostics.
- [x] Preserve investigation originals and add incomplete-comparison markers; outages, missing games, and incomplete scores break the two-comparable-poll alert/convergence streak.
- [x] Run all active/historical validators, Python/JavaScript syntax checks, monitor self-test, dashboard and alert smoke tests, workflow YAML parsing, deterministic generators, and diff hygiene.

**Pass 1 results:** 53 Python unit tests passed; both Node smoke tests passed; active data checks passed (2 reviewed cases, 2 explicitly unverified leads); 14 historical case files validated; monitor self-test and compilation passed; updated Pages/CI YAML parsed; stats/site generation made no unexpected changes; material monitor diff returned `false` for the unchanged checked-in snapshot.

### Pass 2 — adversarial defect and gap review

- [x] Verify alert filtering and payload labels do not assign fault or upgrade a source observation into an NBA-record correction.
- [x] Test deduplication, material score refresh, API-free unchanged runs, persisted notification metadata, closed issues, resolution notices, feed-text HTML/mention escaping, and stale issue references.
- [x] Find and fix a subtle false-positive path: a failed or missing-game poll had no game-row observation, so two mismatches separated by an unobserved poll could appear adjacent. Persist an `incomplete` comparison marker and reset both streaks; repeated incomplete polls do not create heartbeat-only commits.
- [x] Check stale/missing/future poll timestamps and distinguish attempt heartbeat from a successful paired-feed comparison in the dashboard.
- [x] Reorder alerting before material-diff detection and explicitly pass the workspace monitor-state path to the action.

**Pass 2 findings/fixes:** the alert smoke test initially exposed raw-HTML risk in feed-provided play-by-play text; angle brackets are now HTML-encoded. Review also found that a stale saved issue number could otherwise edit an unrelated issue; the notifier now verifies the stable issue marker before mutation and searches/creates safely if the reference is mismatched. Incomplete comparisons now break mismatch and convergence streaks. All findings were regression-tested.

### Pass 3 — full-request recheck

- [x] Recheck the founding scope, source-role distinction, no-overwrite/no-hallucination rules, accessible dashboard status, and notification limitations.
- [x] Keep the originating 213/214 report and 2021 Kevin Porter Jr. lead unverified and excluded from confirmed-case statistics; add no new historical-case claims in this implementation pass.
- [x] Confirm alert behavior does not prove which feed is right, does not auto-create a verified case, does not auto-close GitHub issues, and does not promise personal email/mobile/closed-tab push.
- [x] Run the complete test/check matrix recorded above after final changes.
- [ ] Push the fixed Arena branch, open the requested PR, and merge if GitHub permits; record CI and deployment outcomes below.
- [ ] Verify a later scheduled feed snapshot only after it occurs. No live poll was run during this review; the checked-in snapshot is the previously observed degraded snapshot, not evidence of current source availability.
