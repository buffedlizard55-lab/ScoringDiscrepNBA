# Investigation review and resolution workflow

The current monitor compares the NBA public scoreboard feed with ESPN. A feed difference is an unverified observation—not an accusation, not proof the NBA record is wrong, and not automatically a historical case. The monitor preserves observations and opens GitHub issue alerts for persistent candidates; source-backed research still requires evidence review.

## Current data locations

- `data/live-feed.json` — latest published score/health snapshot and poll heartbeat for the dashboard.
- `data/monitor-state.json` — append-only investigation observations, score baselines, and current investigation states.
- `data/reviewed-cases.json` — two evidence-reviewed root-dashboard examples; separate from the monitor ledger.
- `data/cases/*.json` and `data/cases.json` — preserved earlier historical collection; see `VERIFICATION.md` for its partial statuses and audit flags.
- `data/leads.json` — explicitly unverified leads, including the unidentified 213/214 report; excluded from confirmed counts.

Do not confuse the current root monitor with the retained `scripts/monitor.py` historical/backfill tool or the legacy `data/investigations.json`/`docs/data/monitor/current.json` snapshots.

## Automated states

- `detected` — first saved, parseable source disagreement.
- `investigating` — the same source mismatch was present on at least two consecutive comparable polls. A GitHub issue alert is eligible at this point.
- `monitoring_for_convergence` — one complete matching poll followed the disagreement; the mismatch may have cleared, but the monitor waits for another matching poll.
- `resolved` — two consecutive comparable polls agreed. This closes only the observed feed-mismatch window; `verification_status` remains `unverified` and the cause is not established.

A poll with an unavailable source, an unreturned game, or incomplete scores is recorded as an incomplete comparison and breaks both mismatch and convergence streaks. It cannot count as agreement.
- `change_observed_unverified` — the NBA scoreboard feed's value changed after a final-score baseline was recorded. This is an immediate alert candidate, not proof of an official-record correction.

A missing score, unparseable feed, source outage, ambiguous game match, or one-poll mismatch never becomes a matching zero or auto-clears an open event. A failed NBA poll preserves the last saved games as stale and makes the feed status degraded.

## GitHub issue alerts

`.github/workflows/pages-and-monitor.yml` runs the poll on a five-minute GitHub Actions schedule. The notifier in `scripts/github_alerts.js` creates one issue per persistent mismatch or final-feed revision, deduplicates using a stable hash of the investigation ID, refreshes an existing open issue, and comments when feed agreement is later observed. It never closes an issue on its own and respects a human-closed issue. GitHub delivery is subject to watch/notification settings; this is not email, SMS, or guaranteed push delivery. See [`ALERTING.md`](ALERTING.md) for thresholds, freshness semantics, and limitations.

## Evidence-review procedure

1. **Confirm the game match.** Check date, home/away orientation, NBA game ID, and whether each provider returned the same game. If ambiguous, leave it under investigation; do not guess.
2. **Open both source responses.** Review the NBA scoreboard, ESPN scoreboard, and the game-specific NBA play-by-play when attached. A nearby/latest play is context only, not proof of cause.
3. **Preserve observations.** Keep the first and subsequent poll values/timestamps. Add independently recovered URLs, archived responses/screenshots, capture times, and source publication times only when available. Never replace the original value with a corrected one.
4. **Check the official record and independent evidence.** Look for an NBA correction notice, official box score/gamebook, official play-by-play, or reliable independent reporting. Separate NBA record changes from secondary-provider corrections or delays.
5. **Classify conservatively.** Record whether the NBA record was wrong, only a secondary feed was wrong/delayed, multiple feeds shared an issue, or the case remains unresolved. State what the evidence proves and what is unknown.
6. **Document the review** in a pull request with reviewer, UTC review time when known, direct evidence links, disposition, and remaining questions. Feed agreement alone is not a human-confirmed explanation.
7. **Promote only supported incidents.** Add a source-traceable record to the appropriate research collection under its schema, retaining originally reported, corrected, and final official values. Link the monitor investigation to the case. Do not mark a candidate confirmed merely because it appeared in an issue.

## Operational notes

The monitor timestamps are UTC poll/observation times, not provider update times. `last_poll_attempt_at` describes the latest attempt; `last_successful_comparison_at` describes the latest time both feeds parsed; `last_updated_at` is the last material snapshot change. The five-minute schedule can be delayed or skipped. Inspect source-health status, heartbeat, successful-pair time, and the linked Actions run before calling the feed current.

The monitor cannot see arena/TV scorebugs absent from its feeds, detect an error shared by both feeds, recover a discrepancy shorter than its polling interval, or establish the cause of a score change. It does not autonomously convert a candidate into a verified case. See [`ALERTING.md`](ALERTING.md) and [`ROADMAP.md`](../ROADMAP.md).
