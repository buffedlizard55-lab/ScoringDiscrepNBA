# ScoringDiscrepNBA

An evidence-first, source-traceable research database and monitor for NBA scoring discrepancies and official score corrections.

> **Maximize P(Win). Own the Outcome.** The point is better information and accountable follow-through—not a flashy count. Preserve what each source said, show what changed, and never turn an unverified mismatch into an accusation.

## Project prompt (preserved for future sessions)

The full project brief carried forward from the original request is:

> Build ScoringDiscrepNBA into a source-traceable research database and monitoring system for NBA score discrepancies/corrections, including historical and current games. Records must preserve original observations and later changes; capture the game, date, teams, period/clock, play and score context, reported/corrected/final official values, affected player/team, disagreeing sources and timestamps, what/when changed, and confirmed or suspected cause; distinguish an incorrect NBA record from secondary-source error/delay. Do not infer missing facts: label unverified/disputed items and flag anomalies. Provide a clear, accessible GitHub Pages site for browsing/searching/filtering/verifying records, meaningful historical statistics with transparent denominators and coverage, and continuous automated comparison/detection that tracks investigations through resolution. Put the full project prompt in README and reread it at the beginning of each project session. User also requests creating a PR and merging to main if feasible, suggestions/limitations, and three implementation/review passes.
>
> Keep Arena values **“Maximize P(Win)”** and **“Own the Outcome”** central to implementation, research, upgrades, and recommendations. Work autonomously; do not make the user manually check routine scores. Verify factual claims against reliable sources, include direct links, preserve original and corrected observations, identify whether the NBA record or only a secondary source was wrong/delayed, and label unknowns. Reread this README at the start of each project session. Complete Pass 1 implementation/verification, Pass 2 defect and missing-requirement review/fixes, and Pass 3 full-request recheck/improvements. Create a PR and merge it to `main` if feasible.

This charter is intentionally retained in the README so the next contributor can reread the scope before changing code or records.

## What is here

- A static, keyboard-accessible GitHub Pages research interface with search, filters, evidence links, original-versus-corrected score views, a live-monitor panel, and explicit coverage caveats.
- A small curated seed set of **two confirmed NBA score corrections**, each linked to primary league statements and corroborating reporting/provider pages. In this curated set, **2/2** involve a successful free throw first entered as missed; that sample proportion is not a league-wide rate.
- Explicitly **unverified** research leads for the unidentified 213/214 report and Kevin Porter Jr.'s 2021 player-stat claim, excluded from every confirmed-case count.
- A dependency-free Python monitor that compares the NBA live scoreboard with ESPN's publicly exposed scoreboard feed, records meaningful score/status transitions, and opens/updates unverified candidate investigations. Monitoring convergence is separate from human evidence-backed investigation status; see [`docs/INVESTIGATION_WORKFLOW.md`](docs/INVESTIGATION_WORKFLOW.md). An NBA play-by-play feed may be attached as nearby context; it is never treated as proof of cause by itself.
- JSON data validation and unit tests using local fixtures; no scores are manually re-keyed by the monitor.

## Evidence rules

1. **Prefer the NBA's own correction/record.** An NBA correction is distinct from a score disagreement between third-party feeds. A provider's stale table or story text is recorded as a provider inconsistency, not counted as another NBA correction.
2. **Keep observations immutable in meaning.** Historical records retain original and corrected values and the source/time basis for each. The automated monitor stores timestamped observations when a score/status signature changes; it does not overwrite an earlier observation with a later value.
3. **Do not infer the missing pieces.** The displayed score after a play is labelled *derived* if it is only arithmetic; a suspected cause stays suspected; an inaccessible or undocumented endpoint is not described as a validated integration.
4. **Source every material claim.** Case records link to a source register (`data/sources.json`) and expose claim-level citations. A source's limitations or internal contradictions are shown beside its claims.
5. **No unsupported rate or duration claims.** Two curated examples are not a league-wide denominator. A 213/214 anecdote with no identified game/source remains an unverified lead.

## Seed evidence (scope: curated examples only)

- **Warriors–Trail Blazers, 2024-10-23:** the NBA reported that De'Anthony Melton's made third-quarter free throw was entered as a miss and changed the final from **GSW 139–104 POR** to **GSW 140–104 POR**. NBC Sports Bay Area supplies the 91–67 pre-attempt score and the corrected 11-point player line. CBS and ESPN pages also expose stale embedded values alongside updated values; those are catalogued as provider-page inconsistencies, not extra league corrections. The score immediately after the free throw (92–67) is arithmetic derived from the cited pre-play score and one successful free throw, not a captured live-feed row.
- **Cavaliers–Wizards, 2025-11-07:** the NBA announced that Tre Johnson's made second-quarter free throw at 8:15 was entered as missed, and the final changed from **CLE 148–114 WAS** to **CLE 148–115 WAS**. ESPN's recap has a corrected score table but stale Associated Press prose, so both observations are preserved. The 50–39 pre-play score is reported by The Athletic; the post-play 50–40 value is derived, not independently captured.

