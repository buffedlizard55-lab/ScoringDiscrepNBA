"""Alert book: turn candidate detections into reviewable, deduplicated alerts.

The monitor never claims that a discrepancy *is* an error. Its job is to notice
that two observations do not agree, keep the evidence, and tell a human that
something needs review. This module turns the machine-readable monitor state
into alert records with a lifecycle, a severity, the evidence needed to check
them by hand, and a notification policy that is deliberately conservative so a
live-game feed lag cannot spam the project.

Alert types
-----------
``cross_source_score_mismatch``
    Two reachable sources disagree on a score. Only alerted once the
    disagreement survives two consecutive polls, because a single poll can
    simply catch one provider mid-update.
``final_score_feed_revision``
    A source changed the score of a game it already served as final. This is
    the closest automatic signal to a scoring correction.
``final_score_internal_inconsistency``
    One provider's published final does not follow from the box-score
    components that same provider publishes.
``source_unavailable``
    A feed could not be polled. While it is down, no comparison against it can
    run, so this is an explicit "we are partly blind" alert rather than a
    silent gap.

Nothing here is a fact about the NBA's official record. Every record carries
``verification_status: "unverified"`` and a disclaimer, and the site shows the
same wording.
"""

from __future__ import annotations

import json
from copy import deepcopy
from typing import Any

ALERT_SCHEMA_VERSION = 1

# How long a source may be unreachable before it becomes an alert. The
# authoritative source is the one whose absence blocks the strongest detector,
# so it is reported sooner than a comparator.
AUTHORITATIVE_DOWN_ALERT_MINUTES = 15
COMPARATOR_DOWN_ALERT_MINUTES = 15
COMPARATOR_DOWN_DISPATCH_MINUTES = 60

# Occurrence milestones: the published ledger refreshes when an alert reaches
# one of these counts, so a long-running condition stays visibly current
# without rewriting the file on every poll.
OCCURRENCE_MILESTONES = (1, 3, 12, 48, 144, 720)
DISPATCH_SEVERITIES = ("critical", "high")
SEVERITY_ORDER = {"critical": 0, "high": 1, "medium": 2, "info": 3}

DISCLAIMER = (
    "Automated candidate detection only. This alert records what two published observations "
    "showed and when. It does not establish that any NBA record was wrong, which source was "
    "correct, or what caused the difference."
)

DISPATCH_POLICY = (
    "Alerts are written to data/alerts.json on every material change. Critical and high-severity "
    "alerts are additionally queued for notification as a GitHub issue by "
    "'python3 -m monitor --dispatch-alerts --apply', which the scheduled workflow runs. "
    "Medium-severity alerts stay on the site until they escalate. An optional webhook "
    "(SCORING_DISCREPANCY_WEBHOOK_URL) can mirror dispatched alerts to Slack, Discord, or a "
    "similar endpoint; when it is not configured, notifications are GitHub-issue only and that "
    "is recorded, not assumed."
)

BOOK_NOTE = (
    "This file is the alert ledger for the automated monitor. It advances only when the set of "
    "alerts materially changes (new alert, severity change, lifecycle change, dispatch result, or "
    "an occurrence milestone), so the scheduled runner does not rewrite it on every poll. Times "
    "are monitor poll times in UTC, not provider publication times."
)

REVIEW_STEPS_COMMON = [
    "Open the official NBA game page for the game and record the final score it publishes.",
    "Open each source listed in the evidence section and record the value it publishes now.",
    "If a league, team, or official-scorer statement exists, link it in the investigation record; "
    "do not record a cause from a mismatch alone.",
    "Keep the original observation and the later value side by side; never overwrite the earlier one.",
]


def _occurrence_bucket(occurrences: int) -> int:
    for milestone in OCCURRENCE_MILESTONES:
        if occurrences <= milestone:
            return milestone
    return OCCURRENCE_MILESTONES[-1]


def empty_book() -> dict[str, Any]:
    return {
        "schema_version": ALERT_SCHEMA_VERSION,
        "last_material_signature": None,
        "alerts": [],
        "coverage_gaps": [],
        "dispatch_policy": DISPATCH_POLICY,
        "note": BOOK_NOTE,
    }


