"""Pure state transitions for candidate discrepancies and final-score revisions."""

from __future__ import annotations

from copy import deepcopy
from typing import Any


STATE_SCHEMA_VERSION = 1
RESOLVED_STATUSES = {"resolved"}

# Retention: the first observations of an event and the most recent ones are
# kept, so a long-running mismatch window cannot grow the committed state file
# without bound while the original observation is preserved.
OBSERVATION_RETENTION_FIRST = 3
OBSERVATION_RETENTION_RECENT = 20

# Volatile bookkeeping fields: they change on every healthy poll, so they must
# not by themselves mark the state as materially changed (otherwise the
# scheduled runner would commit on every single poll).
_VOLATILE_STATE_FIELDS = {
    "source_health_state": ("last_ok_at",),
    "final_game_checks": ("checked_at",),
}

# Outage bookkeeping uses wall-clock duration rather than a poll counter,
# because the scheduled runner is queued and delayed by GitHub Actions: a poll
# count would understate how long a source was actually unavailable. Only the
# first failure time is stored, so a long outage does not rewrite the committed
# state file on every poll.


def empty_state() -> dict[str, Any]:
    return {
        "schema_version": STATE_SCHEMA_VERSION,
        "last_state_change_at": None,
        "source_health": {},
        "source_health_state": {},
        "coverage_gaps": [],
        "final_score_baselines": {},
        "final_game_checks": {},
        "investigations": [],
        "note": "Automated detections are unverified leads, not confirmed NBA scoring errors.",
    }


def game_identity(observation: dict[str, Any]) -> str:
    """Stable per-game key used by investigations and alert records."""
    game_id = observation.get("game_id")
    if game_id:
        return str(game_id)
    away = (observation.get("away_team") or {}).get("abbreviation") or "away"
    home = (observation.get("home_team") or {}).get("abbreviation") or "home"
    return f"{observation.get('game_date') or 'undated'}-{away}-{home}"


def _game_identity(observation: dict[str, Any]) -> str:
    return game_identity(observation)


def _compact_observation(observation: dict[str, Any]) -> dict[str, Any]:
    """Copy only the review-relevant observation data into the event ledger."""
    keep = (
        "observed_at",
        "game_id",
        "game_date",
        "status",
        "status_text",
        "period",
        "clock",
        "away_team",
        "home_team",
        "scores",
        "score_mismatch",
        "source_hashes",
        "source_metadata",
        "latest_official_scoring_play",
        "play_by_play_source_url",
    )
    return {key: deepcopy(observation.get(key)) for key in keep if key in observation}


def _open_investigation(
    investigations: list[dict[str, Any]],
    game_id: str,
    detection_type: str,
    source_key: str | None = None,
) -> dict[str, Any] | None:
    for item in reversed(investigations):
        if (
            item.get("game_key") == game_id
            and item.get("detection_type") == detection_type
            and (source_key is None or item.get("source_key") == source_key)
            and item.get("status") not in RESOLVED_STATUSES
        ):
            return item
    return None


def _create_investigation(
    investigations: list[dict[str, Any]],
    observation: dict[str, Any],
    detection_type: str,
    status: str,
    first_details: dict[str, Any],
    source_key: str | None = None,
) -> dict[str, Any]:
    game_key = _game_identity(observation)
    detected_at = observation.get("observed_at")
    index = 1 + sum(
        1
        for item in investigations
        if item.get("game_key") == game_key
        and item.get("detection_type") == detection_type
        and (source_key is None or item.get("source_key") == source_key)
    )
    event_id = f"{game_key}:{detection_type}:{index}"
    compact = _compact_observation(observation)
    item = {
        "id": event_id,
        "game_key": game_key,
        "game_id": observation.get("game_id"),
        "game_date": observation.get("game_date"),
        "away_team": deepcopy(observation.get("away_team")),
        "home_team": deepcopy(observation.get("home_team")),
        "detection_type": detection_type,
        "source_key": source_key,
        "status": status,
        "verification_status": "unverified",
        "detected_at": detected_at,
        "last_seen_at": detected_at,
        "resolved_at": None,
        "consecutive_disagreements": 1 if detection_type == "cross_source_score_mismatch" else 0,
        "max_consecutive_disagreements": 1 if detection_type == "cross_source_score_mismatch" else 0,
        "consecutive_agreements": 0,
        "observation_count": 1,
        "comparison_checks": (
            [{"observed_at": detected_at, "result": "mismatch"}]
            if detection_type == "cross_source_score_mismatch"
            else []
        ),
        "first_observation": compact,
        "latest_observation": compact,
        "observations": [compact],
        "first_details": deepcopy(first_details),
        "resolution": None,
        "warning": "This automated record identifies a difference only. It does not determine which feed is correct or confirm an NBA scoring error.",
    }
    investigations.append(item)
    return item


