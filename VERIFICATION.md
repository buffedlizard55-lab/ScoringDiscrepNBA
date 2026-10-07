# Verification — methods, source hierarchy, and line-by-line log

This file is the project's evidence standard. Every session must work to it and extend the log
at the bottom when facts are added or changed.

## 1. Anti-hallucination rules (binding)

1. **Traceability:** every factual claim in `data/cases/` must trace to a `sources[]` entry with
   a direct `https://` link. The `confirms` field states exactly what that source proves.
2. **Null over guess:** unknown dates, scores, clocks, venues, and causes are `null`, plus an
   entry in `open_questions[]`. Arithmetic derivation (e.g. combined totals) is allowed only
   when both inputs are sourced, and must be labeled as derived where shown.
3. **Official-first ruling:** `classification.layer` + `official_record_was_wrong` must be set
   deliberately on every record. This is the project's core determination.
4. **Preserve disagreement:** conflicting sources go in `disputed_points[]` / `sources_disagreed[]`
   with each position quoted. Never silently pick a winner.
5. **Append corrections:** original, correction, and final values are all retained. History is
   never overwritten.
6. **Status ladder:**
   - `unverified` — report exists, no reliable corroboration (game facts stay `null`).
   - `under-investigation` — monitor/human flag with identified game, research in progress.
   - `verified-partial` — core facts corroborated; some questions remain open.
   - `verified` — ≥2 sources incl. a strong tier (`official-nba`, `wire-ap`,
     `major-sports-media`) corroborate every required field; `open_questions[]` is empty.
     Enforced by `scripts/validate.py`.
   - `disputed` — reliable sources materially disagree on a core fact.
   - `not-a-discrepancy` — investigated and closed as no-error (kept for transparency).
7. **No promotion without evidence:** status upgrades require new dated, linked evidence in the
   record itself.

## 2. Source hierarchy (see also `data/sources.json`)

| Tier | Meaning | Examples |
|---|---|---|
| `official-nba` | League authority | NBA.com releases, @NBAOfficial, official.nba.com rulebook, official box scores |
| `wire-ap` | Wire reporting | Associated Press coverage |
| `major-sports-media` | Major outlets, named sourcing | ESPN, USA Today, SI, The Athletic, NBC Sports, LA Times |
| `team-beat` | Regional/beat | NBC Sports Bay Area, KPRC/Click2Houston |
| `secondary-digital` | Digital outlets, aggregation | Bleacher Report, HoopsWire, Action Network, FanSided, Yahoo agg. |
| `tertiary-unverified` | Leads only | Social posts (non-official), Reddit, recollection, Wikipedia (background) |

Tier ranks *authority for conflict resolution*, not infallibility. Single-secondary core facts
keep the case at `verified-partial` at best and must be flagged in `open_questions[]`.

## 3. Standard reference facts (reusable, sourced)

- **Running-score rule:** “If there is a discrepancy in the score and it cannot be resolved, the
  running score shall be official.” — NBA Rule 5, §I(8).
  https://official.nba.com/rule-no-5-scoring-and-timing/
- **2-vs-3 reviewability:** successful 2-pt/3-pt rulings are reviewable within strict timing
  windows (next-stoppage rules). — NBA Rule 13 + replay triggers.
  https://official.nba.com/rule-no-13-instant-replay/
  https://official.nba.com/trigger/two-point-three-point-field-goal/
- **Official statistician:** Elias Sports Bureau has been the NBA's official statistician since
  1970-71. https://www.esb.com/about
- **Corrections are rare:** the NBA, Elias, and sportsbooks characterize corrections as “rare”;
  Elias says the league issued “far fewer” corrections over the three seasons entering 2022 than
  in prior seasons. — ESPN, Feb 24 2022. https://www.espn.com/espn/print?id=33355887
- **Feed-vs-league taxonomy:** ESPN distinguishes (1) live-scoring updates as better league data
  arrives, (2) post-game NBA adjustments, (3) ESPN feed-data corrections. The monitor adopts this
  to classify detections. https://support.espn.com/hc/en-us/articles/360056679592-Stat-corrections
- **Protest protocol:** notice by fax/email to the commissioner within 48 hours of the game's
  conclusion; upheld protests require misapplication of the rules (not judgment).
  https://www.nytimes.com/athletic/5224974/2024/01/24/nba-game-protest-process-history/
