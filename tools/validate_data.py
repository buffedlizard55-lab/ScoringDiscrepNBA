#!/usr/bin/env python3
"""Validate source-linked research records and monitor-state files offline."""
from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]


def read_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise ValueError(f"{path.relative_to(ROOT)} must contain a JSON object")
    return payload


def issue(errors: list[str], where: str, message: str) -> None:
    errors.append(f"{where}: {message}")


def validate_score(errors: list[str], where: str, score: dict[str, Any]) -> None:
    for field in ("away", "home", "total"):
        value = score.get(field)
        if not isinstance(value, int) or isinstance(value, bool) or value < 0:
            issue(errors, where, f"{field} must be a non-negative integer")
    if all(isinstance(score.get(field), int) and not isinstance(score.get(field), bool) for field in ("away", "home", "total")):
        if score["away"] + score["home"] != score["total"]:
            issue(errors, where, "total does not equal away + home")


def validate_derived_play_score(errors: list[str], where: str, case: dict[str, Any]) -> None:
    context = case.get("playContext", {})
    before = context.get("scoreBefore", {})
    after = context.get("scoreImmediatelyAfter", {})
    if not after.get("isDerived"):
        return
    game = case.get("game", {})
    away_code = game.get("awayTeam", {}).get("code")
    home_code = game.get("homeTeam", {}).get("code")
    affected_team = case.get("affected", {}).get("team")
    if affected_team == game.get("awayTeam", {}).get("name"):
        scoring_code = away_code
    elif affected_team == game.get("homeTeam", {}).get("name"):
        scoring_code = home_code
    else:
        issue(errors, where, "derived play score needs an affected team matching the game's away/home team")
        return
    if not away_code or not home_code or not isinstance(before, dict) or not isinstance(after, dict):
        issue(errors, where, "derived play score needs complete before/after team values")
        return
    for code in (away_code, home_code):
        before_value = before.get(code)
        after_value = after.get(code)
        if not isinstance(before_value, int) or isinstance(before_value, bool) or not isinstance(after_value, int) or isinstance(after_value, bool):
            issue(errors, where, f"derived play score for {code} needs integer before/after values")
            continue
        expected = before_value + (1 if code == scoring_code else 0)
        if after_value != expected:
            issue(errors, where, f"derived successful free-throw score for {code} must be {expected}, not {after_value}")
    if not after.get("derivation") or not after.get("sourceIds"):
        issue(errors, where, "derived play score must explain its arithmetic and cite the reporting/rule sources")


