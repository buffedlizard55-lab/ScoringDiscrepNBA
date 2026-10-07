"""Pure state transitions for candidate discrepancies and final-score revisions."""

from __future__ import annotations

from copy import deepcopy
from typing import Any


STATE_SCHEMA_VERSION = 1
RESOLVED_STATUSES = {"resolved"}


def empty_state() -> dict[str, Any]:
    return {
        "schema_version": STATE_SCHEMA_VERSION,
        "last_state_change_at": None,
        "source_health": {},
        "final_score_baselines": {},
        "investigations": [],
        "note": "Automated detections are unverified leads, not confirmed NBA scoring errors.",
    }


def _game_identity(observation: dict[str, Any]) -> str:
    game_id = observation.get("game_id")
    if game_id:
        return str(game_id)
    away = (observation.get("away_team") or {}).get("abbreviation") or "away"
    home = (observation.get("home_team") or {}).get("abbreviation") or "home"
    return f"{observation.get('game_date') or 'undated'}-{away}-{home}"


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
    investigations: list[dict[str, Any]], game_id: str, detection_type: str
) -> dict[str, Any] | None:
    for item in reversed(investigations):
        if (
            item.get("game_key") == game_id
            and item.get("detection_type") == detection_type
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
) -> dict[str, Any]:
    game_key = _game_identity(observation)
    detected_at = observation.get("observed_at")
    index = 1 + sum(
        1
        for item in investigations
        if item.get("game_key") == game_key and item.get("detection_type") == detection_type
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
        "status": status,
        "verification_status": "unverified",
        "detected_at": detected_at,
        "last_seen_at": detected_at,
        "resolved_at": None,
        "consecutive_disagreements": 1 if detection_type == "cross_source_score_mismatch" else 0,
        "consecutive_agreements": 0,
        "observation_count": 1,
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
    item.setdefault("observations", []).append(compact)


def _process_feed_mismatches(
    state: dict[str, Any], observations: list[dict[str, Any]]
) -> None:
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
                _create_investigation(
                    state["investigations"],
                    observation,
                    "cross_source_score_mismatch",
                    "detected",
                    details,
                )
            else:
                _append_observation(item, observation)
                item["consecutive_disagreements"] = int(item.get("consecutive_disagreements", 0)) + 1
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


def _process_final_score_revisions(
    state: dict[str, Any], observations: list[dict[str, Any]]
) -> None:
    for observation in observations:
        if observation.get("status") != "final":
            continue
        nba_score = (observation.get("scores") or {}).get("nba") or {}
        if nba_score.get("away") is None or nba_score.get("home") is None:
            continue
        game_key = _game_identity(observation)
        baselines = state.setdefault("final_score_baselines", {})
        current = {"away": nba_score["away"], "home": nba_score["home"]}
        baseline = baselines.get(game_key)
        if baseline is None:
            baselines[game_key] = {
                "game_id": observation.get("game_id"),
                "game_date": observation.get("game_date"),
                "first_final_seen_at": observation.get("observed_at"),
                "current_score": current,
                "team_codes": {
                    "away": (observation.get("away_team") or {}).get("abbreviation"),
                    "home": (observation.get("home_team") or {}).get("abbreviation"),
                },
                "source_url": nba_score.get("source_url"),
            }
            continue
        previous = baseline.get("current_score") or {}
        if previous == current:
            continue

        revision = _open_investigation(
            state["investigations"], game_key, "nba_final_feed_revision"
        )
        details = {
            "previous_nba_feed_score": deepcopy(previous),
            "new_nba_feed_score": current,
            "previous_value_first_seen_at": baseline.get("first_final_seen_at"),
            "change_detected_at": observation.get("observed_at"),
            "change_time_precision": "bounded between saved observations; exact internal record-change time unknown",
            "nba_scoreboard_source_url": nba_score.get("source_url"),
            "warning": "A change in the NBA scoreboard feed is not by itself proof that the underlying official record was corrected.",
        }
        if revision is None:
            _create_investigation(
                state["investigations"],
                observation,
                "nba_final_feed_revision",
                "change_observed_unverified",
                details,
            )
            revision = state["investigations"][-1]
            revision["previous_nba_feed_score"] = deepcopy(previous)
            revision["current_nba_feed_score"] = current
            revision["change_interval"] = {
                "not_before": baseline.get("first_final_seen_at"),
                "detected_at": observation.get("observed_at"),
                "precision": "between saved polls; not an exact NBA record-change timestamp",
            }
        else:
            _append_observation(revision, observation)
            revision["current_nba_feed_score"] = current
            revision["current_details"] = details
        # Preserve the old feed value on the investigation before advancing
        # the baseline. A later revision starts a new investigation only
        # after this one is explicitly resolved by independent evidence, not
        # by polling.
        baseline["current_score"] = current
        baseline["first_final_seen_at"] = observation.get("observed_at")


def update_state(
    previous_state: dict[str, Any] | None,
    observations: list[dict[str, Any]],
    observed_at: str,
    source_health: dict[str, Any],
) -> dict[str, Any]:
    """Apply one poll without converting feed differences into verified cases.

    The persisted timestamp advances only when the event ledger, a final-score
    baseline, or source health materially changes. This avoids a Git commit on
    every healthy poll when the observed scores are unchanged.
    """
    state = deepcopy(previous_state) if previous_state else empty_state()
    state.setdefault("schema_version", STATE_SCHEMA_VERSION)
    state.setdefault("final_score_baselines", {})
    state.setdefault("investigations", [])
    before = deepcopy(state)
    state["source_health"] = deepcopy(source_health)

    _process_feed_mismatches(state, observations)
    _process_final_score_revisions(state, observations)
    state["note"] = (
        "Automated detections are unverified leads, not confirmed NBA scoring errors. "
        "Feed convergence closes only an observed mismatch window; it does not establish cause."
    )
    state.pop("last_state_change_at", None)
    before.pop("last_state_change_at", None)
    if state != before:
        state["last_state_change_at"] = observed_at
    else:
        state["last_state_change_at"] = (previous_state or {}).get("last_state_change_at")
    return state


def active_investigations(state: dict[str, Any]) -> list[dict[str, Any]]:
    return [item for item in state.get("investigations", []) if item.get("status") != "resolved"]