- **Protest rarity baseline (CORRECTED 2026-10-07):** per the league's best-available records,
  **only six protests have ever been upheld** (none won since the 2007-08 Shaq case), of 44
  previous entering ~2020 / 45 entering 2023.
  https://www.nba.com/news/nba-protest-process-mavericks-await-news
  https://www.dallasnews.com/sports/mavericks/2023/03/24/mavericks-mark-cuban-file-formal-protest-with-nba-over-controversial-loss-to-warriors/
  A 2014 USA Today research note (“nearly 35 filed… three upheld since 1952”) is CONTRADICTED by
  the league's own records — do not cite the “3”. (Correction credit: the PR #2 session's lead;
  independently re-verified here. See §6.)

## 4. Line-by-line verification log

### Pass 2026-10-07-A (founding research pass; reviewer: agent session)

Method: web search + page fetch for each candidate incident; facts admitted only with a direct
URL recorded in the case file. Validator + stats + monitor self-test all green.

| Case | Core facts admitted | Source count / strongest tier | Flags / open items |
|---|---|---|---|
| 2024-10-23 GSW@POR (Melton FT) | date, Q3 2:00, 1-of-2 entered 0-of-2, 139→140 final, next-day league announcement, 223.5/−5.5 lines | 6 / official-nba (NBA.com/AP + @NBAOfficial embed) | Melton's final points disputed across secondaries (11 vs 12) → `disputed_points`; @NBAOfficial text not independently re-fetched |
| 2025-11-07 CLE@WAS (Johnson FT) | date, Q2 8:15, both made / first entered miss, 148-114→148-115, NBA statement quotes, Frank “human error” quote, 19 pts / 2-of-3 | 3 / major-sports-media (Athletic) | No primary NBA.com URL found → priority open question; betting lines unknown |
| 2019-12-03 HOU@SAS (Harden dunk) | date, Q4 7:50, 102-89, through-net ricochet, no-basket ruling, 48h protest, Dec 9 denial, officials disciplined, replay-would-show-good | 4 / major-sports-media | Primary denial statement URL missing; challenge-timing dispute preserved; final 135-133 2OT stands |
| 2007-12-19 MIA@ATL (Shaq foul) | Q4 3:24 Haslem→Shaq mis-entry, OT 51.9s DQ at 112-111, Horford FTs to 114-111, Jan 11 upheld, $50k fine, Mar 8 scoreless replay | 4 / wire-ap + major | Post-replay 114-111 final single-sourced to SI 2014 recap → needs box-score corroboration; primary ruling URL missing |
| 1982-11-30 LAL@SAS (Nixon FT) | 116-114 setup, fake, jump-ball misapplication, 137-132 2OT overturned, Dec 1982 upheld, Apr 1983 replay, 117-114 | 3 / major-sports-media | Exact April replay day unverified (Apr-13 claim is Reddit-citing-NYT: NOT admitted); schema `type` is approximate (rules-misapplication; see ROADMAP v2) |
| 2018-12-31 MIN@NOP (scoreboard) | final 123-114 + quarter line (ESPN); wrong-board +8-shown-as-7, Towns foul-out sequence, 2H spread (Action Net.) | 3 / major-sports-media for score; single-secondary for the malfunction claim | Malfunction claim is single-source → stays flagged; cause undocumented; :12.0 vs 12.5s clock-text trivia preserved |
| 2022-01-24 UTA@PHX (Paul assist) | erroneous Paul assist → Bridges next day after bettor flag; settlement policies | 2 / major-sports-media | Play detail (Q/clock) undocumented; never a scoring dispute (labeled non-scoring) |
| 2022-01-27 MIN@GSW (Edwards steal) | early-Q1 Curry/Edwards/Towns sideline play; Towns→Edwards next day; FanDuel honored | 2 / major-sports-media | Exact clock undocumented; labeled non-scoring |
| 2022-02-09 CHI-CHA (LaVine assist) | LaVine→DeRozan un-credited assist; 5.5 line; NBA email policy quote (no postgame assist creation; wrong-player only) | 1 / major-sports-media | Single-source; negative case (denied) by design; venue/teams intentionally null |
| 2019-06-13 Finals G6 (Green 2v3) | Q1 ~2:15, ruled 2, not reviewed, league “no clear and conclusive evidence” position, half down 3, down 1 w/ 9s left | 3 (incl. official-nba for procedure context only) | Final score + venue deliberately NULL (not in reviewed sources); no position taken on foot placement; review-trigger reason undocumented |
| 2014-11-13 SAC@MEM (Lee buzzer) | 110-109/0.3s, Carter inbound, Gasol screen, Lee layup, Hollins-tip + late-release claims, Nov 28 denial (“proper judgment”) | 3 / major-sports-media | Primary denial URL missing; no tip asserted |
| 0000-00-00 originating 213/214 | NONE admitted — stub only | 1 / tertiary-unverified (repo link = provenance, not evidence) | Game unidentified; resolution rule embedded in the record |