def _alert_id(alert_type: str, key: str) -> str:
    safe_key = "".join(char if char.isalnum() or char in "-_:" else "-" for char in key)
    return f"ALR-{alert_type}-{safe_key}"


def _team_pair_text(item: dict[str, Any]) -> str:
    away = (item.get("away_team") or {}).get("abbreviation") or "AWAY"
    home = (item.get("home_team") or {}).get("abbreviation") or "HOME"
    return f"{away} @ {home}"


def _score_text(score: Any) -> str:
    if not isinstance(score, dict) or score.get("away") is None or score.get("home") is None:
        return "not published"
    return f"{score['away']}-{score['home']}"


def _desired_mismatch_alerts(state: dict[str, Any]) -> dict[str, dict[str, Any]]:
    alerts: dict[str, dict[str, Any]] = {}
    for item in state.get("investigations", []):
        if item.get("detection_type") != "cross_source_score_mismatch":
            continue
        status = item.get("status")
        if status not in {"investigating", "monitoring_for_convergence"}:
            # A first-poll disagreement is not alerted: one provider is often
            # simply a few seconds behind the other on a live possession.
            continue
        details = item.get("current_details") or item.get("first_details") or {}
        nba_score = details.get("nba_score") or {}
        espn_score = details.get("espn_score") or {}
        urls = details.get("source_urls") or {}
        alert_id = _alert_id("cross_source_score_mismatch", str(item.get("game_key")))
        alerts[alert_id] = {
            "id": alert_id,
            "type": "cross_source_score_mismatch",
            "severity": "high",
            "title": (
                f"Score feeds disagree: {_team_pair_text(item)} "
                f"({_score_text(nba_score)} vs {_score_text(espn_score)})"
            ),
            "summary": (
                f"NBA {_score_text(nba_score)} and ESPN {_score_text(espn_score)} disagreed for "
                f"{item.get('consecutive_disagreements', 1)} consecutive polls. Both values are "
                "recorded as observations; neither is treated as the correct one."
            ),
            "game": {
                "game_key": item.get("game_key"),
                "game_id": item.get("game_id"),
                "game_date": item.get("game_date"),
                "matchup": _team_pair_text(item),
            },
            "evidence": [
                entry
                for entry in (
                    {"label": "NBA scoreboard observation", "url": urls.get("nba"), "value": _score_text(nba_score)},
                    {"label": "ESPN scoreboard observation", "url": urls.get("espn"), "value": _score_text(espn_score)},
                    {
                        "label": "Official play-by-play (context, not attribution)",
                        "url": (item.get("latest_observation") or {}).get("play_by_play_source_url"),
                        "value": (
                            ((item.get("latest_observation") or {}).get("latest_official_scoring_play") or {}).get(
                                "description"
                            )
                        ),
                    },
                )
                if entry.get("url")
            ],
            "review_steps": REVIEW_STEPS_COMMON,
            "dispatch": {"status": "pending", "reason": "high severity", "issue_url": None, "attempts": []},
        }
    return alerts


