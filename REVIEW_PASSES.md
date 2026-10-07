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

## 2026-10-07 alerting session (feasibility question, implementation, three passes)

Requested scope: review the repository; determine whether an alert detection and
notification system for scoring discrepancies can be built; state its
limitations and feasibility; keep the founding brief in the README; publish a
clean dashboard; open a PR and merge it.

### Pass 1 — implement and verify

- [x] Answer feasibility with the repository as evidence: detectors, ledger, dispatch, dashboard
      panel, and `ALERTING.md` (§1 table: detection yes, confirmation no).
- [x] Implement the alert ledger (`monitor/alerts.py`: four detector families, severity policy
      `critical/high/medium/info`, occurrence milestones `1/3/12/48/144/720`, lifecycle
      `opened → reopened → resolved`, coverage gaps, detector status) and dispatch
      (`monitor/dispatch.py`: `gh`-CLI GitHub issues, optional Slack/Discord-compatible webhook,
      append-only `data/alert-dispatch-log.json`, `skipped` recorded rather than assumed).
- [x] Wire the CLI: `--dispatch-alerts [--apply]`, `--resolve-alert <id> [--note]`; workflow step
      `Dispatch alert notifications` with `issues: write` and a non-fatal `::warning::` on delivery
      failure so the site still deploys.
- [x] Dashboard: `#alerts` section (summary pill, alert cards with evidence/arithmetic/review
      steps/delivery state, detector status, coverage gaps) plus the corrected feed status pill.
- [x] Initial implementation checkpoint logged 77 Python tests and dashboard/data checks as green.
      The final integrated suite now passes 82 tests after merge-integration regression fixes (see
      the final verification note below).

### Pass 2 — adversarial defect / assumption review

Found and fixed:

1. **Primary-feed failure blanked the whole journal** (defect, material): rows were built only
   from the NBA feed, so an ESPN-only poll published `games: []`, stopped the ESPN final-score
   baseline, and prevented the single-provider arithmetic check from attaching to any row —
   in exactly the outage this project is living through. Fixed with the union snapshot builder
   (`monitor/feeds.py::build_observations_from_sources`), per-row `score_sources`, and a
   `Not compared` disclosure; the previous test that asserted the empty list was replaced with
   two tests that pin the corrected behaviour, including the real archived ESPN box score
   (derived 148 / 115) firing `final_score_internal_inconsistency` while the NBA feed is down.
2. **Dashboard smoke test asserted the pre-poll world** (`/Not yet active/`) and therefore would
   have failed on the first real published snapshot; it now derives the expected pill from
   `data/live-feed.json`, exercises the alert renderer with a labelled synthetic alert, and checks
   every configured source chip.
3. **Source health chips were hard-coded** to `nba`/`espn` and printed a raw key for any new
   source; labels are now mapped and unknown keys degrade to an upper-cased key with the last
   error in the tooltip.
4. **Machine-written data was never verified**: pushes made with `GITHUB_TOKEN` do not start a new
   workflow run, so the first scheduled commit changed the dashboard's data with no check on it.
   The scheduled job now runs the unit tests + JS syntax + smoke test before committing.
5. **`duration_ms` and per-poll timestamps** would have rewritten committed files every five
   minutes; diagnostics are published without durations and the feed/ledger are only rewritten on
   a material signature or occurrence-milestone change.
6. **The snapshot's explanation was frozen behind an unchanged game list**: the material
   signature that decides whether `data/live-feed.json` is rewritten excluded the `note` text,
   so after this fix a stale explanation ("the last saved snapshot") could have survived even
   while a reachable source was being published. The note is now part of the signature, with a
   focused test (`test_note_wording_is_part_of_the_material_signature`).
7. **Delivery honesty**: unconfigured webhook → logged `skipped` (not silence); missing `gh` →
   `dispatch.status = "skipped"`; three failed attempts → `failed`; issues always carry the
   "does not establish that any NBA record was wrong" limitation.
8. **Comparator outage never became notify-eligible**: `update_book` preserved the first
   `not_required` state after the comparator's 60-minute dispatch threshold. It now promotes that
   state to `pending` only when the current policy explicitly makes it eligible; the existing
   `test_comparator_outage_is_medium_and_not_notified_until_an_hour` caught and locks the fix.
9. **Issue lifecycle and unsafe-text edge cases**: fixed the generated `gh` stub's line endings and
   added regressions for material issue refresh, human closure, non-causal resolution comments,
   Markdown/@mention escaping, and unsafe links. The monitor edits only marker-matching open issues
   and no longer closes issues automatically.
10. **Snapshot freshness wording**: removed dashboard references to unsupported per-poll timestamps;
    the pill describes the saved snapshot, and the page says poll freshness is unknown without an
    Actions-history check. Corrected verification docs to match the actual workflow artifact rules.
11. **Alert search link targeted an obsolete marker**: changed the dashboard query to match the
    `[score-alert]` title prefix generated by `monitor/dispatch.py`; the dashboard smoke test now
    asserts that wiring.

### Pass 3 — full-request recheck

- [x] Founding brief read from `README.md` §0 before work; §0 now carries the entire original
      prompt verbatim (research spec, core values, site-creation and multi-pass instructions,
      including the alerting question) and §1 restates the reading rules.
- [x] Every factual statement added to the README/`ALERTING.md` is either a repository path, a
      test, or a linked source; the two external probes performed this session
      (`cdn.nba.com/robots.txt` → S3 `AccessDenied`; scoreboard object → HTTP 500) are quoted as
      probes, not as league facts. No game-level claim is made about any real correction.
- [x] Confirm the honest layer distinction: an alert is a candidate, feed convergence is not a
      correction, and the two confirmed cases remain the only confirmed records.
- [x] Confirm the "no manual input" requirement: the scheduled workflow polls, validates,
      dispatches, commits, and deploys unattended; there is no step that requires a human, and no
      step that silently depends on one.
- [x] Deliverable status: feasibility answered (§1 table + `ALERTING.md` §3), implementation
      complete and tested, remaining limitations enumerated (no reachable second source, no
      corrections feed, best-effort cron, alert not yet delivered in production).
- [x] Final local verification of the integrated tree: **82 Python tests**. Also passed Python
      compilation (`monitor`, `scripts`, `src`, `tests`), monitor/data validation, the historical
      self-test, active/historical JavaScript syntax checks, dashboard smoke test, diff hygiene,
      and workflow-YAML parsing.
- [x] Re-scan docs for references to deleted alert scripts and stale timestamp/heartbeat claims;
      corrected the contributor checklist and verification notes. Dashboard shows `last_updated_at`
      as a material-change time, not a poll time.
- [ ] **Unfinished by design:** none of the Pass-3 checks depends on the live NBA feed, but the
      production notification has still never fired. That gap is stated in README §8 and
      ROADMAP 5b rather than papered over.
