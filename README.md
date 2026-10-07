# ScoringDiscrepNBA

> **Starting point for every session:** read this README before changing code, collecting evidence, or proposing work. Keep the research goal, evidence rules, and operating values below as the project’s persistent north star.

ScoringDiscrepNBA is intended to become an evidence-led database and monitoring system for NBA scoring discrepancies, scoring corrections, and conflicting score data. It must preserve what each source reported and when, distinguish an NBA-record error from a secondary-feed mismatch or delay, and make each conclusion independently reviewable.

## Persistent project brief

### NBA Scoring Discrepancy Research

Build this project as a comprehensive, continuously updated database and monitoring system for **NBA scoring discrepancies, scoring corrections, and conflicting score data**. The original use case is an incident where one source showed a **213-point final total while another showed 214**, so the system must be capable of finding, documenting, and explaining events like this rather than simply displaying the current final score. Research both historical and current NBA games and identify every verifiable case possible where the official score, play-by-play, box score, scoreboard, official scorer record, or third-party data feed was incorrect, temporarily different, or later corrected.

For every case, capture the **game, date, teams, period/game clock, relevant scoring play, score before and after the event, originally reported value, corrected value, final official value, affected player/team, sources that disagreed, timestamps when available, what changed, when it changed, and the confirmed or suspected cause**. Preserve the original observation and correction rather than overwriting historical data. Most importantly, determine whether the **NBA's official record itself was incorrect** or whether only a secondary source/data provider was incorrect or delayed. Every factual claim must be traceable to a reliable source with a direct link for independent review. Never infer missing information or present an assumption as fact; clearly label anything unverified, disputed, or requiring further investigation.

The system must continuously monitor current NBA games and automatically detect potential discrepancies between authoritative and secondary sources, create an investigation record, and track it through detection, investigation, correction, and resolution. The website should make the entire research collection easy for someone unfamiliar with the project to understand, search, filter, compare, and independently verify. Include historical statistics showing **how often scoring discrepancies/corrections occur, what types are most common, how long they typically last, how often they affect the final score/total, and how rare incidents like the 213/214 discrepancy are**. The final product should allow a new person with no knowledge of this conversation to understand exactly what happened in each case, reproduce the research from the cited evidence, and see the difference between the original data, the correction, and the final official result.

The system should continuously update without requiring someone to manually check every game. Flag anomalies for investigation; do not silently treat a difference as an error or declare it resolved merely because feeds later agree.

### Persistent project operating instructions

Put this brief in the repository README and read it at the start of every project session. Build a strong, useful foundation and improve it incrementally for everyday use. Work independently where possible, verify line by line against official and other trusted sources, and provide direct links for manual review. Do not hallucinate, fill gaps with assumptions, or present unverified details as fact. Flag irregularities and make uncertainty visible.

### Site creation and delivery expectations

Create a GitHub Pages website for this repository with a clean, user-friendly, simple, and easy-to-use interface. Organize relevant information so that a new visitor can search, filter, compare, and verify it. Include official and trusted source links. Review line by line; do not invent facts.

When a pull request is requested, open it from the session’s assigned branch. Merge only after verification and checks permit it. At delivery, suggest the important remaining work and explain limitations that could affect a successful project. Work in multiple passes:

1. Implement the task and verify the result.
2. Review for bugs, missing requirements, incorrect assumptions, and edge cases; fix what is found.
3. Re-check against the original request and improve accuracy, reliability, completeness, and code quality; fix remaining issues.

Do not stop after the first pass. Before finishing, verify the implementation against the complete project brief.

## Core values

Keep the following values in focus when building, researching, suggesting upgrades, and implementing changes:

### Maximize P(Win)

“Maximize the Probability of Winning”: our decision-making framework. In every decision, weigh tradeoffs, assess risk, and choose the path that maximizes the probability that the project succeeds. Set aside emotion, make tough decisions, and put the project outcome first.

### Own the Outcome

Own results end to end—not just an individual slice of the work. When problems arise and there is a way to act, act without waiting for assignment. Treat failure and success as signals and use them to improve. Stay accountable to the final outcome.

## Evidence and data principles

- **Evidence before assertion.** Each incident-level claim must have one or more source IDs and direct URLs. Prefer NBA records and NBA announcements for official status; use reputable reporting to document the original observation, correction history, and statements not available in an official archive.
- **Separate authority from availability.** A current NBA page is not proof of what an NBA or third-party page showed earlier. A secondary feed mismatch is not proof that the NBA was wrong.
- **Preserve snapshots.** Keep original values, later values, timestamps and timestamp precision, source identity, and the sequence of changes. Do not overwrite the old value with the new one.
- **Use explicit unknowns.** Null/unknown is better than inferred. Distinguish directly reported facts from transparent calculations, and label calculations as such.
- **Do not overstate coverage or rates.** Curated cases are not a census. Rates, typical correction time, and rarity require a complete denominator and reliable observation timestamps. Show “not yet measurable” until those conditions are met.
- **Automated detections are leads, not verdicts.** A feed difference may be delay, formatting, mapping, or an actual error. A machine-created record must say “candidate/unverified” until evidence supports a conclusion.