def _desired_revision_alerts(state: dict[str, Any]) -> dict[str, dict[str, Any]]:
    alerts: dict[str, dict[str, Any]] = {}
    for item in state.get("investigations", []):
        if item.get("detection_type") != "final_score_feed_revision":
            continue
        source_key = item.get("source_key") or "unknown"
        previous = item.get("previous_final_score") or {}
        current = item.get("current_final_score") or {}
        alert_id = _alert_id("final_score_feed_revision", f"{source_key}-{item.get('game_key')}")
        alerts[alert_id] = {
            "id": alert_id,
            "type": "final_score_feed_revision",
            "severity": "critical",
            "title": (
                f"{source_key.upper()} changed a final score: {_team_pair_text(item)} "
                f"{_score_text(previous)} -> {_score_text(current)}"
            ),
            "summary": (
                f"The {source_key.upper()} feed first served {_score_text(previous)} as final and later "
                f"served {_score_text(current)}. The change is bounded between the two saved polls "
                f"({(item.get('change_interval') or {}).get('not_before')} and "
                f"{(item.get('change_interval') or {}).get('detected_at')}); the provider's internal "
                "change time is unknown."
            ),
            "game": {
                "game_key": item.get("game_key"),
                "game_id": item.get("game_id"),
                "game_date": item.get("game_date"),
                "matchup": _team_pair_text(item),
            },
            "evidence": [
                entry
                for entry in (
                    {
                        "label": f"{source_key.upper()} feed (current value)",
                        "url": (item.get("first_details") or {}).get("source_url"),
                        "value": _score_text(current),
                    },
                    {
                        "label": "Original value preserved in the investigation record",
                        "url": None,
                        "value": _score_text(previous),
                    },
                )
                if entry.get("url") or entry.get("value")
            ],
            "review_steps": REVIEW_STEPS_COMMON + [
                "Determine whether the league corrected the official record or the provider fixed its "
                "own feed: the two have the same symptom and different meanings.",
            ],
            "dispatch": {"status": "pending", "reason": "critical severity", "issue_url": None, "attempts": []},
        }
    return alerts


def _desired_inconsistency_alerts(state: dict[str, Any]) -> dict[str, dict[str, Any]]:
    alerts: dict[str, dict[str, Any]] = {}
    for item in state.get("investigations", []):
        if item.get("detection_type") != "final_score_internal_inconsistency":
            continue
        if item.get("status") == "resolved":
            continue
        check = item.get("arithmetic_check") or item.get("first_details") or {}
        source_key = item.get("source_key") or "unknown"
        alert_id = _alert_id("final_score_internal_inconsistency", f"{source_key}-{item.get('game_key')}")
        checks = check.get("checks") or []
        mismatched = [entry for entry in checks if entry.get("difference") not in (0, None)]
        summary_parts = [
            f"{entry.get('side', '?')} derived {entry.get('derived_points')} vs published final "
            f"{entry.get('provider_reported_final')} (difference {entry.get('difference')})"
            for entry in mismatched
        ]
        alerts[alert_id] = {
            "id": alert_id,
            "type": "final_score_internal_inconsistency",
            "severity": "critical",
            "title": (
                f"{source_key.upper()} final contradicts its own box score: {_team_pair_text(item)}"
            ),
            "summary": (
                (check.get("note") or "") + " " + "; ".join(summary_parts)
            ).strip(),
            "game": {
                "game_key": item.get("game_key"),
                "game_id": item.get("game_id"),
                "game_date": item.get("game_date"),
                "matchup": _team_pair_text(item),
            },
            "evidence": [
                entry
                for entry in (
                    {"label": f"{source_key.upper()} game data used for the check", "url": check.get("source_url"), "value": _score_text(check.get("provider_reported"))},
                    {
                        "label": "Official NBA game page to compare against",
                        "url": "https://www.nba.com/games",
                        "value": "league schedule and box scores",
                    },
                )
                if entry.get("url")
            ],
            "arithmetic": checks,
            "method": check.get("method"),
            "review_steps": REVIEW_STEPS_COMMON + [
                "Recompute the derived points by hand from the provider's published field-goal, "
                "three-point, and free-throw cells.",
            ],
            "dispatch": {"status": "pending", "reason": "critical severity", "issue_url": None, "attempts": []},
        }
    return alerts


