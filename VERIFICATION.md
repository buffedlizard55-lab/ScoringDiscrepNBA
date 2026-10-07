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
- **Protest rarity baseline:** ~35 protests filed since 1952 with 3 upheld entering Nov 2014
  (a Nets–Sixers game, 1982-83 Lakers–Spurs, 2007-08 Heat–Hawks) — USA Today research.
  https://eu.usatoday.com/story/sports/nba/2014/11/24/sacramento-kings-vs-memphis-grizzlies-protest-game-history-76ers-nets/70046986/

## 4. Line-by-line verification log

### Pass 2026-10-07-A (founding research pass; reviewer: agent session)

Method: web search + page fetch for each candidate incident; facts admitted only with a direct
URL recorded in the case file. Validator + stats + monitor self-test all green.

| Case | Core facts admitted | Source count / strongest tier | Flags / open items |
|---|---|---|---|
| 2024-10-23 GSW@POR (Melton FT) | date, Q3 2:00, 1-of-2 entered 0-of-2, 139→140 final, next-day league announcement, 223.5/−5.5 lines | 4 / official-nba (NBA.com/AP + @NBAOfficial embed) | Melton's final points disputed across secondaries (11 vs 12) → `disputed_points`; @NBAOfficial text not independently re-fetched |
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

## 5. Re-verification checklist (run before any release/PR)

- [ ] `python3 scripts/validate.py` passes
- [ ] `python3 scripts/compute_stats.py && python3 scripts/build_site_data.py` reproduce committed `data/*.json` + `docs/data/*` with no diff
- [ ] `python3 scripts/monitor.py --self-test` passes
- [ ] Every touched case: sources open (spot-check), `last_reviewed` bumped, open questions current
- [ ] Stats caveat still present on site + payload