The record-level citations, time precision, and known source conflicts are in [`data/cases.json`](data/cases.json) and [`data/sources.json`](data/sources.json). NBA rules are included for scoring/scorer-duty context, not as proof of an individual incident.

## Run locally

Requires Python 3.10+; there are no third-party Python packages.

```bash
python -m unittest discover -s tests -v
python tools/validate_data.py
python tools/build_site.py --root . --output _site
python -m http.server 4173 --bind 0.0.0.0
```

Open `http://localhost:4173` in a local browser. The monitor can be run once with:

```bash
python tools/monitor_scores.py --root .
```

That command contacts live public feeds. To test the monitor without network access, run the unit suite; tests use fixtures. A failed/unavailable source is recorded as unavailable, not silently treated as a zero score or a resolved discrepancy.

## Automated monitoring and GitHub Pages

`.github/workflows/monitor-and-pages.yml` runs on a 15-minute schedule (GitHub may delay scheduled runs), on `main` updates, and on manual dispatch. It checks out the fixed Arena session branch, syncs current `main` content into it, polls both providers, persists only meaningful observation/candidate changes on that same branch, builds a small Pages artifact, and deploys it with GitHub Actions. It never pushes monitoring commits to `main`. The session branch must remain available and writable by the workflow token for durable history; a branch-protection rule that blocks Actions pushes will stop persistence/deployment. The static page displays the snapshot from the latest successful deployment; it is not a streaming scoreboard.

Enable **Settings → Pages → Build and deployment → Source: GitHub Actions** once for the repository. The workflow needs the standard repository `GITHUB_TOKEN` permissions shown in its YAML; it uses no external secret. `.github/workflows/tests.yml` runs the deterministic test and data-validation suite on pushes and pull requests.

## Monitoring limits and interpretation

- The monitor compares only team scores exposed by two current public feeds. A difference is an **unverified source divergence**, not proof the NBA is wrong. A feed may lag, fail, revise a value, or share the same underlying error as another source. Player-stat-only corrections that do not change the team score are outside this comparator; the Kevin Porter Jr. lead remains unverified.
- Polling is every 15 minutes when GitHub Actions runs; events corrected entirely between polls, errors shared by both feeds, historical mismatches absent from current feeds, and games unavailable in either feed can be missed. The poll interval is not a measured error duration.
- The NBA CDN endpoints are publicly accessible but not an NBA-published developer contract. The NBA play-by-play URL/shape is documented by the community-maintained `nba_api` project; that documentation is technical context, not primary incident evidence. ESPN's JSON endpoint is likewise an undocumented provider feed. Both may change or block automated access.
- Play-by-play rows shown beside a flag are *nearby feed context only*. The monitor does not assert that a nearby event caused the score divergence.
- An automated candidate moves to **feed-converged** if the two feeds later agree. That operational transition does **not** establish which feed was correct or resolve the root cause; human/source review remains required before promotion to a confirmed case.
- Historical coverage is a small, hand-researched, non-exhaustive seed, not a census of NBA games or all corrections. The Kevin Porter Jr. player-stat lead and unidentified 213/214 report remain unverified and are excluded from counts. No league-wide incident rate, rarity, average time-to-correction, or completeness claim is justified by this dataset.
- Historical NBA.com game pages could not be reliably retrieved during this research pass (they rendered unrelated current schedule content); do not treat those fetches as verification of an old box score.

## Repository map

```text
index.html, styles.css, app.js     Accessible GitHub Pages interface
 data/cases.json                   Curated, evidence-cited confirmed cases + scope note
 data/leads.json                   Unverified leads (excluded from confirmed statistics)
 data/sources.json                 Direct source register and limitations
 data/monitor/current.json         Last published poll snapshot (workflow artifact updates it)
 data/monitor/candidates.json      Durable automatic divergence investigations
 data/monitor/state.json           Last meaningful source signatures for change detection
 data/monitor/observations.jsonl   Append-only meaningful monitor observations
 tools/monitor_scores.py           Feed parsing, comparison, candidate lifecycle
 tools/validate_data.py             Static dataset integrity checks
 tools/build_site.py                Minimal Pages artifact builder
 tests/                            Offline unit tests and JSON fixtures
 .github/workflows/                CI and scheduled monitoring/Pages deployment
 docs/INVESTIGATION_WORKFLOW.md      Evidence-backed candidate review and resolution states
 REVIEW_PASSES.md                   Pass 1, Pass 2, Pass 3 verification log
```

## Next research / improvement opportunities

- Independently retrieve preserved NBA box-score/play-by-play snapshots for both confirmed incidents, especially the original pre-correction player/stat lines.
- Add a third genuinely independent, documented source or a revision-history-capable archive before making stronger claims about provider reliability or detection coverage.
- Expand historical research with a defined search protocol and denominator, preserving capture timestamps and source versions.
- Add manual source-review fields (reviewer, disposition, evidence citations, correction/resolution time) before promoting any automated candidate into the confirmed-case table.
- Consider an alert destination (e.g. an issue per candidate) only after the lifecycle, duplicate prevention, rate limits, and permissions are tested. The current monitor writes its durable state on the session branch and does not ask the user to check every routine score.
