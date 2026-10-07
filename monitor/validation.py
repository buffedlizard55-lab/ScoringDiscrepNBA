"""Repository-data integrity checks using only Python's standard library."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


class DataValidationError(ValueError):
    pass


def _is_https_url(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    parsed = urlparse(value)
    return parsed.scheme == "https" and bool(parsed.netloc)


def _walk_source_references(value: Any, path: str = "$") -> list[tuple[str, str]]:
    """Collect source_id(s) values so factual claims cannot silently lose links."""
    found: list[tuple[str, str]] = []
    if isinstance(value, dict):
        for key, child in value.items():
            child_path = f"{path}.{key}"
            if key == "source_id" and isinstance(child, str):
                found.append((child_path, child))
            elif key == "source_ids" and isinstance(child, list):
                for index, source_id in enumerate(child):
                    if isinstance(source_id, str):
                        found.append((f"{child_path}[{index}]", source_id))
            found.extend(_walk_source_references(child, child_path))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            found.extend(_walk_source_references(child, f"{path}[{index}]"))
    return found


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise DataValidationError(f"Missing required data file: {path}") from exc
    except json.JSONDecodeError as exc:
        raise DataValidationError(f"Invalid JSON in {path}: {exc}") from exc


def validate_repository_data(root: str | Path = ".") -> list[str]:
    """Validate evidence links, calculations, IDs, and unverified-lead exclusion."""
    root_path = Path(root)
    cases_doc = _read_json(root_path / "data" / "reviewed-cases.json")
    leads_doc = _read_json(root_path / "data" / "leads.json")
    feed = _read_json(root_path / "data" / "live-feed.json")
    state = _read_json(root_path / "data" / "monitor-state.json")
    alerts_path = root_path / "data" / "alerts.json"
    alerts = _read_json(alerts_path) if alerts_path.exists() else None
    errors: list[str] = []

    if not isinstance(cases_doc, dict) or not isinstance(cases_doc.get("cases"), list):
        raise DataValidationError("data/reviewed-cases.json must contain a cases array")
    if not isinstance(leads_doc, dict) or not isinstance(leads_doc.get("leads"), list):
        raise DataValidationError("data/leads.json must contain a leads array")
    if not isinstance(feed, dict) or not isinstance(feed.get("games"), list):
        errors.append("data/live-feed.json must contain a games array")
    if not isinstance(state, dict) or not isinstance(state.get("investigations"), list):
        errors.append("data/monitor-state.json must contain an investigations array")
    if isinstance(feed, dict) and not isinstance(feed.get("source_diagnostics", {}), dict):
        errors.append("data/live-feed.json source_diagnostics must be an object when present")
    if isinstance(feed, dict):
        for source_key, attempts in (feed.get("source_diagnostics") or {}).items():
            if not isinstance(attempts, list):
                errors.append(f"live-feed source_diagnostics.{source_key} must be a list")

    # Alert ledger: every alert must be reviewable (evidence, severity, an
    # explicit unverified marker, and a disclaimer) and no delivery may be
    # claimed without a link to the delivered notification.
    if alerts is not None:
        if not isinstance(alerts, dict) or not isinstance(alerts.get("alerts"), list):
            errors.append("data/alerts.json must contain an alerts array")
        else:
            alert_ids: set[str] = set()
            for alert_index, alert in enumerate(alerts.get("alerts", [])):
                where = f"alerts[{alert_index}]"
                if not isinstance(alert, dict):
                    errors.append(f"{where} must be an object")
                    continue
                alert_id = alert.get("id")
                if not isinstance(alert_id, str) or not alert_id:
                    errors.append(f"{where}.id must be a non-empty string")
                elif alert_id in alert_ids:
                    errors.append(f"Duplicate alert id: {alert_id}")
                else:
                    alert_ids.add(alert_id)
                for field in ("type", "severity", "status", "title", "summary", "first_seen_at"):
                    if not alert.get(field):
                        errors.append(f"{where}.{field} is required")
                if alert.get("verification_status") != "unverified":
                    errors.append(f"{where} must stay explicitly marked unverified")
                if not alert.get("disclaimer"):
                    errors.append(f"{where}.disclaimer is required for automated alerts")
                if not isinstance(alert.get("review_steps"), list) or not alert.get("review_steps"):
                    errors.append(f"{where}.review_steps must list how to check the alert by hand")
                if alert.get("status") == "open":
                    evidence = alert.get("evidence") or []
                    if not any(_is_https_url(entry.get("url")) for entry in evidence if isinstance(entry, dict)):
                        errors.append(f"{where} is open but has no https evidence link")
                dispatch = alert.get("dispatch") or {}
                if dispatch.get("status") == "sent" and not _is_https_url(dispatch.get("issue_url")):
                    errors.append(f"{where} claims delivery without an issue URL")
                if dispatch.get("issue_url") and not _is_https_url(dispatch.get("issue_url")):
                    errors.append(f"{where}.dispatch.issue_url must be an HTTPS link")
            for gap_index, gap in enumerate(alerts.get("coverage_gaps") or []):
                where = f"coverage_gaps[{gap_index}]"
                if not isinstance(gap, dict):
                    errors.append(f"{where} must be an object")
                    continue
                for field in ("source_key", "from", "to", "impact"):
                    if not gap.get(field):
                        errors.append(f"{where}.{field} is required")

    cases = cases_doc.get("cases", [])
    case_ids: set[str] = set()
    for case_index, case in enumerate(cases):
        where = f"cases[{case_index}]"
        if not isinstance(case, dict):
            errors.append(f"{where} must be an object")
            continue
        case_id = case.get("id")
        if not isinstance(case_id, str) or not case_id:
            errors.append(f"{where}.id must be a non-empty string")
        elif case_id in case_ids:
            errors.append(f"Duplicate case id: {case_id}")
        else:
            case_ids.add(case_id)
        if case.get("record_kind") != "confirmed_case":
            errors.append(f"{where} must be explicitly marked confirmed_case")
        if not case.get("unknowns"):
            errors.append(f"{where}.unknowns must list gaps rather than silently implying completeness")

        sources = case.get("sources")
        if not isinstance(sources, list) or not sources:
            errors.append(f"{where}.sources must contain at least one direct source")
            sources = []
        source_ids: set[str] = set()
        for source_index, source in enumerate(sources):
            if not isinstance(source, dict):
                errors.append(f"{where}.sources[{source_index}] must be an object")
                continue
            source_id = source.get("id")
            if not isinstance(source_id, str) or not source_id:
                errors.append(f"{where}.sources[{source_index}].id must be non-empty")
                continue
            if source_id in source_ids:
                errors.append(f"{where} has duplicate source id {source_id}")
            source_ids.add(source_id)
            if not _is_https_url(source.get("url")):
                errors.append(f"{where}.sources[{source_index}].url must be an HTTPS direct link")
            for extra_url in source.get("additional_urls", []):
                if not _is_https_url(extra_url):
                    errors.append(f"{where}.sources[{source_index}] has a non-HTTPS additional URL")

        for path, source_id in _walk_source_references(case):
            if source_id not in source_ids:
                errors.append(f"{where}{path[1:]} references missing source id {source_id!r}")

        scores = case.get("scores", {})
        if not isinstance(scores, dict):
            errors.append(f"{where}.scores must be an object")
            continue
        for score_name in ("originally_reported_final", "corrected_final", "final_official"):
            score = scores.get(score_name)
            if not isinstance(score, dict):
                errors.append(f"{where}.scores.{score_name} must be an object")
                continue
            away, home, total = score.get("away"), score.get("home"), score.get("total")
            if not all(isinstance(value, int) and not isinstance(value, bool) and value >= 0 for value in (away, home, total)):
                errors.append(f"{where}.scores.{score_name} must have non-negative integer scores and total")
            elif away + home != total:
                errors.append(f"{where}.scores.{score_name}.total does not equal away + home")
            if not score.get("source_ids"):
                errors.append(f"{where}.scores.{score_name} needs source_ids")

        event = case.get("event", {})
        if isinstance(event, dict):
            for score_key in ("score_before", "immediately_after_original_entry", "immediately_after_corrected_entry"):
                evidence = event.get(score_key)
                if evidence is not None and isinstance(evidence, dict):
                    if evidence.get("evidence_kind", "").startswith("derived") and not evidence.get("derivation"):
                        errors.append(f"{where}.event.{score_key} is derived but has no derivation note")
                    if not evidence.get("source_ids"):
                        errors.append(f"{where}.event.{score_key} needs source_ids")

    leads = leads_doc.get("leads", [])
    lead_ids: set[str] = set()
    for lead_index, lead in enumerate(leads):
        where = f"leads[{lead_index}]"
        if not isinstance(lead, dict):
            errors.append(f"{where} must be an object")
            continue
        lead_id = lead.get("id")
        if not isinstance(lead_id, str) or not lead_id or lead_id in lead_ids:
            errors.append(f"{where}.id must be unique and non-empty")
        else:
            lead_ids.add(lead_id)
        if lead.get("excluded_from_verified_statistics") is not True:
            errors.append(f"{where} must be excluded from verified statistics")
        if lead.get("status") in {"unidentified_unverified_lead", "unverified_lead"} and lead.get("source_ids"):
            errors.append(f"{where} is explicitly unverified and must not imply independent source verification")

    required_leads = {
        "unidentified-213-vs-214-final-total",
        "unverified-2021-kevin-porter-jr-stat-correction",
    }
    missing_leads = required_leads - lead_ids
    if missing_leads:
        errors.append(f"Required unverified research leads are missing: {', '.join(sorted(missing_leads))}")

    for lead in leads:
        if lead.get("id") in required_leads and lead.get("status") not in {"unidentified_unverified_lead", "unverified_lead"}:
            errors.append(f"{lead.get('id')} must remain explicitly unverified")

    melton = next(
        (case for case in cases if case.get("id") == "nba-2024-10-23-gsw-por-free-throw-correction"),
        None,
    )
    if melton is not None:
        player_line = (melton.get("impact") or {}).get("player_points") or {}
        reported_values = {
            entry.get("value")
            for entry in player_line.get("reported_values", [])
            if isinstance(entry, dict)
        }
        if player_line.get("status") != "disputed_unresolved" or not {11, 12}.issubset(reported_values):
            errors.append("Melton's exact corrected player total must remain an unresolved 11-vs-12 dispute")

    johnson = next(
        (case for case in cases if case.get("id") == "nba-2025-11-07-cle-was-free-throw-correction"),
        None,
    )
    if johnson is not None and not any(
        source.get("url") == "https://x.com/NBAOfficial/status/1987199646020870516"
        for source in johnson.get("sources", [])
    ):
        errors.append("Tre Johnson case must retain the direct NBA Official correction post")

    return errors


def load_state(path: str | Path) -> dict[str, Any]:
    """Load monitor state; use an empty state for a missing first-run file."""
    from .engine import empty_state

    file_path = Path(path)
    if not file_path.exists():
        return empty_state()
    data = _read_json(file_path)
    if not isinstance(data, dict):
        raise DataValidationError("Monitor state root must be an object")
    data.setdefault("investigations", [])
    data.setdefault("final_score_baselines", {})
    return data


def write_json(path: str | Path, value: Any) -> None:
    file_path = Path(path)
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