def _desired_source_alerts(state: dict[str, Any], feed: dict[str, Any]) -> dict[str, dict[str, Any]]:
    alerts: dict[str, dict[str, Any]] = {}
    health_state = state.get("source_health_state") or {}
    health = feed.get("source_health") or {}
    for source_key, entry in sorted(health_state.items()):
        if not isinstance(entry, dict):
            continue
        if not entry.get("first_failure_at"):
            continue
        minutes = entry.get("unavailable_minutes")
        if minutes is None:
            continue
        role = entry.get("role") or ("authoritative" if source_key == "nba" else "comparator")
        threshold = (
            AUTHORITATIVE_DOWN_ALERT_MINUTES if role == "authoritative" else COMPARATOR_DOWN_ALERT_MINUTES
        )
        if minutes < threshold:
            # A single failed poll is often a transient timeout; it is recorded
            # in source_health_state but does not become an alert yet.
            continue
        dispatch_eligible = role == "authoritative" or minutes >= COMPARATOR_DOWN_DISPATCH_MINUTES
        alert_id = _alert_id("source_unavailable", source_key)
        url = (health.get(source_key) or {}).get("url")
        alerts[alert_id] = {
            "id": alert_id,
            "type": "source_unavailable",
            "severity": "high" if role == "authoritative" else "medium",
            "title": f"{source_key.upper()} source unavailable for {minutes:g} minutes ({role})",
            "summary": (
                f"The {source_key.upper()} feed has not answered since {entry.get('first_failure_at')} "
                f"({minutes:g} minutes as of the latest poll). While it is unavailable, no comparison "
                "against it can run, so an absence of detections is not evidence that no discrepancy "
                "exists."
            ),
            "game": None,
            "evidence": [
                item
                for item in (
                    {"label": f"{source_key.upper()} endpoint", "url": url, "value": role},
                    {
                        "label": "Last recorded error",
                        "url": None,
                        "value": entry.get("last_error") or (health.get(source_key) or {}).get("error"),
                    },
                )
                if item.get("url") or item.get("value")
            ],
            "review_steps": [
                "Open the endpoint listed in the evidence section from a normal browser and record "
                "whether it responds.",
                "If the endpoint is blocked from the scheduled runner only, record that as an "
                "infrastructure limit, not as a data discrepancy.",
                "Keep the coverage gap visible: an outage window cannot be reported as 'no "
                "discrepancies found'.",
            ],
            "dispatch": {
                "status": "pending" if dispatch_eligible else "not_required",
                "reason": (
                    f"{role} source unavailable for {minutes:g} minutes"
                    if dispatch_eligible
                    else f"comparator down {minutes:g} minutes (notifies after {COMPARATOR_DOWN_DISPATCH_MINUTES})"
                ),
                "issue_url": None,
                "attempts": [],
            },
        }
    return alerts


def _coverage_gaps(state: dict[str, Any]) -> list[dict[str, Any]]:
    gaps = state.get("coverage_gaps") or []
    return [deepcopy(gap) for gap in gaps][-20:]


def detector_status(state: dict[str, Any], feed: dict[str, Any]) -> dict[str, Any]:
    """Describe exactly which detectors ran, so the site cannot overclaim."""
    health = feed.get("source_health") or {}
    comparable = [
        key
        for key, entry in sorted(health.items())
        if isinstance(entry, dict) and entry.get("status") == "ok"
    ]
    checks = state.get("final_game_checks") or {}
    return {
        "cross_source_comparison": {
            "sources_ok": comparable,
            "available": len(comparable) >= 2,
            "blocked_reason": (
                None
                if len(comparable) >= 2
                else "fewer than two sources returned data, so cross-source comparison could not run"
            ),
        },
        "final_score_revision_tracking": {
            "sources_tracked": sorted(
                {
                    key.split(":", 1)[0]
                    for key in (state.get("final_score_baselines") or {})
                }
            ),
            "baselines": len(state.get("final_score_baselines") or {}),
        },
        "single_provider_arithmetic_checks": {
            "games_checked": len(checks),
            "method": "2 * (FGM - 3PM) + 3 * 3PM + FTM from the provider's own box-score components",
            "by_status": {
                status: sum(1 for entry in checks.values() if entry.get("status") == status)
                for status in sorted({entry.get("status") for entry in checks.values() if entry.get("status")})
            },
        },
        "coverage_gaps_recorded": len(state.get("coverage_gaps") or []),
    }