def _append_observation(item: dict[str, Any], observation: dict[str, Any]) -> None:
    compact = _compact_observation(observation)
    item["latest_observation"] = compact
    item["last_seen_at"] = observation.get("observed_at")
    item["observation_count"] = int(item.get("observation_count", 0)) + 1
    stored = item.setdefault("observations", [])
    stored.append(compact)
    limit = OBSERVATION_RETENTION_FIRST + OBSERVATION_RETENTION_RECENT
    if len(stored) > limit:
        dropped = len(stored) - limit
        kept_first = stored[:OBSERVATION_RETENTION_FIRST]
        kept_recent = stored[-OBSERVATION_RETENTION_RECENT:]
        item["observations"] = kept_first + kept_recent
        item["observations_truncated_count"] = int(item.get("observations_truncated_count", 0)) + dropped
        item["observations_retention_note"] = (
            f"Only the first {OBSERVATION_RETENTION_FIRST} and most recent "
            f"{OBSERVATION_RETENTION_RECENT} saved observations are retained in this ledger; "
            "the full count is preserved in observation_count and the first snapshot in first_observation."
        )


def _record_comparison_check(
    item: dict[str, Any],
    observed_at: str,
    result: str,
    reason: str | None = None,
    source_health: dict[str, Any] | None = None,
) -> None:
    checks = item.get("comparison_checks")
    if not isinstance(checks, list):
        checks = []
        item["comparison_checks"] = checks
    # One marker breaks a mismatch streak; repeated unavailable polls do not
    # need to create a repository commit every five minutes.
    if (
        result == "incomplete"
        and checks
        and isinstance(checks[-1], dict)
        and checks[-1].get("result") == "incomplete"
    ):
        return
    check = {"observed_at": observed_at, "result": result}
    if reason:
        check["reason"] = reason
    if result == "incomplete":
        check["source_health"] = deepcopy(source_health or {})
    checks.append(check)
    limit = OBSERVATION_RETENTION_FIRST + OBSERVATION_RETENTION_RECENT
    if len(checks) > limit:
        dropped = len(checks) - limit
        item["comparison_checks"] = checks[:OBSERVATION_RETENTION_FIRST] + checks[-OBSERVATION_RETENTION_RECENT:]
        item["comparison_checks_truncated_count"] = (
            int(item.get("comparison_checks_truncated_count", 0)) + dropped
        )


