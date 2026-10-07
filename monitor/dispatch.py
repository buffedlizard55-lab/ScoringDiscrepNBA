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

import hashlib
import json
import os
import re
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlsplit, urlunsplit
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


def _one_line(value: Any, fallback: str = "not supplied", limit: int = 2_000) -> str:
    text = str(value if value is not None else fallback)
    text = re.sub(r"[\r\n\t\x00-\x1f]+", " ", text).strip()
    return text[:limit] or fallback


def _escape_markdown(value: Any, fallback: str = "not supplied") -> str:
    text = _one_line(value, fallback)
    text = text.replace("<", "&lt;").replace(">", "&gt;").replace("@", "@\u200b")
    return re.sub(r"([\\`*_{}\[\]()#+\-.!|])", r"\\\1", text)


def _safe_issue_url(value: Any) -> str | None:
    text = _one_line(value, "", 2_000)
    if not text:
        return None
    try:
        parsed = urlsplit(text)
        if parsed.scheme.lower() != "https" or not parsed.netloc or parsed.username or parsed.password:
            return None
        path = quote(parsed.path, safe="/%:@!$&'()*+,;=-._~%")
        query = quote(parsed.query, safe="/?@:!$&'()*+,;=-._~%")
        return urlunsplit(("https", parsed.netloc, path, query, ""))
    except ValueError:
        return None


def _issue_marker(alert: dict[str, Any]) -> str:
    alert_id = _one_line(alert.get("id"), "unknown", 200)
    return f"<!-- scoring-discrepancy-alert:{alert_id} -->"


def _body_sha256(body: str) -> str:
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


def _issue_number(issue_url: Any) -> int | None:
    match = re.search(r"/issues/(\d+)(?:$|[?#])", str(issue_url or ""))
    return int(match.group(1)) if match else None


def _evidence_lines(alert: dict[str, Any]) -> list[str]:
    lines: list[str] = []
    for entry in alert.get("evidence") or []:
        label = _escape_markdown(entry.get("label") or "source")
        value = _escape_markdown(entry.get("value") or "not published")
        url = _safe_issue_url(entry.get("url"))
        link = f"[{label}](<{url}>)" if url else label
        lines.append(f"- {link}: {value}")
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
        values = (
            check.get("side"),
            check.get("team") or "",
            check.get("provider_reported_final"),
            check.get("derived_points"),
            check.get("difference"),
            f"{field_goals[0]}-{field_goals[1]}",
            f"{threes[0]}-{threes[1]}",
            f"{free_throws[0]}-{free_throws[1]}",
        )
        lines.append("| " + " | ".join(_escape_markdown(value) for value in values) + " |")
    return lines


