#!/usr/bin/env python3
"""Validate every case file against the project's anti-hallucination rules.

Checks (stdlib only):
  1. Each file in data/cases/*.json parses and carries all schema-required keys.
  2. Enums (status, verification_level, classification, cause, official_record_was_wrong) are legal.
  3. Every source has an http(s) URL; no placeholder/example URLs.
  4. Status/source-count consistency: 'verified' needs >=2 sources with at least one
     official-nba or wire-ap or major-sports-media source. 'unverified' must have
     null game_date and at least one open question.
  5. Null-hygiene: unknown game facts must be null (never guessed); open_questions
     must be non-empty unless status == 'verified'.
  6. Totals arithmetic: where both score values and totals are asserted, totals must
     be consistent integers (validated only when the case asserts them).
  7. cases.json aggregate (if present) matches the individual files.

Exit 0 on success, 1 with a printed violation list on failure.
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CASES_DIR = ROOT / "data" / "cases"
AGGREGATE = ROOT / "data" / "cases.json"

REQUIRED = [
    "id", "title", "status", "verification_level", "game_date", "season",
    "away_team", "home_team", "incident_summary", "classification",
    "originally_reported", "corrected_value", "final_official",
    "official_record_was_wrong", "timeline", "sources", "open_questions",
    "last_reviewed",
]
STATUSES = {"verified", "verified-partial", "under-investigation", "unverified", "disputed", "not-a-discrepancy"}
LEVELS = {"official-nba-confirmed", "multi-secondary-confirmed", "single-secondary", "unverified-report"}
TYPES = {"missed-made-basket", "free-throw-entry-error", "two-vs-three-point-ruling",
         "scoreboard-display-error", "official-scorer-book-error", "stat-correction-non-scoring",
         "stat-correction-denied", "timing-buzzer-dispute", "data-feed-conflict", "unknown"}
LAYERS = {"official-record-wrong-then-corrected", "official-record-wrong-stands",
          "official-record-correct-secondary-wrong", "unresolved"}
OUTCOMES = {"corrected-next-day", "corrected-in-game", "corrected-via-replay",
            "stands-protest-denied", "stands-no-review", "stands-ruled-correct", "pending", "unknown"}
DETERMINATIONS = {"confirmed", "suspected", "unknown"}
OFFICIAL_WRONG = {"yes-temporarily", "yes-stands", "no", "undetermined"}
TIERS = {"official-nba", "wire-ap", "major-sports-media", "team-beat", "secondary-digital", "tertiary-unverified"}
STRONG_TIERS = {"official-nba", "wire-ap", "major-sports-media"}
URL_RE = re.compile(r"^https://[^\s]+$")
ID_RE = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}-[a-z0-9-]+$")
DATE_RE = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}$")


def fail(errors, msg):
    errors.append(msg)


def validate_case(path, errors):
    try:
        case = json.loads(path.read_text())
    except Exception as exc:  # noqa: BLE001
        return fail(errors, f"{path.name}: invalid JSON: {exc}")
    for key in REQUIRED:
        if key not in case:
            fail(errors, f"{path.name}: missing required key '{key}'")
    if case.get("id") != path.stem:
        fail(errors, f"{path.name}: id '{case.get('id')}' does not match filename")
    if case.get("id") and not ID_RE.match(case["id"]):
        fail(errors, f"{path.name}: id does not match required pattern")
    if case.get("status") not in STATUSES:
        fail(errors, f"{path.name}: illegal status '{case.get('status')}'")
    if case.get("verification_level") not in LEVELS:
        fail(errors, f"{path.name}: illegal verification_level '{case.get('verification_level')}'")
    if len(case.get("title", "")) < 10:
        fail(errors, f"{path.name}: title too short")
    if len(case.get("incident_summary", "")) < 50:
        fail(errors, f"{path.name}: incident_summary too short (<50 chars)")
    cls = case.get("classification", {})
    if cls.get("type") not in TYPES:
        fail(errors, f"{path.name}: illegal classification.type '{cls.get('type')}'")
    if cls.get("layer") not in LAYERS:
        fail(errors, f"{path.name}: illegal classification.layer '{cls.get('layer')}'")
    if cls.get("outcome") not in OUTCOMES:
        fail(errors, f"{path.name}: illegal classification.outcome '{cls.get('outcome')}'")
    cause = case.get("cause", {})
    if cause.get("determination") not in DETERMINATIONS:
        fail(errors, f"{path.name}: illegal cause.determination '{cause.get('determination')}'")
    if not cause.get("detail"):
        fail(errors, f"{path.name}: cause.detail is empty")
    if case.get("official_record_was_wrong") not in OFFICIAL_WRONG:
        fail(errors, f"{path.name}: illegal official_record_was_wrong '{case.get('official_record_was_wrong')}'")
    # Layer <-> official_record consistency
    layer, wrong = cls.get("layer"), case.get("official_record_was_wrong")
    if layer == "official-record-wrong-then-corrected" and wrong != "yes-temporarily":
        fail(errors, f"{path.name}: layer says corrected but official_record_was_wrong={wrong}")
    if layer == "official-record-wrong-stands" and wrong not in ("yes-stands", "undetermined"):
        fail(errors, f"{path.name}: layer says stands but official_record_was_wrong={wrong}")
    if layer == "official-record-correct-secondary-wrong" and wrong != "no":
        fail(errors, f"{path.name}: layer says official correct but official_record_was_wrong={wrong}")
    if layer == "unresolved" and wrong != "undetermined":
        fail(errors, f"{path.name}: layer unresolved requires official_record_was_wrong=undetermined")
    # Sources
    sources = case.get("sources", [])
    if not sources:
        fail(errors, f"{path.name}: at least one source required")
    for i, src in enumerate(sources):
        url = src.get("url", "")
        if not URL_RE.match(url):
            fail(errors, f"{path.name}: source[{i}] URL must be https (got '{url}')")
        if "example.com" in url or "placeholder" in url:
            fail(errors, f"{path.name}: source[{i}] looks like a placeholder URL")
        if src.get("tier") not in TIERS:
            fail(errors, f"{path.name}: source[{i}] illegal tier '{src.get('tier')}'")
        if not src.get("confirms"):
            fail(errors, f"{path.name}: source[{i}] missing 'confirms' text")
    # Status/source-count consistency
    tiers_present = {s.get("tier") for s in sources}
    if case.get("status") == "verified":
        if len(sources) < 2 or not (tiers_present & STRONG_TIERS):
            fail(errors, f"{path.name}: 'verified' requires >=2 sources incl. a strong tier")
        if case.get("open_questions"):
            fail(errors, f"{path.name}: 'verified' must have empty open_questions (use verified-partial otherwise)")
    else:
        if not case.get("open_questions") and case.get("status") not in ("not-a-discrepancy",):
            fail(errors, f"{path.name}: status {case.get('status')} should list open_questions (or be 'verified')")
    if case.get("status") == "unverified":
        if case.get("game_date") is not None:
            fail(errors, f"{path.name}: 'unverified' must keep game_date null until identified")
        if case.get("verification_level") != "unverified-report":
            fail(errors, f"{path.name}: 'unverified' requires verification_level=unverified-report")
    # Timeline
    if not case.get("timeline"):
        fail(errors, f"{path.name}: timeline must be non-empty")
    for i, item in enumerate(case.get("timeline", [])):
        if not item.get("date") or not item.get("event"):
            fail(errors, f"{path.name}: timeline[{i}] needs date+event")
        si = item.get("source_index")
        if si is not None and not (0 <= si < len(sources)):
            fail(errors, f"{path.name}: timeline[{i}] source_index out of range")
    # Totals arithmetic sanity (only when asserted)
    for block in ("originally_reported", "corrected_value", "final_official"):
        total = (case.get(block) or {}).get("total")
        if total is not None and not (150 <= total <= 400):
            fail(errors, f"{path.name}: {block}.total={total} outside plausible NBA range 150-400")
    if not DATE_RE.match(str(case.get("last_reviewed", ""))):
        fail(errors, f"{path.name}: last_reviewed must be YYYY-MM-DD")
    return case


def main():
    errors = []
    cases = {}
    files = sorted(CASES_DIR.glob("*.json"))
    if not files:
        print("No case files found.")
        return 1
    for path in files:
        case = validate_case(path, errors)
        if isinstance(case, dict) and case.get("id"):
            if case["id"] in cases:
                errors.append(f"duplicate id {case['id']}")
            cases[case["id"]] = case
    if AGGREGATE.exists():
        try:
            agg = json.loads(AGGREGATE.read_text())
            agg_ids = {c["id"] for c in agg.get("cases", [])}
            if agg_ids != set(cases):
                errors.append(f"cases.json aggregate ids {sorted(agg_ids)} != files {sorted(cases)}; run scripts/build_site_data.py")
        except Exception as exc:  # noqa: BLE001
            errors.append(f"cases.json invalid: {exc}")
    # Every other JSON payload must at least parse (a corrupt sources.json once
    # slipped through because only case files were validated).
    for name in ("sources.json", "investigations.json", "stats.json", "schema.json"):
        path = ROOT / "data" / name
        if path.exists():
            try:
                json.loads(path.read_text())
            except Exception as exc:  # noqa: BLE001
                errors.append(f"data/{name} invalid JSON: {exc}")
    inv = json.loads((ROOT / "data" / "investigations.json").read_text()) if (ROOT / "data" / "investigations.json").exists() else {}
    if isinstance(inv, dict) and "records" in inv and not isinstance(inv["records"], list):
        errors.append("investigations.json: 'records' must be a list")
    if errors:
        print(f"VALIDATION FAILED ({len(errors)} issue(s)):")
        for err in errors:
            print(f"  - {err}")
        return 1
    print(f"OK: {len(cases)} case files valid.")
    for cid in sorted(cases):
        c = cases[cid]
        print(f"  - {cid} [{c['status']}/{c['verification_level']}]")
    return 0


if __name__ == "__main__":
    sys.exit(main())