def _process_feed_mismatches(
    state: dict[str, Any],
    observations: list[dict[str, Any]],
    observed_at: str,
    source_health: dict[str, Any],
) -> None:
    # Legacy ledgers did not distinguish a failed/unmatched poll from no poll
    # at all. Reset their streak once during migration, then count only checks
    # explicitly recorded by this version.
    for item in state["investigations"]:
        if (
            item.get("detection_type") == "cross_source_score_mismatch"
            and item.get("status") not in RESOLVED_STATUSES
            and not isinstance(item.get("comparison_checks"), list)
        ):
            item["max_consecutive_disagreements"] = max(
                int(item.get("max_consecutive_disagreements", 0)),
                int(item.get("consecutive_disagreements", 0)),
            )
            item["consecutive_disagreements"] = 0
            item["consecutive_agreements"] = 0
            item["comparison_checks"] = []

    comparable_game_keys: set[str] = set()
    for observation in observations:
        game_key = _game_identity(observation)
        mismatch = observation.get("score_mismatch")
        nba_score = (observation.get("scores") or {}).get("nba") or {}
        espn_score = (observation.get("scores") or {}).get("espn") or {}
        both_scores = all(
            score.get(side) is not None
            for score in (nba_score, espn_score)
            for side in ("away", "home")
        )
        if mismatch in (True, False) and both_scores:
            comparable_game_keys.add(game_key)
        if mismatch is True and both_scores:
            item = _open_investigation(
                state["investigations"], game_key, "cross_source_score_mismatch"
            )
            details = {
                "nba_score": {"away": nba_score.get("away"), "home": nba_score.get("home")},
                "espn_score": {"away": espn_score.get("away"), "home": espn_score.get("home")},
                "source_urls": {
                    "nba": nba_score.get("source_url"),
                    "espn": espn_score.get("source_url"),
                },
            }
            if item is None:
                created = _create_investigation(
                    state["investigations"],
                    observation,
                    "cross_source_score_mismatch",
                    "detected",
                    details,
                )
                _record_comparison_check(created, observed_at, "mismatch")
            else:
                _append_observation(item, observation)
                _record_comparison_check(item, observed_at, "mismatch")
                item["consecutive_disagreements"] = int(item.get("consecutive_disagreements", 0)) + 1
                item["max_consecutive_disagreements"] = max(
                    int(item.get("max_consecutive_disagreements", 0)),
                    item["consecutive_disagreements"],
                )
                item["consecutive_agreements"] = 0
                item["current_details"] = details
                if item["consecutive_disagreements"] >= 2:
                    item["status"] = "investigating"
                continue
        elif mismatch is False and both_scores:
            item = _open_investigation(
                state["investigations"], game_key, "cross_source_score_mismatch"
            )
            if item is not None:
                _append_observation(item, observation)
                _record_comparison_check(item, observed_at, "agreement")
                item["consecutive_agreements"] = int(item.get("consecutive_agreements", 0)) + 1
                item["consecutive_disagreements"] = 0
                if item["consecutive_agreements"] == 1:
                    item["status"] = "monitoring_for_convergence"
                if item["consecutive_agreements"] >= 2:
                    item["status"] = "resolved"
                    item["resolved_at"] = observation.get("observed_at")
                    item["resolution"] = {
                        "type": "feeds_converged",
                        "at": observation.get("observed_at"),
                        "note": "The two observed feed values converged for two consecutive polls. This closes the observed mismatch window only; it does not establish which prior value was correct or why the feeds differed.",
                    }

    both_sources_ok = all(
        (source_health.get(name) or {}).get("status") == "ok"
        for name in ("nba", "espn")
    )
    incomplete_reason = "game_or_score_not_comparable" if both_sources_ok else "source_unavailable_or_invalid"
    for item in state["investigations"]:
        if (
            item.get("detection_type") != "cross_source_score_mismatch"
            or item.get("status") in RESOLVED_STATUSES
        ):
            continue
        game_key = str(item.get("game_key") or _game_identity(item))
        if game_key in comparable_game_keys:
            continue
        _record_comparison_check(
            item,
            observed_at,
            "incomplete",
            incomplete_reason,
            source_health,
        )
        item["consecutive_disagreements"] = 0
        item["consecutive_agreements"] = 0
        if item.get("status") == "monitoring_for_convergence":
            item["status"] = "investigating"


def _process_final_score_revisions(
    state: dict[str, Any], observations: list[dict[str, Any]]
) -> None:
    """Track post-final score changes on every compared source, keyed per source.

    A source's final score changing after it was first served as final is the
    closest automatic signal to a scoring correction, and it is exactly the
    class of event the project exists to explain. It is still only an
    observation: the record may have been corrected, or the provider may have
    been wrong and then fixed its own feed.
    """
    for observation in observations:
        if observation.get("status") != "final":
            continue
        game_key = _game_identity(observation)
        baselines = state.setdefault("final_score_baselines", {})
        for source_key, source_score in sorted((observation.get("scores") or {}).items()):
            if not isinstance(source_score, dict):
                continue
            if source_score.get("away") is None or source_score.get("home") is None:
                continue
            baseline_key = f"{source_key}:{game_key}"
            current = {"away": source_score["away"], "home": source_score["home"]}
            baseline = baselines.get(baseline_key)
            if baseline is None:
                baselines[baseline_key] = {
                    "source_key": source_key,
                    "game_id": observation.get("game_id"),
                    "game_date": observation.get("game_date"),
                    "first_final_seen_at": observation.get("observed_at"),
                    "current_score": current,
                    "team_codes": {
                        "away": (observation.get("away_team") or {}).get("abbreviation"),
                        "home": (observation.get("home_team") or {}).get("abbreviation"),
                    },
                    "source_url": source_score.get("source_url"),
                }
                continue
            previous = baseline.get("current_score") or {}
            if previous == current:
                continue

            revision = _open_investigation(
                state["investigations"], game_key, "final_score_feed_revision", source_key
            )
            details = {
                "source_key": source_key,
                "previous_final_score": deepcopy(previous),
                "new_final_score": current,
                "previous_value_first_seen_at": baseline.get("first_final_seen_at"),
                "change_detected_at": observation.get("observed_at"),
                "change_time_precision": "bounded between saved observations; exact internal record-change time unknown",
                "source_url": source_score.get("source_url"),
                "warning": (
                    "A change in a published feed is not by itself proof that the underlying official "
                    "record was corrected. Feed-side fixes by the provider are a competing explanation."
                ),
            }
            if revision is None:
                _create_investigation(
                    state["investigations"],
                    observation,
                    "final_score_feed_revision",
                    "change_observed_unverified",
                    details,
                    source_key=source_key,
                )
                revision = state["investigations"][-1]
                revision["previous_final_score"] = deepcopy(previous)
                revision["current_final_score"] = current
                revision["change_interval"] = {
                    "not_before": baseline.get("first_final_seen_at"),
                    "detected_at": observation.get("observed_at"),
                    "precision": "between saved polls; not an exact record-change timestamp",
                }
            else:
                _append_observation(revision, observation)
                revision["current_final_score"] = current
                revision["current_details"] = details
            # Preserve the old feed value on the investigation before advancing
            # the baseline. A later revision starts a new investigation only
            # after this one is explicitly resolved by independent evidence.
            baseline["current_score"] = current
            baseline["first_final_seen_at"] = observation.get("observed_at")


