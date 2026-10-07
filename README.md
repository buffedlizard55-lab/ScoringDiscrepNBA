# ScoringDiscrepNBA

> **Start every project session by reading this README and the project brief below.** Treat the brief as the goal, not a claim that the current implementation has reached it. Never invent an incident, statistic, correction, or attribution.

## Project brief (user request, retained as the starting point)

### NBA Scoring Discrepancy Research

Build this project as a comprehensive, continuously updated database and monitoring system for **NBA scoring discrepancies, scoring corrections, and conflicting score data**. The original use case is an incident where one source showed a **213-point final total while another showed 214**, so the system must be capable of finding, documenting, and explaining events like this rather than simply displaying the current final score. Research both historical and current NBA games and identify every verifiable case possible where the official score, play-by-play, box score, scoreboard, official scorer record, or third-party data feed was incorrect, temporarily different, or later corrected.

For every case, capture the **game, date, teams, period/game clock, relevant scoring play, score before and after the event, originally reported value, corrected value, final official value, affected player/team, sources that disagreed, timestamps when available, what changed, when it changed, and the confirmed or suspected cause**. Preserve the original observation and correction rather than overwriting historical data. Most importantly, determine whether the **NBA's official record itself was incorrect** or whether only a secondary source/data provider was incorrect or delayed. Every factual claim must be traceable to a reliable source with a direct link for independent review. Never infer missing information or present an assumption as fact; clearly label anything unverified, disputed, or requiring further investigation.

The system must continuously monitor current NBA games and automatically detect potential discrepancies between authoritative and secondary sources, create an investigation record, and track it through detection, investigation, correction, and resolution. The website should make the entire research collection easy for someone unfamiliar with the project to understand, search, filter, compare, and independently verify. Include historical statistics showing **how often scoring discrepancies/corrections occur, what types are most common, how long they typically last, how often they affect the final score/total, and how rare incidents like the 213/214 discrepancy are**. The final product should allow a new person with no knowledge of this conversation to understand exactly what happened in each case, reproduce the research from the cited evidence, and see the difference between the original data, the correction, and the final official result.

Put this prompt into the repo readme and read it everytime we work on the project as a starting point to make sure we are building what we are aiming for and have a strong base to continue building and improving on making something useful for everyday use. It should solve the problem of having to manually check everything ourselves and having an up to date current feed.

Review the repo.

The following is taken from the Arena AI team and I think it makes a good point on building a successful project, so let's keep the Core Values and Own the Outcome as a focal point when building, developing, researching, suggesting upgrades, and implementing the work.

Our Core Values

Maximize P(Win)

“Maximize the Probability of Winning”: our decision making framework. In every decision, we weigh tradeoffs, assess risk, and choose the path that maximizes the probability that Arena succeeds. We set aside our emotions and make tough decisions in order to maximize P(Win). “Maximize P(Win)” frees us from constraints and clarifies that we must put Arena first.

Own the Outcome

We own results end to end — not just our individual slice of the work. When problems arise and we have the means to act, we do so without waiting for permission or assignment. We treat failure and success as signals and use them to improve. At Arena, we stay accountable to the final outcome.

Work line by line verifying from official verified trusted sources, provide links for manual review. There should be no manual input, work on your own to complete tasks. Flag any irregularities for review. No hallucinations.

Verify no hallucinations.

The goal of this project is to get a full list that follow our requirements. No hallucinations. Verify line by line.

Site creation

Create a github page for this repo that has clean ui, user friendly, simple and easy to use.

It should be organized and clean. It should include all relevant information in an easy to read format with official verified links as sources for review. Work line by line verify everything no hallucinations.

Go ahead and create a pull request and then merge the pull request onto the main. Make suggestions for what work still needs to be done and any limitations that is in the way of a successful project. It should be worked on in this next session or the next session. Work line by line verify everything no hallucinations.

Run this task through multiple passes.

Pass 1: Implement the task completely and verify the result.

Pass 2: Review your work for bugs, missing requirements, incorrect assumptions, and edge cases. Fix everything you find.

Pass 3: Re-check the entire implementation against the original request. Improve accuracy, reliability, completeness, and code quality. Fix any remaining issues.

Do not stop after the first pass. Each pass must build on the previous one. Before finishing, verify that the final result fully satisfies the original request. Work line by line verify everything no hallucinations.

## Current implementation and evidence limits

**This is a monitoring foundation, not a comprehensive historical database.** There are zero verified historical cases in the repository. The motivating 213/214 event is not identified or verified. Do not calculate incidence or rarity from this incomplete sample.

- `src/monitor.py` queries the [NBA CDN live scoreboard](https://cdn.nba.com/static/json/liveData/scoreboard/todaysScoreboard_00.json) and [ESPN NBA scoreboard API](https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard?dates=20261007) for adjacent UTC dates. It matches by date and home/away abbreviation, only when unique; compares scores only when both label the game final. The NBA CDN feed is NBA-published, **not** evidence that the signed official scorer record was correct or incorrect. ESPN is secondary.
- `data/runs.jsonl` logs polling attempts/errors. `data/observations.jsonl` records changed normalized scores/status with retrieval time, source URL and raw response digest. `data/raw/*.json.gz` preserves fetched source bytes for later audit. `data/investigations.jsonl` logs candidate mismatches. JSONL is append-only; entries are not independently confirmed cases. A feed URL may change; use the archived raw file matching `response_sha256` to reproduce what was seen.
- `src/build.py` exports the static `site/dataset.json`; the site labels unverified records and gives direct source links. No automatic cause determination, play-level attribution, confirmed correction, or resolution is implemented yet.
- `.github/workflows/monitor.yml` polls every 30 minutes on the default branch after merge. GitHub Actions schedules may be delayed or disabled, and provider endpoints may change or block requests. `.github/workflows/pages.yml` publishes the `site/` artifact when GitHub Pages is configured for **GitHub Actions** in repository Settings → Pages. A deployed site is not guaranteed until that setting and workflow are verified.

Run locally: `python -m unittest discover -s tests -v`, `python src/monitor.py --build-only` (offline), or `python src/monitor.py` (network required). Run `python -m http.server 8000 -d site` to view locally. Monitoring errors are logged, not silently treated as absence of discrepancies.

## Next work, prioritized

1. Validate both endpoints in Actions and confirm monitoring and Pages deployments; add alerts for source failures, stale runs, and scheduled-workflow disablement.
2. Research the original 213/214 incident from dated primary evidence. Add an explicit verified-case schema, cited claim-by-claim evidence, signed game book/official scorer evidence, and reviewer-independent verification before calling any case confirmed.
3. Capture period/clock/play-by-play, box-score and game-book changes; add resolution transitions and classify official-record errors separately from feed lag. Detect transient in-game disagreements, not only final-vs-final mismatches.
4. Backfill historical seasons with documented coverage and denominators before publishing rates, correction latency, or rarity claims. Add pagination/data retention strategy and stronger source-independent identity matching.

## Decision rule

Maximize probability of a trustworthy outcome: prefer a clearly labeled incomplete record over a persuasive but unverified story. Own the outcome: investigate failures and gaps, preserve evidence, and never promote a candidate to a confirmed NBA error without primary evidence.