Deliberate omissions in this pass (to avoid hallucination): Finals G6 final score; April-1983
replay day; Melton's exact corrected points; any betting impact not explicitly reported; any
cause beyond what sources state.

### Pass 2026-10-07-B (merge audit + promotion; reviewer: agent session)

- Added `2017-01-20-ind-lal-robinson-2v3` (verified-partial / official-nba-confirmed): lead
  from the PR #2 session, independently re-verified via the NBA.com Lakers release (fetched
  full text), AP via FOX Sports, and ABC7. Original 108-96 is DERIVED (108-95 + 1) and labeled
  as such pending an archived pre-correction box score.
- Corrected the protest-count baseline from “3 since 1952” (USA Today 2014) to the
  league-official “only six upheld” (NBA.com protest-process explainer + 2023 corroboration).
  Updated `compute_stats.py`, `ROADMAP.md`, site copy, and the 1982 case's USA Today note.
- Ran the cross-session audit (§6). No legacy facts imported without fresh verification.

## 5. Re-verification checklist (run before any release/PR)

- [x] `python3 scripts/validate.py` passes
- [x] `python3 scripts/compute_stats.py && python3 scripts/build_site_data.py` reproduce committed `data/*.json` + `docs/data/*` with no diff
- [x] `python3 scripts/monitor.py --self-test` passes
- [x] Every touched case: sources open (spot-check), `last_reviewed` bumped, open questions current
- [x] Stats caveat still present on site + payload

## 6. Cross-session audit (PR #2 legacy store — 2026-10-07)

Scope: `data/discrepancies.json` (12 records), `research/`, prior site/stats. Method: targeted
re-verification of load-bearing claims; NOT a full re-audit. Standing: legacy records are LEADS.

**Confirmed errors (do not cite):**

1. `DISC-20241107-CLE-WAS-001` dates the Cavaliers–Wizards correction game **2024**-11-07 and
   embeds it in the case ID. The record's own cited Athletic URL is `/2025/11/08/`, the cited
   rookie (Tre Johnson) was drafted in **2025**, and the canonical record (3 sources) dates the
   game **2025**-11-07. Verdict: wrong year. Fix requires ID + date correction in the legacy store.
2. `research/README.md` lists 12 `DISC-*.md` files; only one exists
   (`research/DISC-20241023-GSW-POR-001.md`). Verdict: incomplete shipment, not a data error —
   but the checklist claim “each case has its own markdown file” is false.
3. Legacy headline stats (e.g. “41.7% 1-point”, “75% official incorrect”) inherit finding #1 and
   predate this audit. Verdict: do not cite until recomputed from corrected data.

**Confirmed corrections contributed BY the legacy session (credited, re-verified here):**

4. The “only six upheld protests” league record (NBA.com protest-process explainer) — corrected
   this project's own “3 since 1952” note. Independently corroborated by 2023 reporting
   (Dallas Morning News, SF Chronicle).
5. The 2017 Robinson III correction lead (NBA.com Lakers release + ESPN) — independently
   re-verified and promoted to a canonical case (see Pass B log).

**Open leads (NOT verified by this session — verify before use):**

6. Four pre-1982 upheld protests (1952 MIL@PHI, 1969 ATL@CHI, 1971 CLE@BUF, 1978 NJN@PHI):
   consistent with the “six upheld, none since 2008” league record, but per-case facts
   (scores, replays, dates) are unverified here.
7. Two 2026 scorebug errors (NBC Knicks–Hawks, Amazon Hornets–Heat) and the 2021 Porter Jr.
   stat correction: cited URLs on file in the legacy store; not yet independently checked.

## 7. Arena PR #4 integration review (2026-10-07 UTC; post-merge verification)

This integration reconciles the earlier historical catalog/monitor work with the newer `main`
root dashboard and monitor package. The root interface remains `index.html` + `assets/`; the
current automated monitor remains `monitor/` + `data/live-feed.json` / `data/monitor-state.json`.
The older `docs/` catalog and `scripts/monitor.py` are retained as historical/manual layers, not
presented as a second active scheduled monitor.

### Source and case audit

- **2024 Warriors–Trail Blazers:** the NBA-reported 139–104 → 140–104 team-score correction and
  the Q3 2:00 made-free-throw/missed-entry explanation remain supported by the NBA.com/AP and
  official announcement links. NBC Sports Bay Area reports the 91–67 event-local score. ESPN and
  CBS page-component inconsistencies are preserved as secondary-provider observations, not as
  separate NBA corrections. The corrected Melton player total remains **unresolved (11 vs 12)**;
  no official corrected player-line snapshot was recovered. The active root seed no longer chooses
  11 as the official value.
