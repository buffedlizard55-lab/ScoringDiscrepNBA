"""Deliver alert notifications and record whether delivery actually happened.

Design constraints that shaped this module:

* The scheduled runner has no mailbox, no SMS gateway, and no chat token. What
  it *does* have is an authenticated ``gh`` CLI and a repository. GitHub issues
  therefore carry the notification (and GitHub's own notification settings
  deliver them), the issue URL is written back into ``data/alerts.json``, and
  the site shows the link so a reader can see the real delivery state.
* A notification channel that is not configured must never be reported as
  working. Every dispatch attempt, failure, and skip is written to
  ``data/alert-dispatch-log.json``.
* Delivery failure must not stop the research or break the Pages deployment.
  Failures are recorded, retried up to ``MAX_ATTEMPTS`` polls, and surfaced on
  the site.

Optional channels
-----------------
``SCORING_DISCREPANCY_WEBHOOK_URL``
    If set, the same alert summary is POSTed as JSON (``{"text": ...}`` plus an
    ``alert`` object) which Slack- and Discord-compatible webhooks accept.
    Unset means GitHub issues only, and that is recorded as a skip.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .alerts import DISPATCH_SEVERITIES
from .validation import DataValidationError

MAX_ATTEMPTS = 3
ISSUE_LABEL = "score-alert"
LOG_FILENAME = "alert-dispatch-log.json"
ALERTS_FILENAME = "alerts.json"


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise DataValidationError(f"Cannot read {path}: {exc}") from exc


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def _evidence_lines(alert: dict[str, Any]) -> list[str]:
    lines: list[str] = []
    for entry in alert.get("evidence") or []:
        label = entry.get("label") or "source"
        value = entry.get("value")
        url = entry.get("url")
        if url:
            lines.append(f"- {label}: {value or ''} {url}".rstrip())
        else:
            lines.append(f"- {label}: {value or 'not published'}")
    return lines


def _arithmetic_table(alert: dict[str, Any]) -> list[str]:
    checks = alert.get("arithmetic") or []
    if not checks:
        return []
    lines = [
        "",
        "| Side | Team | Provider final | Derived points | Difference | FG | 3PT | FT |",
        "| --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for check in checks:
        components = check.get("components") or {}
        field_goals = components.get("fieldGoalsMade-attempted") or [None, None]
        threes = components.get("threePointersMade-attempted") or [None, None]
        free_throws = components.get("freeThrowsMade-attempted") or [None, None]
        lines.append(
            "| {side} | {team} | {final} | {derived} | {difference} | {fg} | {tp} | {ft} |".format(
                side=check.get("side"),
                team=check.get("team") or "",
                final=check.get("provider_reported_final"),
                derived=check.get("derived_points"),
                difference=check.get("difference"),
                fg=f"{field_goals[0]}-{field_goals[1]}",
                tp=f"{threes[0]}-{threes[1]}",
                ft=f"{free_throws[0]}-{free_throws[1]}",
            )
        )
    return lines


def build_issue(alert: dict[str, Any]) -> dict[str, Any]:
    """Build the GitHub issue title and body for one alert."""
    severity = str(alert.get("severity") or "unknown").upper()
    title = f"[score-alert][{severity}] {alert.get('title') or alert.get('id')}"
    body_lines = [
        f"**Alert id:** `{alert.get('id')}`",
        f"**Severity:** {severity}",
        f"**Status:** {alert.get('status')}",
        f"**First seen (monitor poll time, UTC):** {alert.get('first_seen_at')}",
        f"**Last seen (monitor poll time, UTC):** {alert.get('last_seen_at')}",
        f"**Saved observations:** {alert.get('occurrences')}",
        "",
        "## What was observed",
        alert.get("summary") or "No summary supplied.",
        "",
        "## Evidence to review",
    ]
    body_lines.extend(_evidence_lines(alert) or ["- No evidence link was attached; treat this as incomplete."])
    body_lines.extend(_arithmetic_table(alert))
    body_lines.extend(["", "## How to check this by hand"])
    body_lines.extend(
        [f"{index}. {step}" for index, step in enumerate(alert.get("review_steps") or [], start=1)]
    )
    body_lines.extend(
        [
            "",
            "## Limits of this alert",
            alert.get("disclaimer") or "",
            "",
            "Monitor poll times are when this project observed the value, not when any provider "
            "published or changed it.",
            "",
            "_Generated by the ScoringDiscrepNBA scheduled monitor; see `ALERTING.md` in the "
            "repository for detection scope and known blind spots._",
        ]
    )
    return {
        "title": title,
        "body": "\n".join(body_lines).strip() + "\n",
        "labels": [ISSUE_LABEL, f"severity:{str(alert.get('severity') or 'unknown')}"],
    }


def _run_gh(gh_path: str, args: list[str], body: str | None = None) -> tuple[bool, str]:
    try:
        completed = subprocess.run(
            [gh_path, *args],
            input=body,
            text=True,
            capture_output=True,
            check=False,
            timeout=90,
        )
    except (OSError, subprocess.SubprocessError) as exc:  # pragma: no cover - environment dependent
        return False, f"{type(exc).__name__}: {exc}"
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout or "").strip().splitlines()
        return False, detail[0] if detail else f"gh exited {completed.returncode}"
    return True, (completed.stdout or "").strip()


def _ensure_labels(gh_path: str, labels: list[str]) -> tuple[bool, str]:
    """Create the alert labels when missing; a label failure is not fatal."""
    for label in labels:
        ok, detail = _run_gh(
            gh_path,
            ["label", "create", label, "--force", "--color", "B60205", "--description", "Automated NBA score-discrepancy alert"],
        )
        if not ok:
            return False, f"label {label}: {detail}"
    return True, "labels present"


def _post_webhook(url: str, alert: dict[str, Any]) -> tuple[bool, str]:
    payload = json.dumps(
        {
            "text": f"[{str(alert.get('severity')).upper()}] {alert.get('title')}\n{alert.get('summary')}\n{alert.get('id')}",
            "alert": alert,
        }
    ).encode("utf-8")
    request = Request(
        url,
        data=payload,
        headers={
            "Content-Type": "application/json",
            "User-Agent": "ScoringDiscrepNBA-monitor/0.1 (+https://github.com/buffedlizard55-lab/ScoringDiscrepNBA)",
        },
        method="POST",
    )
    try:
        with urlopen(request, timeout=20) as response:
            return 200 <= getattr(response, "status", 200) < 300, f"HTTP {getattr(response, 'status', 200)}"
    except (HTTPError, URLError, TimeoutError, OSError) as exc:
        return False, f"{type(exc).__name__}: {exc}"


def dispatch_pending(
    root: str | Path = ".",
    apply: bool = False,
    gh_path: str | None = None,
    env: dict[str, str] | None = None,
    now: str | None = None,
) -> dict[str, Any]:
    """Queue or deliver notifications for pending alerts.

    With ``apply=False`` nothing is sent and the plan is returned, which is what
    ``python3 -m monitor --dispatch-alerts`` does by default.
    """
    root_path = Path(root)
    alerts_path = root_path / "data" / ALERTS_FILENAME
    log_path = root_path / "data" / LOG_FILENAME
    book = _read_json(alerts_path, None)
    if not isinstance(book, dict):
        raise DataValidationError(
            "data/alerts.json is missing. Run 'python3 -m monitor --live' or '--fixtures' first."
        )
    environment = dict(os.environ if env is None else env)
    webhook_url = (environment.get("SCORING_DISCREPANCY_WEBHOOK_URL") or "").strip()
    resolved_gh = gh_path if gh_path is not None else shutil.which("gh")
    dispatch_log = _read_json(log_path, {"schema_version": 1, "entries": []})
    if not isinstance(dispatch_log, dict) or not isinstance(dispatch_log.get("entries"), list):
        dispatch_log = {"schema_version": 1, "entries": []}
    timestamp = now or _utc_now()
    results: list[dict[str, Any]] = []
    log_entries: list[dict[str, Any]] = []

    labels_ready: bool | None = None
    for alert in book.get("alerts", []):
        dispatch = alert.get("dispatch") or {}
        status = dispatch.get("status")
        if status == "pending" and alert.get("severity") in DISPATCH_SEVERITIES:
            attempts = list(dispatch.get("attempts") or [])
            if len(attempts) >= MAX_ATTEMPTS and apply:
                dispatch["status"] = "failed"
                dispatch["reason"] = f"gave up after {MAX_ATTEMPTS} delivery attempts"
                alert["dispatch"] = dispatch
                results.append({"alert_id": alert.get("id"), "action": "give_up", "result": "failed"})
                continue
            issue = build_issue(alert)
            if not apply:
                results.append(
                    {
                        "alert_id": alert.get("id"),
                        "action": "create_issue",
                        "result": "planned",
                        "title": issue["title"],
                    }
                )
                continue
            if not resolved_gh:
                attempt = {"at": timestamp, "channel": "github_issue", "result": "skipped", "detail": "gh CLI not available"}
                attempts.append(attempt)
                dispatch.update({"status": "skipped", "reason": "gh CLI not available on PATH", "attempts": attempts})
                alert["dispatch"] = dispatch
                log_entries.append({"alert_id": alert.get("id"), "action": "create_issue", **attempt})
                results.append({"alert_id": alert.get("id"), "action": "create_issue", "result": "skipped"})
                continue
            if labels_ready is None:
                labels_ready, _ = _ensure_labels(resolved_gh, issue["labels"])
            args = ["issue", "create", "--title", issue["title"], "--body-file", "-"]
            for label in issue["labels"] if labels_ready else []:
                args.extend(["--label", label])
            ok, detail = _run_gh(resolved_gh, args, body=issue["body"])
            attempt = {
                "at": timestamp,
                "channel": "github_issue",
                "result": "sent" if ok else "failed",
                "detail": detail,
            }
            attempts.append(attempt)
            if ok and detail.startswith("http"):
                dispatch.update({"status": "sent", "issue_url": detail, "sent_at": timestamp, "reason": None})
                alert["issue_url"] = detail
            elif ok:
                dispatch.update({"status": "sent", "reason": "gh reported success without a URL", "sent_at": timestamp})
            else:
                dispatch.update({"status": "pending" if len(attempts) < MAX_ATTEMPTS else "failed", "reason": detail})
            dispatch["attempts"] = attempts
            alert["dispatch"] = dispatch
            log_entries.append({"alert_id": alert.get("id"), "action": "create_issue", **attempt})
            results.append(
                {"alert_id": alert.get("id"), "action": "create_issue", "result": attempt["result"], "detail": detail}
            )
        if dispatch.get("close_pending") and dispatch.get("issue_url"):
            if not apply:
                results.append(
                    {"alert_id": alert.get("id"), "action": "close_issue", "result": "planned", "issue_url": dispatch.get("issue_url")}
                )
                continue
            if not resolved_gh:
                log_entries.append(
                    {
                        "alert_id": alert.get("id"),
                        "action": "close_issue",
                        "at": timestamp,
                        "channel": "github_issue",
                        "result": "skipped",
                        "detail": "gh CLI not available",
                    }
                )
                continue
            comment = (
                "The automated condition stopped being observed. "
                f"{((alert.get('resolution') or {}).get('note') or '')} "
                "Kept open for source research if the underlying question is still unresolved."
            ).strip()
            ok, detail = _run_gh(
                resolved_gh,
                ["issue", "close", dispatch["issue_url"], "--comment", comment],
            )
            dispatch = dict(dispatch)
            dispatch["close_pending"] = False
            dispatch["closed_at"] = timestamp if ok else None
            alert["dispatch"] = dispatch
            entry = {
                "alert_id": alert.get("id"),
                "action": "close_issue",
                "at": timestamp,
                "channel": "github_issue",
                "result": "sent" if ok else "failed",
                "detail": detail,
            }
            log_entries.append(entry)
            results.append({"alert_id": alert.get("id"), "action": "close_issue", "result": entry["result"]})

    if apply and webhook_url:
        for alert in book.get("alerts", []):
            dispatch = alert.get("dispatch") or {}
            if dispatch.get("status") != "sent" or dispatch.get("webhook_status") == "sent":
                continue
            ok, detail = _post_webhook(webhook_url, alert)
            dispatch = dict(dispatch)
            dispatch["webhook_status"] = "sent" if ok else "failed"
            dispatch["webhook_detail"] = detail
            alert["dispatch"] = dispatch
            log_entries.append(
                {
                    "alert_id": alert.get("id"),
                    "action": "webhook",
                    "at": timestamp,
                    "channel": "webhook",
                    "result": "sent" if ok else "failed",
                    "detail": detail,
                }
            )
    elif apply and not webhook_url:
        pending_webhook = [
            alert.get("id")
            for alert in book.get("alerts", [])
            if (alert.get("dispatch") or {}).get("status") == "sent"
            and (alert.get("dispatch") or {}).get("webhook_status") != "sent"
        ]
        if pending_webhook:
            log_entries.append(
                {
                    "at": timestamp,
                    "action": "webhook",
                    "channel": "webhook",
                    "result": "skipped",
                    "detail": "SCORING_DISCREPANCY_WEBHOOK_URL is not configured; GitHub issues remain the only delivery channel",
                    "alert_ids": pending_webhook,
                }
            )

    if log_entries:
        dispatch_log["entries"] = list(dispatch_log.get("entries") or []) + log_entries
        dispatch_log["updated_at"] = timestamp
        dispatch_log["note"] = (
            "Append-only delivery log. A failed or skipped entry means the alert was not delivered "
            "through that channel; it does not mean the alert did not happen."
        )
        _write_json(log_path, dispatch_log)

    updated = _write_back(book, alerts_path, apply=apply, timestamp=timestamp)
    return {
        "applied": apply,
        "results": results,
        "log_entries": len(log_entries),
        "webhook_configured": bool(webhook_url),
        "gh_available": bool(resolved_gh),
        "alerts": updated,
    }


def _write_back(book: dict[str, Any], alerts_path: Path, apply: bool, timestamp: str) -> dict[str, Any]:
    alerts = book.get("alerts", [])
    counts = dict(book.get("counts") or {})
    counts.update(
        {
            "open": sum(1 for alert in alerts if alert.get("status") == "open"),
            "pending_dispatch": sum(
                1 for alert in alerts if (alert.get("dispatch") or {}).get("status") == "pending"
            ),
            "delivered": sum(
                1 for alert in alerts if (alert.get("dispatch") or {}).get("status") == "sent"
            ),
            "delivery_failed": sum(
                1 for alert in alerts if (alert.get("dispatch") or {}).get("status") == "failed"
            ),
            "delivery_skipped": sum(
                1 for alert in alerts if (alert.get("dispatch") or {}).get("status") == "skipped"
            ),
        }
    )
    book["counts"] = counts
    if apply:
        book["last_dispatch_at"] = timestamp
    _write_json(alerts_path, book)
    return book