def _source_role(source_key: str) -> str:
    return "authoritative" if source_key == "nba" else "comparator"


def _elapsed_minutes(start: Any, end: Any) -> float | None:
    from datetime import datetime

    if not isinstance(start, str) or not isinstance(end, str):
        return None
    try:
        start_dt = datetime.fromisoformat(start.replace("Z", "+00:00"))
        end_dt = datetime.fromisoformat(end.replace("Z", "+00:00"))
    except ValueError:
        return None
    return round((end_dt - start_dt).total_seconds() / 60, 1)


def _process_source_health(
    state: dict[str, Any], source_health: dict[str, Any], observed_at: str | None
) -> None:
    """Record source availability and the blind windows it creates.

    Automated comparison cannot report a discrepancy while a source is down, so
    an outage window is recorded explicitly as a coverage gap rather than being
    silently averaged into "no discrepancies found".
    """
    health_state = state.setdefault("source_health_state", {})
    for source_key, health in sorted(source_health.items()):
        if not isinstance(health, dict):
            continue
        previous = health_state.get(source_key) or {}
        healthy = health.get("status") == "ok"
        if healthy:
            if previous.get("first_failure_at"):
                state.setdefault("coverage_gaps", []).append(
                    {
                        "source_key": source_key,
                        "role": _source_role(source_key),
                        "from": previous.get("first_failure_at"),
                        "to": observed_at,
                        "unavailable_minutes": _elapsed_minutes(
                            previous.get("first_failure_at"), observed_at
                        ),
                        "impact": (
                            "No successful poll of this source during this window. Automated comparison "
                            "against it could not run, so absence of detections here is not evidence of "
                            "absence of discrepancies."
                        ),
                        "last_error": previous.get("last_error"),
                    }
                )
            health_state[source_key] = {
                "role": _source_role(source_key),
                "status": "ok",
                "first_failure_at": None,
                "last_error": None,
                "last_ok_at": observed_at,
            }
            continue
        health_state[source_key] = {
            "role": _source_role(source_key),
            "status": health.get("status"),
            "first_failure_at": previous.get("first_failure_at") or observed_at,
            "last_error": health.get("error"),
            "last_ok_at": previous.get("last_ok_at"),
            "unavailable_minutes": _elapsed_minutes(
                previous.get("first_failure_at") or observed_at, observed_at
            ),
        }


