# Monitor — how continuous detection works

> **Which monitor this describes.** This file documents the earlier
> `scripts/monitor.py` tool (manual/backfill checks for the historical catalog).
> The **active** scheduled monitor is the `monitor/` Python package: see
> `README.md` §2/§8, `ALERTING.md`, and `data/live-feed.json`. Its detector set is
> different and is summarised below so the two are never conflated.

## Purpose

Remove manual checking: an automated job compares **authoritative-leaning** NBA liveData
(box score + play-by-play running score) against the **secondary** ESPN scoreboard feed,
flags disagreements as investigation records, and tracks them to resolution. Humans decide
what becomes a case. The monitor never writes to `data/cases/`.

## Checks (`scripts/monitor.py`, stdlib only)

| Check | Compares | Why it matters |
|---|---|---|
| `cross-source-total-mismatch` | ESPN away/home totals vs NBA-CDN boxscore totals | Direct 213-vs-214-class detector |
| `quarter-sum-mismatch` | Each source's period linescores summed vs its own totals | Catches internal feed corruption |
| `pbp-recompute-mismatch` | NBA PBP final running score vs NBA boxscore totals (final games) | Catches league-internal inconsistency |
| `status-drift` | (reserved) game-state disagreement | Future: live vs final drift |
| `feed-unavailable` | fetch failures | Operational noise — logged, never a “finding” |

Severity: `warn` for final-game mismatches, `info` for live games (feed lag of seconds is
expected and must not page anyone).

## Endpoints

- ESPN: `https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard?dates=YYYYMMDD`
- NBA scoreboard: `https://cdn.nba.com/static/json/liveData/scoreboard/{season}/GameScoreboard_{season}.json`
- NBA boxscore: `https://cdn.nba.com/static/json/liveData/boxscore/boxscore_{gameId}.json`
- NBA play-by-play: `https://cdn.nba.com/static/json/liveData/playbyplay/playbyplay_{gameId}.json`

Games are matched across sources by normalized team tricodes (aliases handled, e.g. NO→NOP).

## Investigation lifecycle (`data/investigations.json`)

```
detected → investigating → correction-observed | explained-no-error → resolved
                                                   ↘ escalated-to-case (human only)
```

- The monitor creates (`detected`), refreshes (`last_seen_utc` + history) and auto-advances to
  `correction-observed` when sources agree again (transient lag cleared *or* a real correction
  landed — a human must determine which before `resolved`).
- `explained-no-error`, `resolved`, and `escalated-to-case` are set by humans (or by a human
  reviewing an auto-advance). Escalation means: open a `data/cases/` record and link it.
- Dedupe key: `(game_date, game_key, check)`.

## Schedule (`.github/workflows/monitor.yml`)

- Every 20 minutes during typical NBA game windows (22:00–05:59 UTC daily) — live detection.
- Nightly backfill sweep of the previous 7 days (catches next-day corrections like the 2024/2025 FT cases).
- Manual dispatch anytime (`workflow_dispatch`).
- On new/updated records: commits `data/investigations.json` + rebuilt `docs/data/` back to `main`.
  (If `main` is branch-protected against direct pushes, either allow the Actions bot to push or
  switch this step to opening a PR — see `.github/workflows/monitor.yml`.)

## Runbook

1. **New `detected` record on a FINAL game** → verify both sources in a browser within the hour;
   screenshot/archive both; if it persists >30 min, move to `investigating` and start a case draft.
2. **New `detected` on a LIVE game** → wait for final; most clear on their own (feed lag). Do not
   open a case on live-only disagreement.
3. **`correction-observed`** → determine: transient lag (→ `explained-no-error` + note) or real
   correction (→ verify against league notice, then `escalated-to-case` or `resolved` with note).
4. **Recurring `feed-unavailable`** → check endpoint health; update URLs/parsers (feeds change
   without notice); never treat feed absence as a score finding.
5. **What the monitor cannot see:** arena scoreboards, TV bugs, in-arena PA. Display-only errors
   (like MIN@NOP 2018) need human spotters — report via issue/PR with footage.

## Offline testing

`python3 scripts/monitor.py --self-test` runs the 213-vs-214 synthetic fixture with no network.
CI runs it on every push/PR. Live-fetch paths are exercised by the scheduled workflow.

---

## Active monitor (`monitor/` package) — detector set as of 2026-10-07

| Detector | Fires when | Alert severity |
|---|---|---|
| `cross_source_score_mismatch` | any two reachable sources publish different scores for the same game for two consecutive polls | high |
| `final_score_feed_revision` | a source changes a score it had already published as final (per-source key `{source}:{game}`) | critical |
| `final_score_internal_inconsistency` | one provider's final does not follow from its own box-score components (`2*(FGM-3PM)+3*3PM+FTM`) | critical |
| `source_unavailable` | a source has not answered for ≥15 minutes (authoritative dispatches immediately; comparator dispatches at ≥60 minutes) | high / medium |

Behaviour added in this session, with tests:

- **Union snapshots.** Rows are built from every source that answered, not only the primary
  feed, so a primary-feed outage no longer blanks the published game list and no longer stops the
  single-provider arithmetic checks (`tests/test_runner.py::test_single_provider_arithmetic_check_runs_while_nba_feed_is_down`).
- **Coverage gaps.** An outage window is recorded and published; "no alerts" during an outage is
  never presented as a clean result.
- **Alert ledger + delivery.** `data/alerts.json` (lifecycle, evidence, arithmetic, review steps,
  dispatch state) and `data/alert-dispatch-log.json` (append-only). Delivery is a GitHub issue
  created by `python3 -m monitor --dispatch-alerts --apply`, optionally mirrored to
  `SCORING_DISCREPANCY_WEBHOOK_URL`. Unconfigured channels are logged as `skipped`, never assumed.
- **Commit churn control.** The scheduled runner rewrites `data/live-feed.json` only when the
  material signature changes, and rewrite of the ledger is gated on occurrence milestones
  (1, 3, 12, 48, 144, 720) plus lifecycle/dispatch changes.
