# Alert detection and notification: what is possible, what is not, and why

This document answers one question honestly: **can this project detect scoring
discrepancies automatically and notify someone?** Short answer: **yes for
candidate detection and notification, no for automatic confirmation** — and the
difference matters, because a mismatch between two published numbers is not the
same thing as the NBA's official record being wrong.

Everything below is written so a reader with no knowledge of this project can
check it from the repository files and the cited links. Nothing here is a claim
about any specific game unless a link is attached.

- Live alert ledger: [`data/alerts.json`](data/alerts.json)
- Delivery log: [`data/alert-dispatch-log.json`](data/alert-dispatch-log.json)
- Investigation ledger: [`data/monitor-state.json`](data/monitor-state.json)
- Published feed snapshot + source diagnostics: [`data/live-feed.json`](data/live-feed.json)
- Site panel: the **Alerts** section of the [dashboard](index.html)

---

## 1. Bottom line

| Question | Answer | Why |
| --- | --- | --- |
| Can we detect that two published sources disagree on a score? | **Yes**, when two feeds are both reachable | [`monitor/feeds.py`](monitor/feeds.py) unions every source's games into one row per game and flags disagreement; the latest saved poll had only ESPN reachable, a historical observation rather than current health |
| Can we detect that a source changed a score it had already published as final? | **Yes** | [`monitor/engine.py`](monitor/engine.py) keeps a per-source baseline of the first final score it saw |
| Can we detect that one provider's final score contradicts the box score that same provider publishes? | **Yes** | [`monitor/consistency.py`](monitor/consistency.py) recomputes `2 × (FGM − 3PM) + 3 × 3PM + FTM` from the provider's own cells. This detector works while the primary feed is down, because rows are now built from every source that answered |
| Can we notify someone automatically? | **Yes**, as GitHub issues with the repository's `GITHUB_TOKEN`, and optionally to a webhook | [`monitor/dispatch.py`](monitor/dispatch.py) + the scheduled workflow |
| Can the system confirm that the NBA's *official* record was wrong? | **No** | No dedicated official correction feed has been verified or integrated here; see §3.1 |
| Can it see arena scoreboard / TV graphics errors? | **No** | Those are not published through the feeds we can read; see §3.5 |
| Can it find historical cases before this monitor existed? | **No, not automatically** | We only observe feeds forward in time; historical cases come from archive research; see §3.4 |
| Does "no alerts" mean "no discrepancies"? | **No** | Outages, poll delay, and consistent errors all produce silence; see §3.6 |

---

## 2. How the running system works

```
github.com Actions (cron */5 * * * *)        ┌───────────────────────────────┐
        │                                    │ data/live-feed.json           │ published snapshot
        ▼                                    │ data/monitor-state.json       │ investigation ledger
python3 -m monitor --live                    │ data/alerts.json              │ alert ledger
 ├─ NBA liveData scoreboard  (fallback header profiles)   │ data/alert-dispatch-log.json  │ delivery log
 ├─ ESPN scoreboard                                    └───────────────────────────────┘
 ├─ ESPN summary box score for un-checked finals  ◄── committed to main by the workflow
 └─ NBA play-by-play for games whose feeds disagree
        │
        ▼
python3 -m monitor --dispatch-alerts --apply   →  GitHub issue per pending alert (+ optional webhook)
```

Four detectors feed the alert ledger:

1. **`cross_source_score_mismatch`** — two reachable sources disagree on a live
   or final score. Recorded on the first poll, but **alerted only after two
   consecutive polls**, because a single poll frequently catches one provider
   mid-update.
2. **`final_score_feed_revision`** — a source changed a score it had already
   served as final. This is the closest automatic signal to a scoring
   correction and it is alerted as **critical** immediately. It still does not
   say *why*: the league may have corrected the record, or the provider may have
   been wrong and fixed its own feed.
3. **`final_score_internal_inconsistency`** — a provider's published final does
   not follow from the box-score components in its own summary payload.
   Alerted as **critical**, with the full arithmetic in the alert and the issue.
