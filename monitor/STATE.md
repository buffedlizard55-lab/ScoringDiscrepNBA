# Current monitor — architecture, schedule, and operator notes

This runbook describes the active monitor in `monitor/` and its five-minute GitHub Actions workflow. The similarly named `scripts/monitor.py` is a retained historical/backfill tool and is **not** the active schedule.

## Purpose and source scope

The active monitor observes the NBA public live scoreboard and compares its game totals with ESPN's public NBA scoreboard. NBA is the primary feed being observed; it is not assumed infallible. ESPN is a secondary comparison feed. The monitor stores mismatches and post-final NBA-feed revisions as unverified investigations. It does not write confirmed cases into `data/reviewed-cases.json` or `data/cases/`.

Configured endpoints:

- NBA scoreboard: `https://cdn.nba.com/static/json/liveData/scoreboard/todaysScoreboard_00.json`
- NBA play-by-play, fetched for score mismatches: `https://cdn.nba.com/static/json/liveData/playbyplay/playbyplay_{game_id}.json`
- ESPN scoreboard: `https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard`

Games are paired using normalized home/away team abbreviations. Ambiguous or incomplete matches are not guessed. If scores differ, the latest explicitly marked NBA scoring action may be attached as context; the monitor does not identify it as the cause.

## Checks and lifecycle

- `cross_source_score_mismatch`: compares both teams' NBA-feed and ESPN-feed totals when all four values are present.
- `nba_final_feed_revision`: compares later NBA final-feed values to the monitor's first saved final baseline.
- Missing values and source outages remain health/coverage failures; they are not changed to zero or interpreted as agreement.

Lifecycle for a cross-source mismatch:

```text
detected → investigating (2 consecutive mismatch polls)
         → monitoring_for_convergence (1 complete agreement)
         → resolved (2 consecutive agreements; still unverified)
```

A final-feed revision is stored as `change_observed_unverified`. Automated agreement closes only the observed mismatch window; it does not prove which earlier value was correct, that the NBA record changed, or why it changed. Investigations remain distinct from human-reviewed cases.

## Alerts and publication

`.github/workflows/pages-and-monitor.yml` runs every five minutes (best effort), polls both feeds, saves material changes, creates/refreshes GitHub issue alerts for persistent mismatches and final-feed revisions, and publishes the current dashboard artifact. A mismatch requires two consecutive comparable polls; an unavailable source, missing game, or incomplete score is recorded as a streak-breaking comparison. The notifier requires the workflow's `issues: write` permission and uses the repository token; no external webhook secret is needed. A failure in the issue transport is a warning and does not discard monitor state or block Pages publishing.

The issue channel is not a guaranteed personal notification. A user must receive GitHub notifications according to repository watch/subscription settings. Slack/Discord/email/SMS or closed-tab web push requires a configured delivery backend and secrets. Details: [`docs/ALERTING.md`](../docs/ALERTING.md).

Freshness fields:

- `last_poll_attempt_at`: UTC time of this monitor attempt, whether or not both sources responded.
- `last_successful_comparison_at`: last time both NBA and ESPN payloads parsed successfully; retained through degraded polls.
- `games[].observed_at`: current monitor observation time for the published game data.
- `last_updated_at`: time of the last material feed-state change, not every poll.

The scheduled run deploys a fresh static artifact each time so clocks and poll timestamps can update without adding heartbeat-only commits. `scripts/monitor_diff.py` ignores poll-time/clock-only fields when deciding whether to commit to `main`; scores, source health, investigation history, and other material updates are committed. The workflow ignores monitor-only commit pushes to avoid a redundant second Pages deployment.

## Operator checks

1. Check the dashboard health label, NBA/ESPN health chips, latest poll attempt, and last successful paired-comparison time.
2. If a source is unavailable/invalid, treat the displayed game list as stale or incomplete; an empty list is not evidence of no games or discrepancies.
3. Inspect a GitHub issue alert and open the linked feed URLs/monitor ledger. Confirm the matchup before comparing scores.
4. Check official NBA notices/gamebook/box score and independent reliable reports before deciding the NBA record or a provider was wrong.
5. Keep unresolved and disputed values explicit. Preserve all original observations. Do not close an issue or promote a case based solely on two feeds agreeing again.

The monitor is not streaming. Cron jobs can be delayed/skipped, endpoints can change or fail, the five-minute cadence can miss brief differences, feeds can share an error, and broadcast/arena display-only faults are outside its sources. Inspect the workflow run and timestamps before calling the feed current. See `ROADMAP.md` for the broader evidence and historical coverage gaps.

## Offline tests

```bash
python3 -m unittest discover -s tests -v
python3 -m monitor --check-data
node tests/dashboard-smoke.js
node tests/github-alerts-smoke.js
```

The fixtures include a synthetic 213-vs-214 mismatch to verify detection behavior; it is test input, not evidence that the unidentified project lead has been resolved.
