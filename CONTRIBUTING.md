# Contributing — evidence-first, no-hallucination workflow

## Start here, every session

Read [`README.md`](README.md) first. It contains the founding brief, Core Values, operating rules, and current architecture. Then read [`VERIFICATION.md`](VERIFICATION.md) for source standards and known audit flags, plus [`ROADMAP.md`](ROADMAP.md) for limitations.

**Maximize P(Win):** choose the change that increases reliability and evidence quality while controlling false positives, secret exposure, and operational cost. **Own the Outcome:** run the tests, inspect the diff, update the runbook, and state any remaining limitation; do not stop at code that merely appears complete.

## Where active and retained data live

- `data/reviewed-cases.json` — evidence-reviewed seed shown on the current root dashboard.
- `data/leads.json` — research leads, including the unidentified 213/214 report; leads are excluded from confirmed-case counts.
- `data/live-feed.json` and `data/monitor-state.json` — current feed snapshot and automated, unverified investigation history.
- `data/cases/*.json` — earlier historical catalog records checked by `scripts/validate.py`.
- `data/discrepancies.json`, `src/`, `research/`, and `scripts/monitor.py` — retained legacy/backfill material. Do not bulk-import or describe it as current/verified without a fresh audit.

For a current-case change, edit only the relevant canonical data file after source review; do not hand-edit generated historical bundles (`data/cases.json`, `docs/data/`, or `data/stats.json`) when a generator owns them.

## Research and correction workflow

1. Identify the game and event from reliable evidence; if any key fact is not supported, preserve it as `null`/unknown and add an open question.
2. Add direct HTTPS source URLs and a `confirms`/support description for each factual claim. Distinguish official NBA material from independent reporting and provider page observations.
3. Preserve the original observation, correction, final official value, observation/update times, source disagreement, and unknown cause. Never overwrite history.
4. Classify whether the NBA record was wrong, a secondary provider was wrong/delayed, multiple feeds shared a problem, or the evidence remains disputed. A score-feed mismatch is not proof of an NBA error.
5. Keep the 213/214 and Kevin Porter Jr. leads unverified until unique games and source histories are established. Do not infer missing game IDs, dates, teams, totals, player values, or causes.
6. Re-run validation and tests below. Review generated changes and explain coverage, confidence, and limitations in the pull request.

For an automated monitor candidate, follow [`docs/INVESTIGATION_WORKFLOW.md`](docs/INVESTIGATION_WORKFLOW.md) and [`ALERTING.md`](ALERTING.md). GitHub issue notifications are unverified candidates; they must not be promoted to historical cases without independent evidence.

## Local checks

```bash
python3 -m unittest discover -s tests -v
python3 -m compileall -q monitor scripts src tests
python3 -m monitor --check-data
python3 scripts/validate.py
python3 scripts/monitor.py --self-test
node --check assets/app.js
node --check docs/app.js
node tests/dashboard-smoke.js
```

If historical case files or generated bundles change, also run:

```bash
python3 scripts/compute_stats.py
python3 scripts/build_site_data.py
```

If live data generation changes, verify offline with fixtures. Do not treat a local network failure, an empty feed, or a successful CI run as proof that live monitoring is healthy; inspect the published feed health and the scheduled Actions run. See [`monitor/STATE.md`](monitor/STATE.md).

## Notifications, credentials, and security

The scheduled monitor can create GitHub issue alerts using the workflow's scoped token. Do not add secrets to JSON, source control, or chat. External notification destinations (email, Slack, Discord, SMS, push) require maintainers to configure repository/environment secrets and a delivery service; document rate limiting, deduplication, retries, and failure behavior before enabling one.

## Pull request checklist

- [ ] Change is on the session branch supplied by Arena; never switch branches.
- [ ] README brief and operating values remain intact.
- [ ] Every new historical fact has a direct source and a line-by-line verification note.
- [ ] Unknown or conflicting fields remain explicitly uncertain.
- [ ] All relevant tests/validators pass; screenshots/URLs/Commands are included for review.
- [ ] Data status, monitor freshness, alert limits, and generated-file behavior are described honestly.
