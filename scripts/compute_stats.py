#!/usr/bin/env python3
"""Compute within-collection statistics from verified case files.

IMPORTANT SCOPE CAVEAT (also embedded in the output + shown on the site):
these statistics describe ONLY this repository's research collection. They are
NOT league-wide incidence rates — the collection is not a census of all NBA
games. Every stats payload carries that caveat verbatim.
"""
import json
import re
from collections import Counter
from datetime import date
from pathlib import Path

FULL_DATE = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}$")

ROOT = Path(__file__).resolve().parents[1]
CASES_DIR = ROOT / "data" / "cases"
OUT = ROOT / "data" / "stats.json"

CAVEAT = (
    "Within-collection statistics only. This repository is a growing research collection, "
    "not a census of all NBA games, so these shares describe the collection — not league-wide "
    "incidence rates. Do not cite them as 'X% of NBA games'."
)


def load_cases():
    cases = []
    for path in sorted(CASES_DIR.glob("*.json")):
        cases.append(json.loads(path.read_text()))
    return cases


def main():
    cases = load_cases()
    # Only verified-partial and verified cases feed headline stats; unverified never does.
    verified = [c for c in cases if c["status"] in ("verified", "verified-partial")]
    by_type = Counter(c["classification"]["type"] for c in verified)
    by_layer = Counter(c["classification"]["layer"] for c in verified)
    by_outcome = Counter(c["classification"]["outcome"] for c in verified)
    by_official_wrong = Counter(c["official_record_was_wrong"] for c in verified)
    by_level = Counter(c["verification_level"] for c in verified)

    CORRECTED_OUTCOMES = {"corrected-next-day", "corrected-in-game", "corrected-via-replay"}

    NON_SCORING_TYPES = {"stat-correction-non-scoring", "stat-correction-denied"}

    def corrected_box_value(c):
        # Any corrected outcome whose recorded value changed (score OR stat).
        if c["classification"]["outcome"] not in CORRECTED_OUTCOMES:
            return False
        o, f = c["originally_reported"], c["final_official"]
        return bool(o.get("value") and f.get("value") and o["value"] != f["value"])

    def changed_final(c):
        # The game SCORE changed: a corrected scoring-type case whose values differ.
        # Non-scoring stat corrections (Paul assist, Edwards steal) never count here —
        # their scores were never in dispute — even though their box values changed.
        if c["classification"]["type"] in NON_SCORING_TYPES:
            return False
        return corrected_box_value(c)

    final_changed = [c["id"] for c in verified if changed_final(c)]
    total_changed = [c["id"] for c in verified
                     if (c["originally_reported"].get("total") is not None
                         and c["final_official"].get("total") is not None
                         and c["originally_reported"]["total"] != c["final_official"]["total"])]
    one_point_total = [c["id"] for c in verified
                       if (c["originally_reported"].get("total") is not None
                           and c["final_official"].get("total") is not None
                           and abs(c["originally_reported"]["total"] - c["final_official"]["total"]) == 1)]

    # Resolution lag in days: last full timeline date minus game date, only when both
    # are day-granularity and the endpoint is after the game — and only for outcomes
    # that HAVE a resolution event (a correction or a protest ruling). Publication
    # dates and transient display errors must never masquerade as correction lag.
    RESOLVED_OUTCOMES = {"corrected-next-day", "corrected-in-game", "corrected-via-replay",
                         "stands-protest-denied"}
    lag_days = {}
    for c in verified:
        if c["classification"]["outcome"] not in RESOLVED_OUTCOMES:
            continue
        gd = c.get("game_date")
        if not (gd and FULL_DATE.match(gd)):
            continue
        full_dates = [t["date"] for t in c["timeline"] if FULL_DATE.match(t.get("date", ""))]
        if not full_dates:
            continue
        end = max(full_dates)
        if end > gd:
            lag_days[c["id"]] = (date.fromisoformat(end) - date.fromisoformat(gd)).days
    duration_notes = []
    by_id = {c["id"]: c for c in verified}
    next_day = sorted(i for i, d in lag_days.items() if d == 1)
    nd_corr = [i for i in next_day if by_id[i]["classification"]["outcome"].startswith("corrected")]
    nd_deny = [i for i in next_day if by_id[i]["classification"]["outcome"] == "stands-protest-denied"]
    if nd_corr:
        duration_notes.append(
            f"Next-day corrections (1 day, game to corrected record): {len(nd_corr)} cases — " +
            ", ".join(nd_corr) + ".")
    if nd_deny:
        duration_notes.append(
            f"Protest denied next day (1 day, game to ruling): " + ", ".join(nd_deny) + ".")
    longer = sorted(((i, d) for i, d in lag_days.items() if d > 1), key=lambda x: x[1])
    for i, d in longer:
        duration_notes.append(f"Resolution lag {d} days (game to final ruling/replay): {i}.")
    for c in verified:
        if c.get("duration_note"):
            duration_notes.append(f"{c['id']}: {c['duration_note']}")
    unknown_dur = [c["id"] for c in verified if c["id"] not in lag_days and not c.get("duration_note")]
    if unknown_dur:
        duration_notes.append(
            "Duration unknown or not applicable (stands unreviewed / transient display / single-date record): " +
            ", ".join(sorted(unknown_dur)) + ".")

    stats = {
        "generated": date.today().isoformat(),
        "scope_caveat": CAVEAT,
        "collection_size": len(cases),
        "verified_count": len(verified),
        "status_counts": dict(Counter(c["status"] for c in cases)),
        "verified_type_counts": dict(by_type),
        "verified_layer_counts": dict(by_layer),
        "verified_outcome_counts": dict(by_outcome),
        "verified_official_record_counts": dict(by_official_wrong),
        "verified_level_counts": dict(by_level),
        "final_score_changed_ids": final_changed,
        "corrected_box_value_ids": [c["id"] for c in verified if corrected_box_value(c)],
        "total_changed_ids": total_changed,
        "one_point_total_change_ids": one_point_total,
        "resolution_lag_days": lag_days,
        "duration_notes": duration_notes,
        "headline": {
            "official_record_wrong_share": _share(by_official_wrong, ("yes-temporarily", "yes-stands"), len(verified)),
            "secondary_only_share": _share(by_official_wrong, ("no",), len(verified)),
            "final_changed_share": round(len(final_changed) / len(verified), 3) if verified else 0,
            "most_common_types": ([t for t, n in by_type.most_common() if n == by_type.most_common(1)[0][1]] if by_type else []),
            "most_common_type_count": (by_type.most_common(1)[0][1] if by_type else 0),
        },
        "rarity_notes": [
            "Post-game changes to an NBA final score are rare: the league, Elias Sports Bureau, and sportsbooks all characterize corrections as 'rare' (ESPN, Feb 24 2022), and the NBA's own correction notices call scoring errors rare.",
            "This collection documents 2 next-day one-point final-total corrections (Oct 2024: 243->244; Nov 2025: 262->263).",
            "Uphold-grade protests with replays are rarer still: 3 granted since 1952 entering 2014 (USA Today) — 2 of the 3 are documented in this collection (1982-83 Lakers-Spurs, 2007-08 Heat-Hawks). The third (a Nets-76ers game; date not captured in this pass) is a known research gap; denied protests (2014 Kings-Grizzlies, 2019 Rockets-Spurs) are also documented.",
            "The originating 213-vs-214 cross-source conflict remains UNVERIFIED (game unidentified) — its rarity cannot be quantified until identified.",
        ],
    }
    OUT.write_text(json.dumps(stats, indent=2) + "\n")
    print(f"Wrote {OUT}: {len(verified)} verified of {len(cases)} total.")


def _share(counter, keys, denom):
    if not denom:
        return 0
    return round(sum(counter.get(k, 0) for k in keys) / denom, 3)


if __name__ == "__main__":
    main()
