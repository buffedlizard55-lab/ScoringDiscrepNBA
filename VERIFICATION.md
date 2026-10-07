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
