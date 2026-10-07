# Contributing - No Hallucinations Policy

## Core Rule: Verify Line by Line

Every factual claim must be traceable to a reliable source with a direct link for independent review.

## How to Add a New Discrepancy Case

1. **Find official source**: NBA.com statement, ESPN/AP report, or official protest record. No blogs, no tweets without official corroboration.

2. **Capture evidence**:
   - URL, title, publisher, date
   - Screenshot or Wayback Machine archive
   - Video link if available

3. **Fill schema**: Follow `data/schema.json`. Required fields:
   - `id`: DISC-YYYYMMDD-AWAY-HOME-SEQ
   - `date`, `teams`, `period_clock`, `relevant_scoring_play`
   - `original_value`, `corrected_value`, `final_official_value`
   - `affected_player`, `cause`, `cause_confidence`
   - `incident_type` (must be one of enum)
   - `nba_official_record_incorrect` (true/false)
   - `sources` (array with at least 1 official or 2 independent)
   - `verification_status`: verified / partially_verified / requires_investigation

4. **Never infer**:
   - If source doesn't say period/clock, leave blank
   - If cause not stated, set cause_confidence = "suspected" or "under_investigation"
   - Label unverified clearly

5. **Test**:
   ```bash
   python -c "import json; json.load(open('data/discrepancies.json'))"
   ```

6. **Update research file**: Create `research/DISC-*.md` with detailed writeup and source verification steps.

## What Counts as Verified?

- **verified**: 2+ independent sources, at least 1 official_nba or espn/ap, facts match
- **partially_verified**: 1 official source but missing details, or 2 secondary that agree
- **requires_investigation**: Found potential discrepancy but need official confirmation
- **disputed**: Sources disagree on facts
- **unverified**: Single source, no corroboration - DO NOT INCLUDE in main dataset, put in investigation queue

## Monitoring System Contributions

- Improve `src/nba_api_client.py` to support more sources
- Add tests for discrepancy detection
- Improve archiving (Wayback Machine integration)
- Add notification channels (Slack, email)

## Pull Request Process

1. Fork, create branch
2. Add case to `data/discrepancies.json`
3. Add research file
4. Run `python src/monitor.py --data-dir data` to regenerate stats
5. Ensure `docs/data.json` and `docs/statistics.json` updated
6. Submit PR with verification steps in description

## Code Style

- Python: black, flake8
- JS: vanilla, no frameworks for GitHub Pages simplicity
- CSS: clean, dark theme, mobile responsive

## Limitations to Address

See README.md "Limitations & Next Work" section.

## Core Values Reminder

- Maximize P(Win) - choose path that maximizes probability project succeeds
- Own the Outcome - own results end-to-end, act without waiting
- Verify line by line, no hallucinations
