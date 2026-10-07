# Candidate investigation and resolution workflow

The scheduled monitor handles routine score comparisons. People review only candidates it flags; an automated feed mismatch is never promoted to a confirmed NBA error automatically.

## Separate lifecycles

A record keeps three states separate:

- `monitorStatus`: `active_source_divergence` or `feed_converged`. This describes whether NBA and ESPN's latest comparable score observations still differ. A failed/missing source does not mean convergence.
- `investigationStatus`: `needs_review`, `under_review`, or a documented terminal disposition (`resolved_nba_correction`, `resolved_secondary_source_only`, `resolved_feed_or_match_error`, `closed_unresolved`). This is changed only by a source-backed review, not by polling.
- `reviewStatus`: `unverified` by default. Set to `confirmed`, `secondary_source_only`, `feed_or_match_error`, or `reviewed_unresolved` only when the corresponding terminal disposition has been supported by review evidence.

The monitor may append score snapshots and change `monitorStatus`/`monitorNote`. It must preserve the human investigation status, reviewer, evidence, and resolution fields if they exist. Even if the feeds reconverge, an unreviewed issue remains `needs_review` until its source history is assessed. If a new divergence episode appears after a terminal review, the previous disposition is copied into `reviewHistory` and the fresh episode reopens as unverified/`needs_review`.

## Review procedure

1. Match the candidate to the correct NBA game using team orientation, date, and game ID. Record any uncertain match.
2. Capture the NBA and secondary-provider score/clock observations and their UTC capture times. Preserve source URLs or archived copies when available; do not overwrite earlier values.
3. Inspect official NBA box-score/play-by-play or a league correction notice plus an independent report. Treat nearby play-by-play context as a lead, not proof that the play caused the mismatch.
4. Select a disposition only when its evidence supports it:
   - `resolved_nba_correction` → `reviewStatus: confirmed` only if the NBA confirms or its preserved official record establishes a correction;
   - `resolved_secondary_source_only` → `reviewStatus: secondary_source_only` when the NBA record is supported and a secondary source is shown to be stale/incorrect;
   - `resolved_feed_or_match_error` → `reviewStatus: feed_or_match_error` when a source endpoint, parser, or game match caused the divergence;
   - `closed_unresolved` → `reviewStatus: reviewed_unresolved` when review is complete but the correct observation cannot be established;
   - `under_review` keeps `reviewStatus: unverified` while evidence gathering continues.
5. Update `data/monitor/candidates.json` in a reviewed pull request. Add/update `investigationStatus`, `reviewStatus`, `reviewer`, `reviewedAt` (UTC, or null if unknown), `resolution` (plain-language explanation), and `resolutionSourceIds` pointing to `data/sources.json`. Leave unknown values null. A terminal disposition needs a reviewer, review time, resolution note, and source IDs; the offline validator checks that contract.
6. If a source-backed NBA correction is confirmed, add a separate curated entry to `data/cases.json` with original/corrected/final values, timestamps, claim-level sources, and limitations; the automated candidate remains as its detection history.

This repository is static, so review changes are made through a normal source-control change rather than an in-browser admin form. Routine scoreboard comparisons, polling, and candidate creation are automated; human review is reserved for true source divergences.