def _process_final_game_consistency(
    state: dict[str, Any],
    checks: list[dict[str, Any]] | None,
    observations: list[dict[str, Any]],
    observed_at: str | None,
) -> None:
    """Record single-provider arithmetic checks for finals and flag mismatches.

    ``checks`` are produced by ``monitor.consistency`` and must already carry
    ``source_key`` and ``game_key``. A passing check is stored (so the coverage
    of the check itself is auditable) and resolves any earlier mismatch record
    for the same source/game only when the arithmetic is consistent.
    """
    if not checks:
        return
    observation_by_game = {_game_identity(item): item for item in observations}
    store = state.setdefault("final_game_checks", {})
    for check in checks:
        source_key = check.get("source_key")
        game_key = check.get("game_key")
        if not source_key or not game_key:
            continue
        store_key = f"{source_key}:{game_key}"
        record = {
            "source_key": source_key,
            "game_key": game_key,
            "game_id": check.get("game_id"),
            "checked_at": observed_at,
            "status": check.get("status"),
            "provider_reported": deepcopy(check.get("provider_reported")),
            "derived": [
                {
                    "side": item.get("side"),
                    "derived_points": item.get("derived_points"),
                    "provider_reported_final": item.get("provider_reported_final"),
                }
                for item in check.get("checks", [])
            ],
            "source_url": check.get("source_url"),
            "method": check.get("method"),
            "note": check.get("note"),
        }
        store[store_key] = record
        observation = observation_by_game.get(game_key)
        if check.get("status") == "inconsistent":
            if observation is None or observation.get("status") != "final":
                continue
            existing = _open_investigation(
                state["investigations"], game_key, "final_score_internal_inconsistency", source_key
            )
            if existing is None:
                _create_investigation(
                    state["investigations"],
                    observation,
                    "final_score_internal_inconsistency",
                    "detected",
                    deepcopy(check),
                    source_key=source_key,
                )
                item = state["investigations"][-1]
                item["arithmetic_check"] = deepcopy(check)
            else:
                _append_observation(existing, observation)
                existing["current_details"] = deepcopy(check)
                existing["arithmetic_check"] = deepcopy(check)
        elif check.get("status") == "consistent":
            existing = _open_investigation(
                state["investigations"], game_key, "final_score_internal_inconsistency", source_key
            )
            if existing is not None:
                _append_observation(existing, observation or {})
                existing["status"] = "resolved"
                existing["resolved_at"] = observed_at
                existing["resolution"] = {
                    "type": "arithmetic_now_consistent",
                    "at": observed_at,
                    "note": (
                        "A later check of the same provider data found the published final consistent "
                        "with its own box-score components. This records that the earlier mismatch no "
                        "longer reproduces; it does not explain the earlier values or establish who "
                        "changed what."
                    ),
                }


def material_state_view(state: dict[str, Any]) -> dict[str, Any]:
    """Return the state without per-poll bookkeeping timestamps.

    Used to decide whether a poll materially changed anything, so the scheduled
    runner does not commit a new revision every five minutes while nothing
    reviewable changed.
    """
    view = deepcopy(state)
    view.pop("last_state_change_at", None)
    for section, fields in _VOLATILE_STATE_FIELDS.items():
        entries = view.get(section)
        if isinstance(entries, dict):
            for entry in entries.values():
                if isinstance(entry, dict):
                    for field in fields:
                        entry.pop(field, None)
    return view


def update_state(
    previous_state: dict[str, Any] | None,
    observations: list[dict[str, Any]],
    observed_at: str,
    source_health: dict[str, Any],
    consistency_checks: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Apply one poll without converting feed differences into verified cases.

    The persisted timestamp advances only when the event ledger, a final-score
    baseline, or source health materially changes. This avoids a Git commit on
    every healthy poll when the observed scores are unchanged.
    """
    state = deepcopy(previous_state) if previous_state else empty_state()
    state.setdefault("schema_version", STATE_SCHEMA_VERSION)
    state.setdefault("final_score_baselines", {})
    state.setdefault("final_game_checks", {})
    state.setdefault("source_health_state", {})
    state.setdefault("coverage_gaps", [])
    state.setdefault("investigations", [])
    before = deepcopy(state)
    state["source_health"] = deepcopy(source_health)

    _process_feed_mismatches(state, observations, observed_at, source_health)
    _process_final_score_revisions(state, observations)
    _process_final_game_consistency(state, consistency_checks, observations, observed_at)
    _process_source_health(state, source_health, observed_at)
    state["note"] = (
        "Automated detections are unverified leads, not confirmed NBA scoring errors. "
        "Feed convergence closes only an observed mismatch window; it does not establish cause. "
        "Source outages are recorded as coverage gaps because no comparison can run while a "
        "source is unavailable."
    )
    if material_state_view(state) != material_state_view(before):
        state["last_state_change_at"] = observed_at
    else:
        state["last_state_change_at"] = (previous_state or {}).get("last_state_change_at")
    return state


def active_investigations(state: dict[str, Any]) -> list[dict[str, Any]]:
    return [item for item in state.get("investigations", []) if item.get("status") != "resolved"]
