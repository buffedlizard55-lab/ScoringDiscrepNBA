# Automated score alerts: what is possible and what this project does

## Current alert channel

The scheduled monitor now creates repository **GitHub issue alerts** using the repository's built-in `GITHUB_TOKEN`; it needs no external API key or webhook secret.

It opens or refreshes an alert when:

1. NBA and ESPN provide parseable but different scores for the same home/away matchup on **two consecutive completed comparisons** (normally scheduled five minutes apart). Any poll with an unavailable source, an unreturned game, or incomplete scores breaks the streak; the comparison-check history records that interruption. This persistence threshold suppresses one-poll feed lag. It is a candidate notification, not a declaration that either source is wrong.
2. The monitored NBA scoreboard changes a game's score after the monitor has saved its first final-score baseline. That final-feed revision is alerted immediately and remains an unverified observation.

A feed outage, a missing score, an ambiguous game match, or a one-poll live mismatch is not promoted to a scoring-alert issue. Source-health failures remain visible on the dashboard. The issue body preserves the investigation identifier, first monitor observation time, latest saved feed values (not provider publication times), relevant play-by-play context (explicitly not treated as cause), and safe source links. The issue number, current body hash, and alert status are saved with the investigation so unchanged five-minute polls do not repeatedly search or edit GitHub; changed score/status content refreshes the same issue rather than opening a new one. When two feeds later agree for two polls, the issue receives a clarification comment but is **not auto-closed**; agreement does not explain the earlier difference. A person may close or disposition the issue after reviewing evidence.

The workflow requests only `issues: write` in addition to its existing site/monitor permissions. If issue creation fails, the monitor keeps its score observations and Pages publication going, records a workflow warning, and retries on a later scheduled run. It does not create a verified historical case automatically.

- [Current monitor dashboard](https://buffedlizard55-lab.github.io/ScoringDiscrepNBA/#monitor)
- [Monitor alert issues](https://github.com/buffedlizard55-lab/ScoringDiscrepNBA/issues?q=is%3Aissue+in%3Atitle+SDNBAALERT)
- [Scheduled workflow and permissions](../.github/workflows/pages-and-monitor.yml)
- [Alert implementation](../scripts/github_alerts.js)
- [Investigation review workflow](INVESTIGATION_WORKFLOW.md)

## Freshness and publication semantics

The five-minute GitHub Actions schedule is best-effort, not a real-time service-level guarantee. Each scheduled run now publishes a fresh snapshot heartbeat and, when NBA data is available, a current game clock—even if scores did not change. It commits monitor JSON to `main` only when scores, source health, investigation history, or another material state changes. Heartbeat-only timestamps and clocks are omitted from Git commit comparisons, avoiding a repository commit every five minutes. The scheduled workflow still stages and deploys the fresh static Pages artifact on every run.

- `last_poll_attempt_at` is when this monitor attempted to fetch feeds; it is **not** proof that both feeds responded.
- `last_successful_comparison_at` is the latest poll where both NBA and ESPN payloads parsed successfully. On a degraded poll, the previous value is retained.
- `games[].observed_at` is the monitor's UTC observation time; it is not a provider publication time.
- `last_updated_at` is the last **material snapshot change**, not a poll heartbeat.
- HTTP `Last-Modified` and `ETag` headers, when present, are response metadata; they do not prove when a provider's score changed internally.

The dashboard shows source health and both poll timestamps. It marks a snapshot stale when the last recorded attempt is over 15 minutes old and marks freshness unknown if a checked snapshot has no attempt heartbeat, so a delayed/one-sided poll is not mistaken for a healthy, current comparison.

## What it can and cannot detect

The current comparison is between the NBA's public CDN scoreboard and ESPN's public scoreboard, matched by normalized home/away team abbreviations. The NBA feed is the primary feed being observed, not an infallible ruling. An NBA play-by-play request is made for score mismatches, but the latest scoring play is context only; adjacency does not prove it caused a discrepancy.

The system can detect a mismatch **only if** a configured source returns the game and a different value. It cannot prove which source was right, find a game omitted by both feeds, detect two feeds sharing the same wrong value, or identify a broadcast/arena scorebug that never appears in either feed. Short differences can begin and end between five-minute polls. Provider outages, changed schemas, time-zone/game-date boundaries, game matching, delayed corrections, and GitHub Actions schedule delays can cause missed or late observations. Hashes and HTTP headers help distinguish captured response versions but are not a substitute for preserving the raw response or an independent archival source.

The historical collection also remains a partial research sample. Its counts cannot establish NBA-wide frequency or quantify how rare the unidentified 213-vs-214 lead is.

## Notification limits and future options

GitHub issues are a useful no-secret first channel, but the repository cannot force a particular person's email, mobile push, or desktop notification. Delivery depends on the user's GitHub watch/subscription settings and notification configuration. The issue is public because this repository is public.

A targeted Slack, Discord, SMS, or email channel is technically possible through GitHub Actions, but it requires a destination URL/token or mail-service credentials stored as repository/environment secrets, plus rate limits, retry policy, delivery monitoring, and spam controls. Never commit those secrets or paste them into chat. Browser push to a closed tab needs both a user subscription and a server-side push sender; a static GitHub Pages site alone cannot provide that backend. Browser notifications while the page is open are possible but are not a substitute for reliable background delivery.

Before adding a second channel, soak-test during NBA games, measure false positives and workflow delay, and agree on the severity threshold and deduplication policy. Prefer improving evidence and operational health over sending noisy alerts.