def validate(root: Path = ROOT) -> list[str]:
    errors: list[str] = []
    try:
        cases_data = read_json(root / "data/cases.json")
        source_data = read_json(root / "data/sources.json")
        leads_data = read_json(root / "data/leads.json")
        current_data = read_json(root / "data/monitor/current.json")
        candidates_data = read_json(root / "data/monitor/candidates.json")
        state_data = read_json(root / "data/monitor/state.json")
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        return [f"Unable to load required JSON: {exc}"]

    sources = source_data.get("sources")
    if not isinstance(sources, list):
        issue(errors, "data/sources.json", "sources must be an array")
        sources = []
    source_map: dict[str, dict[str, Any]] = {}
    for index, source in enumerate(sources):
        where = f"data/sources.json:sources[{index}]"
        if not isinstance(source, dict):
            issue(errors, where, "source must be an object")
            continue
        source_id = source.get("id")
        if not isinstance(source_id, str) or not source_id:
            issue(errors, where, "id is required")
            continue
        if source_id in source_map:
            issue(errors, where, f"duplicate source id {source_id}")
        source_map[source_id] = source
        if not str(source.get("url", "")).startswith(("https://", "http://")):
            issue(errors, where, "direct http(s) URL is required")

    cases = cases_data.get("cases")
    if not isinstance(cases, list):
        issue(errors, "data/cases.json", "cases must be an array")
        cases = []
    case_ids: set[str] = set()
    for index, case in enumerate(cases):
        where = f"data/cases.json:cases[{index}]"
        if not isinstance(case, dict):
            issue(errors, where, "case must be an object")
            continue
        case_id = case.get("id")
        if not isinstance(case_id, str) or not case_id:
            issue(errors, where, "id is required")
        elif case_id in case_ids:
            issue(errors, where, f"duplicate case id {case_id}")
        else:
            case_ids.add(case_id)
        if case.get("researchStatus") != "confirmed":
            issue(errors, where, "only confirmed records belong in the confirmed cases file")
        game = case.get("game", {})
        try:
            date.fromisoformat(str(game.get("date", "")))
        except ValueError:
            issue(errors, where, "game.date must be ISO YYYY-MM-DD")
        if not game.get("nbaGameId") or not game.get("awayTeam", {}).get("code") or not game.get("homeTeam", {}).get("code"):
            issue(errors, where, "game id and both team codes are required")
        scores = case.get("scores", {})
        for key in ("originalReported", "corrected", "finalOfficial"):
            value = scores.get(key)
            if not isinstance(value, dict):
                issue(errors, where, f"scores.{key} is required")
            else:
                validate_score(errors, f"{where}:scores.{key}", value)
        if all(isinstance(scores.get(key), dict) for key in ("corrected", "finalOfficial")):
            corrected_values = tuple(scores["corrected"].get(key) for key in ("away", "home", "total"))
            final_values = tuple(scores["finalOfficial"].get(key) for key in ("away", "home", "total"))
            if corrected_values != final_values:
                issue(errors, where, "corrected score and finalOfficial score values must agree for these confirmed corrections")
        validate_derived_play_score(errors, where, case)
        references: list[str] = list(case.get("sourceIds", []))
        for evidence in case.get("evidence", []):
            references.extend(evidence.get("sourceIds", []))
        for event in case.get("timeline", []):
            references.extend(event.get("sourceIds", []))
        for item in case.get("sourceDisagreements", []):
            references.extend(item.get("sourceIds", []))
            for observation in item.get("sourceObservations", []):
                if observation.get("sourceId"):
                    references.append(observation["sourceId"])
            if item.get("observedAt"):
                try:
                    date.fromisoformat(str(item["observedAt"]))
                except ValueError:
                    issue(errors, where, "sourceDisagreement.observedAt must be a valid ISO date")
            else:
                issue(errors, where, "source disagreement needs a capture/observation date")
        affected = case.get("affected", {})
        for line_key in ("originalProviderLine", "originalPlayerLine", "correctedLine"):
            line = affected.get(line_key) or {}
            references.extend(line.get("sourceIds", []))
        play = case.get("playContext", {})
        for score_key in ("scoreBefore", "scoreImmediatelyAfter"):
            references.extend(play.get(score_key, {}).get("sourceIds", []))
        cause = case.get("cause", {})
        references.extend(cause.get("sourceIds", []))
        for source_id in references:
            if source_id not in source_map:
                issue(errors, where, f"unknown source id {source_id}")
        if not case.get("evidence"):
            issue(errors, where, "at least one claim-level evidence entry is required")
        for claim_index, claim in enumerate(case.get("evidence", [])):
            if not claim.get("sourceIds"):
                issue(errors, f"{where}:evidence[{claim_index}]", "every material claim needs a source id")

    coverage = cases_data.get("coverage", {})
    if coverage.get("populationDenominator") is not None or coverage.get("populationRate") is not None:
        issue(errors, "data/cases.json:coverage", "population rate/denominator are intentionally not established")
    if coverage.get("durationStatistic") is not None:
        issue(errors, "data/cases.json:coverage", "correction-duration statistic must remain null without comparable timestamps")
    if coverage.get("confirmedCaseCount") != len(cases):
        issue(errors, "data/cases.json:coverage", "confirmedCaseCount must match the curated cases array")

    leads = leads_data.get("leads")
    if not isinstance(leads, list):
        issue(errors, "data/leads.json", "leads must be an array")
        leads = []
    for index, lead in enumerate(leads):
        where = f"data/leads.json:leads[{index}]"
        if lead.get("status") != "unverified_lead":
            issue(errors, where, "unverified leads must retain the explicit unverified status")
        if lead.get("includeInConfirmedStatistics") is not False:
            issue(errors, where, "unverified lead must be excluded from confirmed statistics")
        if lead.get("game") is not None:
            issue(errors, where, "incomplete lead must not invent a fully identified game")
        for source_id in lead.get("sourceIds", []):
            if source_id not in source_map:
                issue(errors, where, f"unknown source id {source_id}")

    if current_data.get("schemaVersion") != 1:
        issue(errors, "data/monitor/current.json", "unsupported or missing schemaVersion")
    if current_data.get("status") not in {"not_run", "ok", "partial", "error"}:
        issue(errors, "data/monitor/current.json", "status must be not_run/ok/partial/error")
    if not isinstance(current_data.get("sourceStatus"), dict):
        issue(errors, "data/monitor/current.json", "sourceStatus object is required")
    candidates = candidates_data.get("candidates")
    if candidates_data.get("schemaVersion") != 1 or not isinstance(candidates, list):
        issue(errors, "data/monitor/candidates.json", "schemaVersion 1 and candidate array are required")
        candidates = []
    allowed_monitor = {"active_source_divergence", "feed_converged"}
    allowed_investigation = {
        "needs_review", "under_review", "resolved_nba_correction",
        "resolved_secondary_source_only", "resolved_feed_or_match_error", "closed_unresolved",
    }
    terminal_investigations = allowed_investigation - {"needs_review", "under_review"}
    allowed_review = {"unverified", "confirmed", "secondary_source_only", "feed_or_match_error", "reviewed_unresolved"}
    terminal_review = {
        "resolved_nba_correction": "confirmed",
        "resolved_secondary_source_only": "secondary_source_only",
        "resolved_feed_or_match_error": "feed_or_match_error",
        "closed_unresolved": "reviewed_unresolved",
    }
    for index, candidate in enumerate(candidates):
        where = f"data/monitor/candidates.json:candidates[{index}]"
        if not isinstance(candidate, dict):
            issue(errors, where, "candidate must be an object")
            continue
        if candidate.get("monitorStatus") not in allowed_monitor:
            issue(errors, where, "monitorStatus must describe active divergence or feed convergence")
        investigation_status = candidate.get("investigationStatus", "needs_review")
        if investigation_status not in allowed_investigation:
            issue(errors, where, f"unsupported investigationStatus {investigation_status}")
        review_status = candidate.get("reviewStatus", "unverified")
        if review_status not in allowed_review:
            issue(errors, where, f"unsupported reviewStatus {review_status}")
        if investigation_status in terminal_review and review_status != terminal_review[investigation_status]:
            issue(errors, where, f"{investigation_status} requires reviewStatus {terminal_review[investigation_status]}")
        resolution_sources = candidate.get("resolutionSourceIds", [])
        for source_id in resolution_sources:
            if source_id not in source_map:
                issue(errors, where, f"unknown resolution source id {source_id}")
        if investigation_status in terminal_investigations:
            if not candidate.get("reviewer") or not candidate.get("reviewedAt") or not candidate.get("resolution"):
                issue(errors, where, "terminal investigation requires reviewer, reviewedAt, and a resolution note")
            if not resolution_sources:
                issue(errors, where, "terminal investigation requires source IDs documenting the review")
    if not isinstance(state_data.get("games"), dict):
        issue(errors, "data/monitor/state.json", "games object is required")

    observation_log = root / "data/monitor/observations.jsonl"
    if observation_log.exists():
        for line_number, line in enumerate(observation_log.read_text(encoding="utf-8").splitlines(), start=1):
            if not line.strip():
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError as exc:
                issue(errors, f"data/monitor/observations.jsonl:{line_number}", f"invalid JSON: {exc}")
                continue
            if not isinstance(event, dict) or not event.get("observedAt") or not event.get("nbaGameId"):
                issue(errors, f"data/monitor/observations.jsonl:{line_number}", "event needs observedAt and nbaGameId")

    return errors


def main() -> int:
    errors = validate()
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        print(f"Validation failed: {len(errors)} problem(s)", file=sys.stderr)
        return 1
    cases = read_json(ROOT / "data/cases.json")["cases"]
    leads = read_json(ROOT / "data/leads.json")["leads"]
    print(f"Data validation passed: {len(cases)} confirmed case(s), {len(leads)} explicitly unverified lead(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