4. **`source_unavailable`** — a feed could not be polled for 15 minutes or more
   (authoritative source: high severity and notified; comparator: medium until
   it has been down an hour). While a source is down, no comparison against it
   can run, so the outage is published as a **coverage gap** instead of being
   silently recorded as a clean result.

Lifecycle: every alert is `open` until the automated condition stops being
observed or a reviewer closes it (`python3 -m monitor --resolve-alert <id>
--note "..."`). A reviewed closure stays closed across identical polls; materially
changed evidence or a new condition generation can reopen it. The ledger is
append-only in spirit: closures keep the earlier observations, the lifecycle
entries, the review note, and the delivery record.

---

## 3. Limitations that are real today

### 3.1 No dedicated official correction feed has been verified here

The NBA announces scoring corrections as prose: game recaps, league statements,
and posts from the official account in the linked seed cases. This project has
not verified or integrated a dedicated correction endpoint; that does not prove
no such product exists. With the currently integrated feeds, the
system can produce a *candidate* and attach evidence, but a human (or an agent
under review) must confirm whether the league's record changed. The two
confirmed examples in this project both required reading a published statement:
the [NBA.com recap for October 2024](https://www.nba.com/news/nba-finds-scoring-error-warriors-blazers)
and the [NBA Official post for November 2025](https://x.com/NBAOfficial/status/1987199646020870516).

### 3.2 The primary feed (NBA CDN) is not reachable from the scheduled runner

This was the largest source-coverage limitation in the latest reviewed snapshot;
its status is observed in that artifact, not assumed to persist unchanged:

- The scheduled run recorded at
  [commit `99cae832`](https://github.com/buffedlizard55-lab/ScoringDiscrepNBA/commit/99cae8322239b52486fe26777fa70f33565f3959)
  ([Actions run 37616762038](https://github.com/buffedlizard55-lab/ScoringDiscrepNBA/actions/runs/37616762038))
  saved `nba: {"status": "unavailable", "error": "Could not fetch or decode upstream JSON: HTTPError"}`
  while ESPN was `ok`.
- `https://cdn.nba.com/robots.txt` answered with an S3 `AccessDenied` error
  document rather than a robots file, and the scoreboard object at
  `https://cdn.nba.com/static/json/liveData/scoreboard/todaysScoreboard_00.json`
  returned HTTP 500 to a separate fetch service during an earlier probe. These
  are observations of those clients at those times; they do **not** establish
  the cause or the league's access policy.
- The newest scheduled run in the reviewed GitHub Actions history is
  [37663924132](https://github.com/buffedlizard55-lab/ScoringDiscrepNBA/actions/runs/37663924132)
  (started `2026-10-07T18:03:53Z`). Its committed feed snapshot is timestamped
  `2026-10-07T18:04:06Z`: ESPN was `ok`; the NBA scoreboard was `unavailable`
  with HTTP 403 under both `monitor` and `browser` profiles; five ESPN-only game
  rows were published, with cross-source comparison unavailable. This is a
  historical snapshot, not current endpoint health. See the snapshot's
  `source_health`, `source_diagnostics`, and `detector_status` fields in
  [`data/live-feed.json`](data/live-feed.json).

**Mitigations in place:** the monitor tries a second, browser-like header
profile and publishes every attempt (profile, outcome, HTTP status, error) under
`source_diagnostics` in `data/live-feed.json`, so the snapshot can show what the
CDN answered instead of a bare "HTTPError". It also builds its published rows
as the **union of every source that answered** rather than from the primary
feed alone: with the NBA feed down, ESPN games are still published (each row
marked `Not compared`), the ESPN final-score baseline is still tracked, and the
single-provider arithmetic check still runs — this is proven by
`tests/test_runner.py::test_single_provider_arithmetic_check_runs_while_nba_feed_is_down`
and by an end-to-end fixture run that opens a critical alert with a pending
notification while the NBA feed is simulated down.

### 3.3 Poll cadence cannot see most transient errors

The workflow requests every 5 minutes, which is the documented minimum
([GitHub Actions schedule event](https://docs.github.com/actions/using-workflows/events-that-trigger-workflows)).
The same documentation states that scheduled runs **can be delayed, and under
load some queued jobs may be dropped** — a dropped run leaves no trace. The
reviewed workflow history returned 10 runs, only 2 of them scheduled:
`2026-10-07T11:49:59Z` and `2026-10-07T18:03:53Z`, about 6 hours 14 minutes
apart. That observed cadence is much sparser than the requested cron and is a
material blocker, not just a theoretical GitHub caveat.

Practical consequence: a divergence that appears and disappears inside a few
minutes may never be sampled, and a "delay" of a few minutes cannot be
distinguished from a data error. The system detects **persistent divergence**
and **post-final revisions**, not every live blip. The static dashboard's
`last_updated_at` is the last material snapshot change, not a poll heartbeat;
check Actions run history to know when the workflow most recently attempted a
poll. An unchanged run does not deploy a fresh timestamped page.

### 3.4 No historical archive, so nothing is retroactive

The monitor stores only what it observes from the moment it runs. It cannot
re-derive what a feed showed in 2019. Historical cases must be researched from
published records, which is what `data/cases/*.json`, `docs/`, and
`data/reviewed-cases.json` do. Feed snapshots that were never captured cannot be
recovered later.

### 3.5 Some error classes are invisible to feed comparison

An in-arena scoreboard or TV graphic error (for example the December 2018
Timberwolves–Pelicans display issue in this collection) never appears in an HTTP
feed. Those cases are only discoverable from reporting, so they are documented
research records, not monitor alerts.

### 3.6 Absence of alerts is not absence of discrepancies

Three different situations all produce "no alerts":

1. a source was unreachable, so no comparison could run (recorded as a coverage gap);
2. the poll happened to miss the window in which the numbers differed;
3. an error was propagated consistently — the provider's scoreboard and its own
   box score are wrong in the same direction, so the arithmetic check reports
   `consistent` (there is a test that keeps this blind spot explicit:
   `tests/test_consistency.py::EspnSummaryTests::test_a_consistently_propagated_error_is_a_documented_blind_spot`).

### 3.7 Correlated upstream data is weak evidence

ESPN, Yahoo, and most third-party scoreboards ingest data from the same small
set of upstream providers. When two of them disagree, that is a signal worth
investigating; when they agree, it is **not** independent confirmation. This is
why the project treats "two secondary feeds agree" as weaker than a league
statement.

### 3.8 Delivery is limited to the channels that are actually configured

- **GitHub issues** work with the workflow's own `GITHUB_TOKEN`
  (`issues: write`) and are the default channel. GitHub's own notification
  settings (email, mobile, web) then apply to whoever watches the repository.
  Delivery is only recorded as `sent` when the CLI returns a parseable HTTPS
  issue URL. If the CLI exits successfully but returns no such URL, the result
  is `failed` with an explicitly unknown remote outcome; the dispatcher does
  not retry blindly because that could create duplicate issues. A person must
  inspect the repository before retrying that ambiguous case.
- **Optional webhook**: set the repository secret
  `SCORING_DISCREPANCY_WEBHOOK_URL` to a Slack/Discord-compatible webhook and
  dispatched alerts are mirrored there. If it is not set, the ledger and the
  dispatch log record `skipped` — no channel is ever reported as working when it
  is not.
- **Not implemented** (and not claimed): SMS, phone calls, or email sent
  directly by the monitor. Sending email from Actions requires an external SMTP
  credential, which this project does not hold.

### 3.9 Rate limits, terms, and good behaviour

The monitor makes a handful of requests per poll to public endpoints, with a
descriptive user agent, no scraping of HTML pages, and a cap (`MAX_SUMMARY_FETCHES`)
on per-game box-score requests. Any increase in scope must stay inside each
provider's terms of use, and the repository stores HTTP `ETag`,
`Last-Modified`, and SHA-256 response metadata so claims about what a source
served remain reviewable.

### 3.10 A queued job can still commit to `main`

The scheduled workflow writes `data/*.json` back to `main` with the
`GITHUB_TOKEN`. GitHub documents that pushes made with that token
**do not trigger further workflow runs**
([automatic token authentication](https://docs.github.com/en/actions/security-guides/automatic-token-authentication)),
which is why the workflow now re-runs the data validators *and* the dashboard
smoke test after the poll, inside the same job, before committing. Without that,
a broken machine-written data file could reach `main` with no check ever
running on it — exactly the failure that this review found from the previous
session's scheduled commit.

The monitor keeps outage elapsed minutes in memory for threshold checks but
strips per-poll `last_ok_at` / `unavailable_minutes` fields from the committed
state. Outage alert wording is stable between severity, notification-eligibility,
recovery, and occurrence-milestone changes. This avoids heartbeat-only commits
for an otherwise unchanged source outage; new score observations and coverage
events are still persisted deliberately (`tests/test_runner.py::test_repeated_source_outage_poll_does_not_persist_a_heartbeat_only_change`,
`tests/test_alerts.py::AlertRuleTests::test_source_outage_alert_does_not_change_text_on_every_poll`).

---

### 3.11 Feed matching is a heuristic, not a shared game identifier

The NBA and ESPN adapters do not expose a shared event ID. The monitor now
requires a **known matching Eastern-calendar game date** and a unique ordered
home/away team pair within each source before joining. Duplicate same-day rows
and unknown-date rows remain visible as separate `Not compared` observations;
response order is never used to choose a match. The adapters retain each
provider's event ID, date, status, period and clock alongside its score so
source-local timing can be reviewed (`tests/test_feeds.py` covers cross-date,
unknown-date, duplicate and context-preservation cases).

This date-and-team join is still a best-effort mapping: postponed games,
provider date conventions, or an incorrect date can suppress or create a
*candidate* comparison. A common poll time is not a common provider publication
time, and no mismatch proves which source is right. A provider-supported shared
event key plus durable canonical IDs would improve identity.

## 4. Verifying the system yourself

```bash
# Offline checks (no network): rules, lifecycle, dedupe, delivery, rendering
python3 -m unittest discover -s tests -v
node tests/dashboard-smoke.js
python3 -m monitor --check-data

# Deterministic end-to-end poll from a fixture into a throwaway directory
python3 -m monitor --fixtures <fixture.json> --root /tmp/check
cat /tmp/check/data/alerts.json          # alert ledger with evidence + arithmetic
python3 -m monitor --dispatch-alerts --root /tmp/check        # dry run: prints the plan
```

To see what the next scheduled run will attempt:

```bash
gh run list --workflow="publish-and-monitor" --limit 10   # adjust to the workflow name in your fork
python3 -c "import json;print(json.load(open('data/live-feed.json'))['source_diagnostics'])"
```

---

## 5. What would raise the ceiling

Ordered by expected value per unit of work:

1. **A reachable authoritative feed or a paid/official data licence.** Either
   unblocks true cross-source comparison with the league's own numbers, or a
   provider that publishes corrections.
2. **A second independent comparator that is reachable from CI** (for example
   a different upstream such as a stats vendor rather than another aggregator),
   which would make disagreement meaningful rather than correlated noise.
3. **Archived official box scores per game**, so a correction can be proven by
   diffing the league's own before/after documents instead of inferring it from
   a provider's revision.
4. **A corrections watcher** over the league's statement channels (newsroom RSS,
   official account) that opens an investigation record automatically when a
   correction is published — the notification half of the loop that is
   currently manual.
5. **Higher-frequency sampling during games** (for example a short-interval job
   triggered at tip-off) to shrink the window in which a transient error can
   hide, at a higher request volume.

---

## 6. Statement of scope

The alert ledger records **what was published, by which source, when this
project looked, and how the numbers disagree**. It never asserts that the NBA's
official record was wrong, never asserts a cause, and never deletes the earlier
value. Confirmation requires evidence outside the monitor, and every case that
reaches `confirmed` status in this repository carries its own direct links.