def build_issue(alert: dict[str, Any]) -> dict[str, Any]:
    """Build stable, source-linked issue text; volatile poll heartbeats stay out."""
    severity = _one_line(alert.get("severity") or "unknown").upper()
    alert_id = _escape_markdown(alert.get("id"), "unknown")
    alert_title = _one_line(alert.get("title") or alert.get("id"), "Unspecified scoring alert", 220)
    # Issue titles are not Markdown-rendered, but feed-controlled @mentions and
    # angle-bracket markup should still not become active-looking text.
    alert_title = alert_title.replace("<", "&lt;").replace(">", "&gt;").replace("@", "@\u200b")
    title = f"[score-alert][{severity}] {alert_title}"[:256]
    status = _one_line(alert.get("status") or "open", "open", 40)
    occurrence_band = alert.get("occurrences_bucket") or 1
    body_lines = [
        _issue_marker(alert),
        f"**Alert id:** `{alert_id}`",
        f"**Severity:** {severity}",
        f"**Status:** {_escape_markdown(status)}",
        f"**First seen (monitor poll time, UTC):** {_escape_markdown(alert.get('first_seen_at'))}",
        f"**Occurrence milestone:** {_escape_markdown(occurrence_band)}",
        "",
        "## What was observed",
        _escape_markdown(alert.get("summary") or "No summary supplied."),
        "",
        "## Evidence to review",
    ]
    body_lines.extend(_evidence_lines(alert) or ["- No evidence link was attached; treat this as incomplete."])
    body_lines.extend(_arithmetic_table(alert))
    body_lines.extend(["", "## How to check this by hand"])
    body_lines.extend(
        [
            f"{index}. {_escape_markdown(step)}"
            for index, step in enumerate(alert.get("review_steps") or [], start=1)
        ]
    )
    body_lines.extend(
        [
            "",
            "## Limits of this alert",
            _escape_markdown(alert.get("disclaimer") or "Automated candidate detection only; this does not establish that any NBA record was wrong."),
            "",
            "Monitor poll times are when this project observed a value, not when any provider "
            "published or changed it. A feed difference does not identify which source is correct.",
            "",
            "_Generated by the ScoringDiscrepNBA scheduled monitor; see `ALERTING.md` in the "
            "repository for detection scope and known blind spots._",
        ]
    )
    resolution = alert.get("resolution") or {}
    if status == "resolved":
        body_lines.extend(
            [
                "",
                f"**Monitor disposition (not causal):** {_escape_markdown(resolution.get('note') or 'The automated condition is no longer observed; the earlier values remain in the evidence ledger.')}",
                "The monitor will not close this issue. Please review the original observations before a person closes it.",
            ]
        )
    return {
        "title": title,
        "body": "\n".join(body_lines).strip() + "\n",
        "labels": [ISSUE_LABEL, f"severity:{_one_line(alert.get('severity') or 'unknown', 'unknown', 30)}"],
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


def _view_issue(gh_path: str, issue_url: str) -> tuple[dict[str, Any] | None, str]:
    ok, detail = _run_gh(
        gh_path,
        ["issue", "view", issue_url, "--json", "state,title,body,comments"],
    )
    if not ok:
        return None, detail
    try:
        value = json.loads(detail)
    except json.JSONDecodeError:
        return None, "gh issue view returned invalid JSON"
    if not isinstance(value, dict):
        return None, "gh issue view returned an unexpected response"
    return value, "issue loaded"


def _update_comment(alert: dict[str, Any], body_hash: str) -> str:
    alert_id = _one_line(alert.get("id"), "unknown", 200)
    marker = f"<!-- scoring-discrepancy-update:{alert_id}:{body_hash} -->"
    if alert.get("status") == "resolved":
        note = _escape_markdown((alert.get("resolution") or {}).get("note") or "The automated condition is no longer observed.")
        message = (
            "**Non-causal monitor resolution notice.** "
            f"{note} This does not identify which earlier value was correct or why the feeds differed. "
            "The issue remains open for human review."
        )
    else:
        message = (
            "**Monitor update.** The alert's saved score/evidence content changed materially; see the "
            "updated issue body. This remains an unverified source observation and does not determine "
            "which feed is correct."
        )
    return f"{marker}\n\n{message}"


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
        dispatch = dict(alert.get("dispatch") or {})
        alert["dispatch"] = dispatch
        if dispatch.pop("close_pending", False):
            # Migrate older ledgers without ever closing the linked GitHub issue.
            dispatch["resolution_comment_pending"] = True

        severity = alert.get("severity")
        issue = build_issue(alert)
        body_hash = _body_sha256(issue["body"])
        current_status = _one_line(alert.get("status") or "open", "open", 40)
        issue_url = dispatch.get("issue_url")

        if not apply:
            if dispatch.get("status") == "pending" and severity in DISPATCH_SEVERITIES:
                results.append(
                    {
                        "alert_id": alert.get("id"),
                        "action": "create_issue",
                        "result": "planned",
                        "title": issue["title"],
                    }
                )
            elif issue_url and (
                dispatch.get("last_body_sha256") != body_hash
                or dispatch.get("last_status") != current_status
                or dispatch.get("resolution_comment_pending")
            ):
                results.append(
                    {
                        "alert_id": alert.get("id"),
                        "action": "refresh_issue",
                        "result": "planned",
                        "issue_url": issue_url,
                    }
                )
            continue

        if dispatch.get("status") == "pending" and severity in DISPATCH_SEVERITIES and not issue_url:
            attempts = list(dispatch.get("attempts") or [])
            if len(attempts) >= MAX_ATTEMPTS:
                dispatch.update({"status": "failed", "reason": f"gave up after {MAX_ATTEMPTS} delivery attempts"})
                alert["dispatch"] = dispatch
                results.append({"alert_id": alert.get("id"), "action": "give_up", "result": "failed"})
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
            if ok and _safe_issue_url(detail):
                issue_number = _issue_number(detail)
                dispatch.update(
                    {
                        "status": "sent",
                        "issue_url": detail,
                        "issue_number": issue_number,
                        "sent_at": timestamp,
                        "reason": None,
                        "last_body_sha256": body_hash,
                        "last_comment_sha256": body_hash,
                        "last_status": current_status,
                        "human_closed": False,
                        "resolution_comment_pending": False,
                        "reference_mismatch": False,
                    }
                )
                alert["issue_url"] = detail
            elif ok:
                dispatch.update({"status": "sent", "reason": "gh reported success without a valid issue URL", "sent_at": timestamp})
            else:
                dispatch.update({"status": "pending" if len(attempts) < MAX_ATTEMPTS else "failed", "reason": detail})
            dispatch["attempts"] = attempts
            alert["dispatch"] = dispatch
            log_entries.append({"alert_id": alert.get("id"), "action": "create_issue", **attempt})
            results.append(
                {"alert_id": alert.get("id"), "action": "create_issue", "result": attempt["result"], "detail": detail}
            )
            continue

        if not issue_url or dispatch.get("status") != "sent" or dispatch.get("human_closed") is True:
            continue
        # Avoid repository API requests on an unchanged scheduled alert. If the
        # title/body/status changes, load by saved URL/number and verify the
        # stable marker before editing anything.
        comment_needed = dispatch.get("last_comment_sha256") != body_hash
        sync_needed = (
            dispatch.get("last_body_sha256") != body_hash
            or dispatch.get("last_status") != current_status
        )
        if not sync_needed and not comment_needed and not dispatch.get("resolution_comment_pending"):
            continue
        if not resolved_gh:
            results.append({"alert_id": alert.get("id"), "action": "refresh_issue", "result": "skipped", "reason": "gh CLI not available"})
            continue

        issue_ref = str(dispatch.get("issue_number") or issue_url)
        existing, detail = _view_issue(resolved_gh, issue_ref)
        if existing is None:
            log_entries.append(
                {"alert_id": alert.get("id"), "action": "view_issue", "at": timestamp, "channel": "github_issue", "result": "failed", "detail": detail}
            )
            results.append({"alert_id": alert.get("id"), "action": "refresh_issue", "result": "failed", "detail": detail})
            continue
        if str(existing.get("state") or "").lower() == "closed":
            dispatch.update(
                {
                    "human_closed": True,
                    "last_body_sha256": body_hash,
                    "last_status": current_status,
                    "last_comment_sha256": body_hash,
                    "resolution_comment_pending": False,
                    "reason": "issue was closed by a person; automated edits and comments stopped",
                }
            )
            alert["dispatch"] = dispatch
            log_entries.append(
                {"alert_id": alert.get("id"), "action": "respect_human_closure", "at": timestamp, "channel": "github_issue", "result": "skipped", "detail": "issue is closed; no edit, comment, or reopen performed"}
            )
            results.append({"alert_id": alert.get("id"), "action": "respect_human_closure", "result": "skipped"})
            continue
        if str(existing.get("state") or "").lower() != "open":
            log_entries.append(
                {"alert_id": alert.get("id"), "action": "view_issue", "at": timestamp, "channel": "github_issue", "result": "failed", "detail": f"unexpected issue state: {existing.get('state')}"}
            )
            continue
        if _issue_marker(alert) not in str(existing.get("body") or ""):
            dispatch.update(
                {
                    "reference_mismatch": True,
                    "last_body_sha256": body_hash,
                    "last_status": current_status,
                    "last_comment_sha256": body_hash,
                    "resolution_comment_pending": False,
                    "reason": "saved issue reference did not contain this alert's marker; refused to edit",
                }
            )
            alert["dispatch"] = dispatch
            log_entries.append(
                {"alert_id": alert.get("id"), "action": "refuse_mismatched_issue", "at": timestamp, "channel": "github_issue", "result": "skipped", "detail": "stable alert marker did not match"}
            )
            results.append({"alert_id": alert.get("id"), "action": "refuse_mismatched_issue", "result": "skipped"})
            continue

        dispatch["reference_mismatch"] = False
        if existing.get("title") != issue["title"] or existing.get("body") != issue["body"]:
            ok, detail = _run_gh(
                resolved_gh,
                ["issue", "edit", issue_ref, "--title", issue["title"], "--body-file", "-"],
                body=issue["body"],
            )
            if not ok:
                log_entries.append(
                    {"alert_id": alert.get("id"), "action": "refresh_issue", "at": timestamp, "channel": "github_issue", "result": "failed", "detail": detail}
                )
                results.append({"alert_id": alert.get("id"), "action": "refresh_issue", "result": "failed", "detail": detail})
                continue
            log_entries.append(
                {"alert_id": alert.get("id"), "action": "refresh_issue", "at": timestamp, "channel": "github_issue", "result": "sent", "detail": "material alert content refreshed"}
            )
            results.append({"alert_id": alert.get("id"), "action": "refresh_issue", "result": "sent"})

        comment = _update_comment(alert, body_hash)
        comment_marker = comment.splitlines()[0]
        existing_comments = existing.get("comments") if isinstance(existing.get("comments"), list) else []
        already_commented = any(
            isinstance(entry, dict) and comment_marker in str(entry.get("body") or "")
            for entry in existing_comments
        )
        if not already_commented and (comment_needed or dispatch.get("resolution_comment_pending")):
            ok, detail = _run_gh(
                resolved_gh,
                ["issue", "comment", issue_ref, "--body", comment],
            )
            if not ok:
                # The body may already be refreshed. Keep its hash, but leave
                # the comment marker pending so the next poll retries safely.
                dispatch["last_body_sha256"] = body_hash
                dispatch["last_status"] = current_status
                alert["dispatch"] = dispatch
                log_entries.append(
                    {"alert_id": alert.get("id"), "action": "comment_issue", "at": timestamp, "channel": "github_issue", "result": "failed", "detail": detail}
                )
                results.append({"alert_id": alert.get("id"), "action": "comment_issue", "result": "failed", "detail": detail})
                continue
            log_entries.append(
                {"alert_id": alert.get("id"), "action": "comment_issue", "at": timestamp, "channel": "github_issue", "result": "sent", "detail": "non-causal monitor update comment"}
            )
            results.append({"alert_id": alert.get("id"), "action": "comment_issue", "result": "sent"})

        dispatch.update(
            {
                "last_body_sha256": body_hash,
                "last_status": current_status,
                "last_comment_sha256": body_hash,
                "resolution_comment_pending": False,
                "reason": None,
            }
        )
        alert["dispatch"] = dispatch


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
        pending_webhook = []
        for alert in book.get("alerts", []):
            dispatch = dict(alert.get("dispatch") or {})
            if (
                dispatch.get("status") != "sent"
                or dispatch.get("webhook_status") in {"sent", "skipped"}
            ):
                continue
            pending_webhook.append(alert.get("id"))
            dispatch["webhook_status"] = "skipped"
            dispatch["webhook_detail"] = "SCORING_DISCREPANCY_WEBHOOK_URL is not configured"
            alert["dispatch"] = dispatch
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

    if apply and log_entries:
        book["last_dispatch_at"] = timestamp
    updated = _write_back(book, alerts_path)
    return {
        "applied": apply,
        "results": results,
        "log_entries": len(log_entries),
        "webhook_configured": bool(webhook_url),
        "gh_available": bool(resolved_gh),
        "alerts": updated,
    }


def _write_back(book: dict[str, Any], alerts_path: Path) -> dict[str, Any]:
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
    _write_json(alerts_path, book)
    return book