def _material_signature(book: dict[str, Any]) -> str:
    rows = [
        {
            "id": alert.get("id"),
            "status": alert.get("status"),
            "severity": alert.get("severity"),
            "occurrences_bucket": alert.get("occurrences_bucket"),
            "dispatch": (alert.get("dispatch") or {}).get("status"),
            "issue_url": (alert.get("dispatch") or {}).get("issue_url"),
        }
        for alert in book.get("alerts", [])
    ]
    return json.dumps(
        {
            "alerts": rows,
            "coverage_gaps": len(book.get("coverage_gaps") or []),
            "detector_status": book.get("detector_status"),
        },
        sort_keys=True,
        separators=(",", ":"),
    )


def update_book(
    previous_book: dict[str, Any] | None,
    state: dict[str, Any],
    feed: dict[str, Any],
    observed_at: str,
) -> tuple[dict[str, Any], bool]:
    """Merge the current detections into the alert ledger.

    Returns ``(book, material_changed)``. When nothing reviewable changed, the
    caller should keep the previously published file untouched.
    """
    previous_book = deepcopy(previous_book) if previous_book else empty_book()
    existing = {
        alert.get("id"): deepcopy(alert)
        for alert in previous_book.get("alerts", [])
        if isinstance(alert, dict) and alert.get("id")
    }

    desired: dict[str, dict[str, Any]] = {}
    for producer in (
        _desired_mismatch_alerts,
        _desired_revision_alerts,
        _desired_inconsistency_alerts,
    ):
        desired.update(producer(state))
    desired.update(_desired_source_alerts(state, feed))

    for alert_id, wanted in desired.items():
        previous = existing.get(alert_id) or {}
        record = wanted
        record["verification_status"] = "unverified"
        record["disclaimer"] = DISCLAIMER
        record["first_seen_at"] = previous.get("first_seen_at") or observed_at
        record["last_seen_at"] = observed_at
        record["occurrences"] = int(previous.get("occurrences") or 0) + 1
        record["occurrences_bucket"] = _occurrence_bucket(record["occurrences"])
        record["status"] = "open"
        record["resolved_at"] = None
        record["resolution"] = None
        lifecycle = list(previous.get("lifecycle") or [])
        if not previous:
            lifecycle.append({"at": observed_at, "event": "opened", "detail": "first detection"})
        elif previous.get("status") == "resolved":
            lifecycle.append(
                {"at": observed_at, "event": "reopened", "detail": "the condition was observed again"}
            )
        dispatch = previous.get("dispatch") or {}
        if dispatch.get("issue_url"):
            record["dispatch"] = {
                "status": dispatch.get("status") or "sent",
                "reason": dispatch.get("reason"),
                "issue_url": dispatch.get("issue_url"),
                "attempts": dispatch.get("attempts") or [],
                "sent_at": dispatch.get("sent_at"),
                "close_pending": False,
            }
        record["lifecycle"] = lifecycle
        existing[alert_id] = record

    open_ids = set(desired)
    for alert_id, alert in existing.items():
        if alert_id in open_ids or alert.get("status") == "resolved":
            continue
        alert["status"] = "resolved"
        alert["resolved_at"] = observed_at
        resolution = _resolution_for(alert, state)
        alert["resolution"] = resolution
        alert["lifecycle"] = list(alert.get("lifecycle") or []) + [
            {"at": observed_at, "event": "resolved", "detail": resolution.get("note")}
        ]
        dispatch = alert.get("dispatch") or {}
        if dispatch.get("issue_url"):
            dispatch = dict(dispatch)
            dispatch["close_pending"] = True
            alert["dispatch"] = dispatch

    alerts = sorted(
        existing.values(),
        key=lambda item: (
            0 if item.get("status") == "open" else 1,
            SEVERITY_ORDER.get(item.get("severity"), 9),
            str(item.get("detected_at") or item.get("first_seen_at") or ""),
        ),
    )
    for alert in alerts:
        alert.setdefault("detected_at", alert.get("first_seen_at"))

    book: dict[str, Any] = {
        "schema_version": ALERT_SCHEMA_VERSION,
        "generated_at": previous_book.get("generated_at"),
        "alerts": alerts,
        "counts": {
            "open": sum(1 for alert in alerts if alert.get("status") == "open"),
            "open_by_severity": {
                severity: sum(
                    1
                    for alert in alerts
                    if alert.get("status") == "open" and alert.get("severity") == severity
                )
                for severity in ("critical", "high", "medium", "info")
            },
            "resolved": sum(1 for alert in alerts if alert.get("status") == "resolved"),
            "total": len(alerts),
            "pending_dispatch": sum(
                1
                for alert in alerts
                if (alert.get("dispatch") or {}).get("status") == "pending"
            ),
        },
        "coverage_gaps": _coverage_gaps(state),
        "detector_status": detector_status(state, feed),
        "dispatch_policy": DISPATCH_POLICY,
        "note": BOOK_NOTE,
        "unverified_reminder": DISCLAIMER,
    }
    signature = _material_signature(book)
    material_changed = signature != previous_book.get("last_material_signature")
    if material_changed:
        book["generated_at"] = observed_at
    book["last_material_signature"] = signature
    return book, material_changed