- **2025 Cavaliers–Wizards:** the direct NBA Official post
  (https://x.com/NBAOfficial/status/1987199646020870516) is linked alongside the official NBA
  Gamebook and secondary reporting. The official post establishes the league’s correction
  statement; The Athletic’s separate “human error” and audit-process detail remains explicitly
  attributed to that secondary report. The exact NBA record-update time and pre-correction Johnson
  player total remain unknown. ESPN/CBS stale components are retained as later provider observations.
- **Unverified leads:** both the 213/214 report and 2021 Kevin Porter Jr. item remain in `data/leads.json`
  as unverified, and in the historical case collection as unverified stubs. No unsupported game,
  matchup, changed player statistic, cause, or provider fault is treated as fact. Both are excluded
  from confirmed-case statistics by data checks.
- **Historical stats:** `data/stats.json` is regenerated from 14 historical case records (12
  verified-partial, 2 unverified; **0 fully verified**). The legacy `verified_count` includes
  `verified` + `verified-partial` and is explicitly scoped in the payload. It is collection-only. `data/statistics.json` is an audit-flagged superseded manifest; the old
  numeric summary remains in the standalone PR #2 archive and is not current evidence.

### Monitor and release state

- `data/live-feed.json` still says `not_started` and `data/monitor-state.json` is the seed ledger.
  No successful live NBA/ESPN poll is claimed. `data/monitor/current.json` is the separate earlier
  monitor’s intentional `not-run` baseline.
- Offline checks currently cover the active root dashboard/monitor and the retained historical
  monitor. The current local suite reported **47 tests passed**; `python3 -m monitor --check-data`,
  `python3 scripts/validate.py`, `python3 scripts/monitor.py --self-test`, JavaScript syntax checks,
  Python compilation, and generated-data rebuilding passed at this integration checkpoint.
- **PR #4 merged:** GitHub reports merge time `2026-10-07T06:18:55Z`; main merge commit is
  `9e0925547bbf11902220712c11ff20d0beae7deb` ([PR #4](https://github.com/buffedlizard55-lab/ScoringDiscrepNBA/pull/4)).
  The PR-head `validate` and `verify` checks passed. Post-merge `Validate research data`
  ([37580834050](https://github.com/buffedlizard55-lab/ScoringDiscrepNBA/actions/runs/37580834050)),
  `Verify research data and monitor`
  ([37580833196](https://github.com/buffedlizard55-lab/ScoringDiscrepNBA/actions/runs/37580833196)),
  the Pages publisher ([37580833159](https://github.com/buffedlizard55-lab/ScoringDiscrepNBA/actions/runs/37580833159)),
  and Pages build/deployment ([37580833006](https://github.com/buffedlizard55-lab/ScoringDiscrepNBA/actions/runs/37580833006)) all succeeded.
- The public root page and `/docs/` historical catalog were fetched after deployment. The root page
  showed both evidence-reviewed cases and both separately labeled unverified leads; the historical
  catalog rendered its 14 records and collection-only caveats.
- **Live polling remains unverified:** the successful push-triggered publisher skipped its
  schedule-only source-comparison step. The published `data/live-feed.json` still reports
  `not_started`; no successful NBA/ESPN poll is claimed. A manual workflow dispatch was attempted
  but GitHub returned HTTP 403, `Resource not accessible by integration`. The five-minute schedule
  is configured, but its first successful poll and published timestamp still need verification.
- Project review date: **2026-10-07 UTC** (2026-10-06 in America/Los_Angeles). Appendix A below
  remains the byte-preserved prior-session guide.

## Appendix A — prior session (PR #2) verification guide, preserved verbatim

*Everything below this line is the byte-identical content of the PR #2 session's
`VERIFICATION.md` (commit `060be50`), preserved so its per-case verification steps survive the
merge. It documents the legacy `data/discrepancies.json` store. Cross-session audit findings in
§6 above take precedence where they conflict.*

---
# Verification Guide - No Hallucinations

## Policy: Verify Line by Line

Every factual claim must be traceable to a reliable source with a direct link.

## How to Verify Each Case

### Case DISC-20241023-GSW-POR-001 (Warriors-Blazers)

**Claim:** Final score changed from 139-104 to 140-104 due to Melton FT error.

**Verification steps:**
1. Visit https://www.nba.com/news/nba-finds-scoring-error-warriors-blazers
   - Should show title "NBA finds error, adjusts score in Warriors-Blazers"
   - Should mention Melton 1-of-2 FT with 2:00 remaining in 3rd
   - Should show corrected final 140-104
2. Visit https://www.espn.com/nba/story/_/id/41990836/nba-acknowledges-error-adjusts-warriors-trail-blazers-score
   - Should confirm same facts
   - Should quote "Statisticians at the game recorded Melton as having missed both free throws"
3. Check Basketball-Reference for 2024-10-23 GSW @ POR - should show 140-104 final
4. Search Wayback Machine for original 139-104 box score (may be cached)

**Status:** VERIFIED - 2 official sources (NBA.com, ESPN) + 2 secondary (Bleacher, NBC) all agree.

### Case DISC-20170120-IND-LAL-001 (Pacers-Lakers)

**Claim:** Glenn Robinson III 3-pointer was actually 2-pointer, final 108-96 → 108-95

**Verification:**
1. Visit https://www.nba.com/lakers/releases/nba-corrects-scoring-error-from-pacers-lakers-game
   - Should show date Jan 27 2017, mentions Robinson III incorrectly credited with 3-pt when inside line at 1:49 Q4
   - Should show video link: https://www.nba.com/video/2017/01/27/pacers-lakers-scoring-error-corrected
   - Should state final now 108-95
2. Visit https://www.espn.com/nba/story/_/id/18569405/nba-corrects-scoring-error-los-angeles-lakers-indiana-pacers-game
   - Should confirm same
3. Visit https://www.espn.com/nba/game/_/gameId/400900070/pacers-lakers - should show final 108-95 (corrected)

**Status:** VERIFIED

### Historical Protests (6 cases)

**Claim:** Only 6 protests upheld in NBA history

**Verification:**
1. Visit https://www.nba.com/news/nba-protest-process-mavericks-await-news
   - Should state "only six upheld" and list history
   - Should mention 1952 first protest Indianapolis Olympians denied
   - Should mention 6 successful cases
2. Visit https://fadeawayworld.net/successful-nba-protests-the-six-games-that-saw-their-outcomes-overturned
   - Should list all 6 with dates and details matching our data
3. For 2007 MIA-ATL case, visit https://www.espn.com/nba/news/story?id=3192421
   - Should mention Shaq foul out error, Hawks fined $50k, replay 51.9 sec

**Status:** VERIFIED - NBA.com official + multiple independent

### Secondary Errors (NBC, Amazon)

**Claim:** NBC scorebug showed Knicks had timeout when 0 left, April 2026

**Verification:**
1. Visit https://frontofficesports.com/nbc-amazon-crucial-scorebug-errors-nba-postseason/
   - Should mention both NBC and Amazon errors
   - Should mention Knicks-Hawks Game 2, 5.6 sec left, CJ McCollum FTs
   - Should quote Maria Taylor: "due to a data issue, the wrong timeout information was communicated"
2. Visit https://sports.yahoo.com/nba/article/nbc-apologizes-for-data-issue-erroneous-timeout-on-scorebug-that-caused-confusion-in-knicks-hawks-game-2-161013275.html
   - Should confirm same

**Status:** VERIFIED

## Red Flags for Hallucination

- No source link → HALLUCINATION
- Source link doesn't mention claimed fact → HALLUCINATION
- Date in future beyond 2026-10-07 → HALLUCINATION (system date)
- Player not on team at that date → HALLUCINATION
- Score doesn't add up (e.g., 213 vs 214 but impact says 5 points) → ERROR

## Current Dataset Audit

Run this check:

```bash
python -c "
import json
with open('data/discrepancies.json') as f:
    cases = json.load(f)
    for c in cases:
        print(f\"{c['id']}: {c['date']} - {c['verification_status']} - {len(c['sources'])} sources\")
        for s in c['sources']:
            print(f\"  - {s['url']}\")
"
```

Every case must have at least 1 source with type official_nba, espn, or news from reputable outlet.

## How to Add New Case Without Hallucination

1. Find official NBA statement or ESPN/AP report of scoring error
2. Capture exact URLs
3. Fill schema.json fields ONLY from sources, leave unknown blank or "requires_investigation"
4. Set verification_status = "verified" only if 2+ independent sources confirm same facts
5. Set cause_confidence = "confirmed" only if source explicitly states cause (e.g., "human error")
6. Never infer: if source doesn't say period/clock, leave blank and label requires_investigation
7. Preserve original AND corrected values

## Automated Checks

```bash
# Check for missing sources
python src/discrepancy_detector.py  # Should generate statistics.json

# Verify all URLs are reachable (manual)
# Use fetch_page tool to verify each URL returns expected content
```
