# Repository audit and alerting feasibility

Review date: 2026-10-07 UTC. Read with the [founding brief](../README.md).

## Decision

**Yes: automated candidate detection and notification is feasible and already
implemented. No: this repository is not yet a complete, continuously observed,
independently verified database of every NBA scoring discrepancy.** Do not
market it as such. No system observing only current JSON feeds can reconstruct
an overwritten score it never captured, or determine an unseen scorer's intent.

The high-value next step is evidence durability and actual delivery validation,
not adding speculative historical cases. This applies **Maximize P(Win)** by
reducing false findings and **Own the Outcome** by testing the full chain from
observation to published evidence and notification.

## Evidence and verification boundaries

- Read the README brief first. Inspected active adapters, runner, state engine,
  workflow, tests, site, and collection validation results. This is a targeted
  code/data review, **not independent line-by-line factual re-verification of
  all inherited prose or every legacy module**.
- Baseline: 82 unit tests passed. After fixes: 90 tests passed; both active and
  historical validators, dashboard smoke test, and historical monitor self-test
  passed. Validators test contracts and citations, not the truth of articles.
- GitHub [Pages API](https://api.github.com/repos/buffedlizard55-lab/ScoringDiscrepNBA/pages)
  returned `status: built`, HTTPS enabled, root of main, and `build_type: legacy`.
  The workflow also deploys Pages artifacts. This is duplicate deployment
  configuration; consolidate before treating deployments as operationally clean.
- GitHub [run 37663924132](https://github.com/buffedlizard55-lab/ScoringDiscrepNBA/actions/runs/37663924132)
  and its [job metadata](https://api.github.com/repos/buffedlizard55-lab/ScoringDiscrepNBA/actions/runs/37663924132/jobs)
  reported success for polling, checks, dispatch step, and deployment. Logs
  could not be downloaded because their storage host is outside this session's
  network allowlist. A successful dispatch step is **not** a delivery receipt:
  it can have no eligible alerts, and the workflow tolerates delivery failures.
- The checkout contains no `data/alert-dispatch-log.json`. Live delivery remains
  unproven here. Do not send synthetic incidents as genuine scoring alerts.
- Only GitHub and package-registry network hosts are available in this session.
  NBA, ESPN, NBA Official, and news article content could not be freshly read.
  Existing source labels are inherited evidence classifications, not new
  verification. No case was added or promoted based on inaccessible evidence.

## Bugs fixed in this review

| Finding | Change | Regression evidence |
| --- | --- | --- |
| Active union matched by teams only, including different dates and duplicate rows | Require known equal Eastern game dates and unique ordered matchups in each source; preserve unmatched rows with comparison unknown | `tests/test_feeds.py`: different-day/missing-date and duplicate-source tests |
| ESPN UTC dates and NBA Eastern dates were not on the same calendar | Convert timezone-aware ESPN tipoffs to America/New_York; NBA uses scoreboard date or UTC-tipoff fallback when game date absent | Eastern midnight/winter/summer and NBA fallback tests |
| Only one provider's game status/clock and ID survived in the normalized row | Retain each provider's own ID/date/status/period/clock under its score entry | Provider-context test; engine copies scores into investigation observations |
| Summary fallback could associate the wrong same-team game | Match summaries by unique ESPN event ID, not team pair | Existing joined and single-source runner tests |
| Failed summary fallback returned `None`, which the arithmetic checker could receive as JSON | Skip absent payloads, leaving the check unknown, not consistent | Failed-summary test |
| Summary recheck lookup used ESPN ID but stored checks used NBA row ID | Look up the source-specific ID when the row-key lookup misses | Recheck test verifies unchanged score waits and changed score is due |
| A row marked final could establish a final baseline for a secondary feed still marked live | Use each provider’s own status for final-revision tracking; legacy rows retain fallback behavior | Provider-final-status engine test |
| Documentation asserted no official correction API exists without establishing that universal claim | State only that none has been verified or integrated by this project | `ALERTING.md` §3.1 |

Fail-closed matching intentionally sacrifices some coverage to avoid inventing a
comparison. Unknown-date or ambiguous rows remain visible, but are not compared.
Provider clocks are evidence for investigation, not automatically synchronized.

## Outstanding irregularities and limitations

1. **Primary source coverage:** committed `data/live-feed.json` is degraded.
   NBA endpoint availability must be checked from the production collector;
   a sandbox restriction does not establish NBA service availability.
2. **Evidence loss:** `monitor/engine.py` truncates event observations to first
   3/latest 20 and comparison checks similarly. Response hashes are retained,
   not raw HTTP bodies. Hashes cannot reconstruct missing evidence. Git history
   is useful but is not a guaranteed full polling archive.
3. **Detection identity:** when only ESPN answers the row uses its ID; when NBA
   returns it uses the NBA ID. Investigations can split across provider recovery.
   Durable canonical game IDs and alias migration remain needed; no retrospective
   merge should be guessed.
4. **Sampling:** sources are fetched sequentially. A common poll timestamp is
   not each provider's publication time. Two consecutive differences can still
   be ordinary latency. Best-effort scheduling can miss brief discrepancies.
5. **Post-final monitoring:** current live fetching is today's scoreboards.
   Once games disappear, the six-hour summary-recheck rule cannot revisit them.
   A persisted post-final watch queue is required for next-day corrections.
6. **Attribution:** a score difference does not establish whether the official
   record, secondary feed, display, or timing was wrong. PBP's latest scoring play
   is context, not a proven cause. Two sources can reproduce the same error.
7. **Research:** root dashboard has 2 seed cases; historical catalog has 14
   entries (12 `verified-partial`, 2 unverified, **0 fully verified** per its own
   schema). They overlap; do not add the counts. The Melton player-total dispute
   and unidentified 213/214 report remain unresolved. Legacy data flagged by
   `VERIFICATION.md` are not a canonical verified list.
8. **Statistics:** collection shares are not league-wide rates. No complete
   monitored-game denominator exists. Durations are sampled observation windows,
   not exact error lifetimes. Rarity of 213/214 cannot currently be estimated.
9. **Notifications:** issue creation does not guarantee a person received email
   or push; GitHub subscription settings govern that. Webhook delivery requires
   a configured destination. Crash/retry duplicate-delivery behavior needs a
   production drill, not only mocks.
10. **Storage and operations:** git-backed ledgers are not a scalable database,
    and Pages is only a static viewer. A production collector needs independent
    heartbeat monitoring, retry/backoff, bounded costs, retention, and licensing
    review. The in-process monitor cannot report its own failure to start.

## Next sessions: acceptance-driven plan

### Priority 0 — trustworthy evidence and delivery

- Configure a durable, append-only object store/database outside Git. Save raw
  responses, SHA-256, URL, request start/end UTC, HTTP result, source timestamp
  when supplied, and normalized observation. Test retrieval/hash verification
  after restart and prevent mutation of existing objects. Publish safe excerpts
  and direct evidence references subject to provider terms.
- Run a clearly labeled synthetic end-to-end notification drill in a test
  channel. Verify issue/webhook receipt, retry, dedupe, recovery and closure;
  preserve receipts without representing test data as real NBA findings.
- Probe authorized production NBA access and record exact diagnostics. If
  unavailable, evaluate licensed providers rather than bypass access controls.
- Choose Actions-only Pages deployment; confirm one deployment per release.

### Priority 1 — coverage and false-positive controls

- Introduce canonical game identity with NBA/ESPN aliases and tested migration
  across single-source outages, timezone boundaries, duplicates and recovery.
- Persist a configurable post-final queue (proposed: 24/48/72-hour checks).
  Test corrections after a game vanishes from today's scoreboard, request
  failures, retry limits, and no starvation across busy schedules.
- Store source-local periods/clocks and fetch timestamps in the UI; classify
  asynchronous comparisons separately from comparable final states.
- Add an external heartbeat watchdog and exposure counters: scheduled games,
  games observed, games compared, source uptime, polling gaps and retention gaps.

### Priority 2 — historical completeness and usable statistics

- Re-open every historical citation in a network-capable research session.
  Maintain a claim-by-claim evidence matrix, publisher, verbatim supporting
  excerpt, retrieval date and archive reference where legally permissible.
  Resolve conflicting values without filling unknown fields by inference.
- Unify legacy and current collections with stable IDs, deduplication, source
  provenance, field-level confidence and transparent status mapping.
- Define the league/season population and denominator before estimating rates;
  separate team-total corrections, player attribution and display-only errors.
  Publish median observed duration only with sample size and censoring limits.

The request for zero manual checking is achievable for routine collection,
comparison, triage and notification, but automatic factual confirmation is not
established. Ambiguous evidence must remain unresolved rather than forcing a
conclusion just to close a workflow.