def _resolution_for(alert: dict[str, Any], state: dict[str, Any]) -> dict[str, Any]:
    alert_type = alert.get("type")
    game_key = (alert.get("game") or {}).get("game_key")
    if alert_type == "cross_source_score_mismatch":
        for item in state.get("investigations", []):
            if item.get("game_key") == game_key and item.get("detection_type") == alert_type:
                resolution = item.get("resolution")
                if resolution:
                    return {
                        "type": resolution.get("type") or "closed",
                        "note": resolution.get("note"),
                    }
        return {
            "type": "no_longer_observed",
            "note": (
                "The two feeds were not both readable in the latest poll, or the mismatch was not "
                "reproduced. The earlier observations remain in the investigation ledger; this "
                "closure does not establish that either earlier value was correct."
            ),
        }
    if alert_type == "final_score_internal_inconsistency":
        return {
            "type": "arithmetic_now_consistent",
            "note": (
                "A later check found the provider's final consistent with its own box-score "
                "components. That does not explain the earlier values."
            ),
        }
    if alert_type == "source_unavailable":
        source_key = alert_id_source(alert)
        for gap in reversed(state.get("coverage_gaps") or []):
            if gap.get("source_key") == source_key:
                return {
                    "type": "source_recovered",
                    "note": (
                        f"The source answered again. Blind window recorded from {gap.get('from')} to "
                        f"{gap.get('to')}; comparison could not run during that window."
                    ),
                }
        return {"type": "source_recovered", "note": "The source answered again."}
    return {
        "type": "retained_for_review",
        "note": (
            "The automated condition stopped being observed. A feed change is not by itself a "
            "confirmed correction, so this record stays in the ledger for source research."
        ),
    }


def alert_id_source(alert: dict[str, Any]) -> str | None:
    """Extract the source key from a source-unavailable alert id."""
    alert_id = str(alert.get("id") or "")
    prefix = "ALR-source_unavailable-"
    if alert_id.startswith(prefix):
        return alert_id[len(prefix):]
    return None


def resolve_alert(
    book: dict[str, Any], alert_id: str, note: str, resolved_at: str, reviewer: str | None = None
) -> dict[str, Any]:
    """Human/agent action: close one alert with a recorded reason."""
    updated = deepcopy(book)
    for alert in updated.get("alerts", []):
        if alert.get("id") != alert_id:
            continue
        alert["status"] = "resolved"
        alert["resolved_at"] = resolved_at
        alert["resolution"] = {
            "type": "closed_by_review",
            "note": note,
            "reviewer": reviewer,
        }
        alert["lifecycle"] = list(alert.get("lifecycle") or []) + [
            {"at": resolved_at, "event": "closed_by_review", "detail": note}
        ]
        dispatch = alert.get("dispatch") or {}
        if dispatch.get("issue_url"):
            dispatch = dict(dispatch)
            dispatch["close_pending"] = True
            alert["dispatch"] = dispatch
        break
    updated["counts"] = {
        **(updated.get("counts") or {}),
        "open": sum(1 for alert in updated.get("alerts", []) if alert.get("status") == "open"),
    }
    return updated
