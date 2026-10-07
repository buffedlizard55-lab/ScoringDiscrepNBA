# Investigation review and resolution workflow

Routine scoreboard comparisons are automated. A feed difference is an unverified source observation, not an accusation and not proof the NBA record is wrong. Only confirmed, source-backed research becomes a canonical case.

## Separate the monitor state from the research conclusion

Records live in `data/investigations.json`. The latest published score comparison and feed-health snapshot lives in `data/monitor/current.json` and is mirrored to `docs/data/monitor/current.json` for the Pages site.

- `detected`: the monitor recorded a source disagreement or an internal data check failure.
- `investigating`: a person is reviewing the source history.
- `correction-observed`: a later run completed the same scoped check and no longer saw the mismatch. This is an operational convergence, not proof of a correction or an explanation.
- `explained-no-error`: a person established that the discrepancy was a transient delay, source/parser/game-match issue, or another non-NBA-record error, and documented the evidence.
- `resolved`: a person has documented the outcome and its source basis.
- `escalated-to-case`: a person promoted a source-confirmed incident into `data/cases/` and linked the case ID.

Feed outages, unmatched games, and missing scores are shown in the latest snapshot, never converted to zeroes or treated as a cleared discrepancy. Each investigation also stores a `check_scope`; a check on one source/team side cannot clear a different scoped check.

## Review procedure

1. **Confirm the game match.** Check team orientation, date, and NBA game ID. If ambiguous, keep it under investigation; do not infer a match.
2. **Preserve source observations.** The monitor retains the first evidence and appends timestamped observations when values or severity change. Add manually recovered source URLs, archived responses/screenshots, and capture times without deleting earlier evidence. Repeated identical observations update `last_seen_utc` and a repeat count.
3. **Check the official record and independent reporting.** Use the NBA correction notice, box score, and play-by-play where available. Compare secondary-provider snapshots separately. Nearby play-by-play is context, not proof of cause.
4. **Classify the outcome with explicit evidence.** Decide whether the NBA record was wrong, only a secondary source was wrong/delayed, the feeds shared an issue, or the result remains unresolved. Preserve uncertainty and disputed positions.
5. **Document the human review** in a pull request: reviewer, review timestamp (UTC when known), source URLs, plain-language disposition, and remaining questions. Do not move a record to `resolved` solely because two feeds agree again.
6. **Promote only supported incidents.** For an NBA correction or confirmed secondary-source error, create a separate `data/cases/<date>-<slug>.json` record with original, corrected, and final values, timeline, direct sources, and limitations. Then mark the investigation `escalated-to-case` and add a case link/ID while retaining its observation history.

## Roles and limits

The monitor performs recurring scoreboard checks and creates/updates investigation records without user data entry. The static Pages site shows the latest committed poll; GitHub Actions schedules may be delayed, so it is not a streaming feed. Human review is reserved for flagged mismatches and is required before a candidate becomes a researched case.