## Current repository state (2026-10-07)

This repository began as a README-only project. The initial implementation adds a static, responsive research dashboard; a small, source-linked seed collection of two confirmed postgame score corrections; an explicitly unresolved **213 vs 214** lead; and an offline-testable monitoring pipeline intended to poll the NBA’s public live scoreboard and an ESPN secondary scoreboard. It preserves candidate discrepancies and final-score revisions in JSON rather than silently overwriting values.

**Important:** the project is not yet a complete historical census, and no successful scheduled monitor run has been observed from this checkout. The seed cases are evidence-backed examples, not an incidence rate. The 213/214 lead has no game/date/provider information in the brief and has not been uniquely identified; it is deliberately excluded from verified-case statistics. Live polling and Pages publishing depend on the repository’s GitHub Actions/Pages settings and on upstream feeds remaining reachable. Do not describe automation as operational until successful workflow runs confirm it.

## Run and verify locally

The monitor and tests use Python’s standard library; no third-party Python packages are required.

```sh
python3 -m unittest discover -s tests -v
python3 -m monitor --check-data
python3 -m http.server 8000
```

Open `http://localhost:8000` for a local static preview. To run one live collection cycle locally (network access required):

```sh
python3 -m monitor --live
```

The live command calls the NBA CDN scoreboard and ESPN’s public scoreboard endpoint. These are external dependencies, and the ESPN endpoint is not a guaranteed or official NBA feed. A failed or unavailable source must be shown as unavailable, never interpreted as “no discrepancy.” Unit tests use local fixtures and do not require network access.

## Monitoring, persistence, and publishing

`.github/workflows/pages-and-monitor.yml` is configured to publish only the static dashboard and its JSON data through GitHub Pages, and to schedule best-effort source comparisons every five minutes. Each check compares the NBA public scoreboard feed with ESPN’s public scoreboard, records compact timestamped observations for differences, and watches for changes to the NBA feed after a final score first appears. A feed revision is stored as an **unverified observation**, not proof that the NBA’s underlying official record was corrected. Investigation observations are appended to the retained ledger; the current feed snapshot and rolling baselines are updated in place. Changed monitor JSON is committed to the default branch and redeployed with the site. Recorded observation times are the monitor’s UTC poll time, not an upstream publication timestamp; HTTP `ETag`/`Last-Modified` values and SHA-256 response hashes are retained with discrepancy observations when available. ESPN’s [stat-corrections guidance](https://support.espn.com/hc/en-us/articles/360056679592-Stat-corrections) distinguishes official NBA post-game stat changes from ESPN feed corrections and notes that ESPN data corrections can be delayed; this supports treating feed mismatches as review candidates, not proof that the NBA record is wrong.

The workflow can only operate after it is merged to the repository’s default branch and GitHub Actions/Pages permissions allow it to run, write data, and deploy. Default-branch protections may prevent the scheduled job from persisting monitor data unless they allow the workflow’s repository token to push. Scheduled runs can be delayed or skipped, and a five-minute sampling interval can miss short-lived differences. This is not a real-time or betting-grade alert service. A successful first run, source health, and the live-feed timestamp must be checked before calling the monitor active. Long-term, high-volume event history should move to a durable database or event store rather than growing indefinitely in Git.

## Next work and known limitations

1. Identify the exact 213/214 game and source pair from primary evidence; the prompt alone is not enough to identify it safely.
2. Expand the historical review season by season. Capture primary records and preserved before/after snapshots, including corrections that affected only a player stat and did not change the final team score.
3. Validate NBA CDN and ESPN field semantics and availability in actual GitHub Actions runs; add alerting/health monitoring for missed runs, upstream schema changes, and feed outages.
4. Add more independent secondary feeds only after their access terms, stability, identifiers, and timestamps are documented. Record source-specific timestamps and raw-response hashes or immutable snapshots where lawful and practical.
5. Build denominators (games and source observations monitored) and enough timestamped cases before publishing prevalence, median duration, or rarity statistics.
6. Consider a database/API and notifications if Git-backed JSON becomes too large or if a higher-frequency, lower-latency monitor is needed.
7. Add accessibility, mobile, browser, and end-to-end checks as the site grows; preserve no-JavaScript access to the evidence where feasible.

## Project links

- Public-facing research dashboard: `index.html`. Expected GitHub Pages URL after Pages is enabled and the workflow deploys: `https://buffedlizard55-lab.github.io/ScoringDiscrepNBA/` (not claimed live until a successful deployment is observed).
- Curated cases: `data/cases.json`.
- Unresolved research leads: `data/leads.json`.
- Current feed and automatic investigation state: `data/live-feed.json` and `data/monitor-state.json`.
- Monitor implementation: `monitor/`.
- Data contract: `schemas/case.schema.json`.
