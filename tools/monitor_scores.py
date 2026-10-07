#!/usr/bin/env python3
"""Compare current NBA and ESPN score feeds and preserve meaningful changes.

A score disagreement is recorded as an unverified source divergence. This script
never decides which provider is correct and never infers a cause from nearby plays.
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable

NBA_SCOREBOARD_URL = "https://cdn.nba.com/static/json/liveData/scoreboard/todaysScoreboard_00.json"
ESPN_SCOREBOARD_URL = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard"
NBA_PBP_URL = "https://cdn.nba.com/static/json/liveData/playbyplay/playbyplay_{game_id}.json"
POLL_INTERVAL_MINUTES = 15
USER_AGENT = "ScoringDiscrepNBA/1.0 (evidence-first research monitor; public feeds only)"

TEAM_ALIASES = {
    "GS": "GSW", "GSW": "GSW",
    "SA": "SAS", "SAS": "SAS",
    "NY": "NYK", "NYK": "NYK",
    "NO": "NOP", "NOP": "NOP",
    "WSH": "WAS", "WAS": "WAS",
    "UTAH": "UTA", "UTA": "UTA",
}

JsonFetcher = Callable[[str], dict[str, Any]]


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def as_utc_string(value: datetime | None = None) -> str:
    value = value or utc_now()
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    raw = str(value).strip()
    if not raw:
        return None
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(raw)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def normalise_team_code(value: Any) -> str | None:
    if value is None:
        return None
    code = str(value).strip().upper()
    if not code:
        return None
    return TEAM_ALIASES.get(code, code)


def score_value(value: Any) -> int | None:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value if value >= 0 else None
    if isinstance(value, float):
        return int(value) if value >= 0 and value.is_integer() else None
    raw = str(value).strip()
    if not raw:
        return None
    try:
        numeric = float(raw)
    except (TypeError, ValueError):
        return None
    if numeric < 0 or not numeric.is_integer():
        return None
    return int(numeric)


def _team_from_nba(raw: dict[str, Any]) -> dict[str, Any]:
    code = normalise_team_code(raw.get("teamTricode") or raw.get("teamCode") or raw.get("abbreviation"))
    return {
        "code": code,
        "name": raw.get("teamName") or raw.get("teamCity") or code or "Unknown team",
        "score": score_value(raw.get("score")),
    }


def parse_nba_scoreboard(payload: dict[str, Any]) -> list[dict[str, Any]]:
    """Parse the public NBA CDN scoreboard shape without turning absent scores into zero."""
    scoreboard = payload.get("scoreboard", payload)
    if not isinstance(scoreboard, dict):
        raise ValueError("NBA scoreboard payload has no object-valued scoreboard")
    games = scoreboard.get("games")
    if not isinstance(games, list):
        raise ValueError("NBA scoreboard payload has no games array")
    result: list[dict[str, Any]] = []
    for raw in games:
        if not isinstance(raw, dict):
            continue
        home_raw = raw.get("homeTeam") or {}
        away_raw = raw.get("awayTeam") or {}
        if not isinstance(home_raw, dict) or not isinstance(away_raw, dict):
            continue
        game_id = str(raw.get("gameId") or raw.get("gameID") or "").strip()
        home = _team_from_nba(home_raw)
        away = _team_from_nba(away_raw)
        if not game_id or not home["code"] or not away["code"]:
            continue
        result.append({
            "nbaGameId": game_id,
            "gameDate": raw.get("gameEt") or raw.get("gameDateEst") or scoreboard.get("gameDate"),
            "startTimeUtc": raw.get("gameTimeUTC"),
            "awayTeam": away,
            "homeTeam": home,
            "period": score_value(raw.get("period")),
            "clock": raw.get("gameClock"),
            "statusText": raw.get("gameStatusText") or raw.get("gameStatusTextShort") or "",
            "statusBucket": _nba_status_bucket(raw),
            "gameStatus": raw.get("gameStatus"),
            "sourceUrl": NBA_SCOREBOARD_URL,
        })
    return result


def _nba_status_bucket(raw: dict[str, Any]) -> str:
    status = score_value(raw.get("gameStatus"))
    if status == 1:
        return "pre"
    if status == 2:
        return "live"
    if status == 3:
        return "post"
    text = str(raw.get("gameStatusText") or "").lower()
    if "final" in text:
        return "post"
    if any(word in text for word in ("q1", "q2", "q3", "q4", "ot", "half", "live")):
        return "live"
    return "unknown"


def _team_from_espn(raw: dict[str, Any]) -> dict[str, Any]:
    team = raw.get("team") if isinstance(raw.get("team"), dict) else raw
    code = normalise_team_code(team.get("abbreviation") or team.get("shortDisplayName"))
    return {
        "code": code,
        "name": team.get("displayName") or team.get("shortDisplayName") or code or "Unknown team",
        "score": score_value(raw.get("score")),
    }


def parse_espn_scoreboard(payload: dict[str, Any]) -> list[dict[str, Any]]:
    """Parse ESPN's public scoreboard response into normalized home/away rows."""
    events = payload.get("events")
    if not isinstance(events, list):
        raise ValueError("ESPN scoreboard payload has no events array")
    result: list[dict[str, Any]] = []
    for event in events:
        if not isinstance(event, dict):
            continue
        competitions = event.get("competitions") or []
        if not competitions or not isinstance(competitions[0], dict):
            continue
        competition = competitions[0]
        competitors = competition.get("competitors") or []
        home_raw = next((team for team in competitors if team.get("homeAway") == "home"), None)
        away_raw = next((team for team in competitors if team.get("homeAway") == "away"), None)
        if not isinstance(home_raw, dict) or not isinstance(away_raw, dict):
            continue
        home = _team_from_espn(home_raw)
        away = _team_from_espn(away_raw)
        if not home["code"] or not away["code"]:
            continue
        status = competition.get("status") or event.get("status") or {}
        status_type = status.get("type") or {}
        result.append({
            "espnEventId": str(event.get("id") or ""),
            "date": event.get("date"),
            "awayTeam": away,
            "homeTeam": home,
            "period": score_value(status.get("period")),
            "clock": status.get("displayClock") or status.get("clock"),
            "statusText": status_type.get("detail") or status_type.get("shortDetail") or status_type.get("description") or "",
            "statusBucket": status_type.get("state") or "unknown",
            "sourceUrl": ESPN_SCOREBOARD_URL,
        })
    return result


def fetch_espn_games(now: datetime, fetch_json: JsonFetcher) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Check UTC yesterday/today/tomorrow to cover date/time-zone boundaries."""
    today = now.astimezone(timezone.utc).date()
    games_by_id: dict[str, dict[str, Any]] = {}
    successful_dates: list[str] = []
    errors: list[str] = []
    for offset in (-1, 0, 1):
        date_value = today + timedelta(days=offset)
        date_string = date_value.strftime("%Y%m%d")
        url = f"{ESPN_SCOREBOARD_URL}?{urllib.parse.urlencode({'dates': date_string})}"
        try:
            payload = fetch_json(url)
            games = parse_espn_scoreboard(payload)
            successful_dates.append(date_string)
            for game in games:
                key = game.get("espnEventId") or f"{game['awayTeam']['code']}-{game['homeTeam']['code']}-{game.get('date')}"
                games_by_id[key] = game
        except Exception as exc:  # Each date request is isolated; partial feed success remains useful.
            errors.append(f"{date_string}: {_safe_error(exc)}")
    if not successful_dates:
        raise RuntimeError("; ".join(errors) or "ESPN returned no valid date response")
    status = {
        "ok": True,
        "url": ESPN_SCOREBOARD_URL,
        "eventCount": len(games_by_id),
        "successfulDateQueries": successful_dates,
        "warnings": errors,
    }
    return list(games_by_id.values()), status


def _same_teams(nba_game: dict[str, Any], espn_game: dict[str, Any]) -> bool:
    return (
        nba_game["awayTeam"]["code"] == espn_game["awayTeam"]["code"]
        and nba_game["homeTeam"]["code"] == espn_game["homeTeam"]["code"]
    )


def _nearest_candidate(candidates: list[dict[str, Any]], nba_game: dict[str, Any]) -> tuple[dict[str, Any] | None, str]:
    if not candidates:
        return None, "no_secondary_match"
    nba_time = parse_datetime(nba_game.get("startTimeUtc"))
    if nba_time:
        dated: list[tuple[float, dict[str, Any]]] = []
        undated: list[dict[str, Any]] = []
        for candidate in candidates:
            espn_time = parse_datetime(candidate.get("date"))
            if espn_time:
                distance = abs((espn_time - nba_time).total_seconds())
                if distance <= 36 * 60 * 60:
                    dated.append((distance, candidate))
            else:
                undated.append(candidate)
        if dated:
            dated.sort(key=lambda pair: pair[0])
            if len(dated) > 1 and dated[1][0] - dated[0][0] < 2 * 60 * 60:
                return None, "ambiguous_secondary_match"
            return dated[0][1], "matched"
        if len(candidates) == 1 and undated:
            return undated[0], "matched"
        return None, "no_secondary_match"
    if len(candidates) == 1:
        return candidates[0], "matched"
    return None, "ambiguous_secondary_match"


def compare_scoreboards(nba_games: list[dict[str, Any]], espn_games: list[dict[str, Any]]) -> list[dict[str, Any]]:
    comparisons: list[dict[str, Any]] = []
    for nba_game in nba_games:
        candidates = [game for game in espn_games if _same_teams(nba_game, game)]
        espn_game, match_status = _nearest_candidate(candidates, nba_game)
        nba_score = {"away": nba_game["awayTeam"]["score"], "home": nba_game["homeTeam"]["score"]}
        espn_score = None
        if espn_game:
            espn_score = {"away": espn_game["awayTeam"]["score"], "home": espn_game["homeTeam"]["score"]}
        score_values_present = bool(
            espn_score is not None
            and nba_score["away"] is not None and nba_score["home"] is not None
            and espn_score["away"] is not None and espn_score["home"] is not None
        )
        mismatch = score_values_present and nba_score != espn_score
        away_name = nba_game["awayTeam"]["name"]
        home_name = nba_game["homeTeam"]["name"]
        comparisons.append({
            "nbaGameId": nba_game["nbaGameId"],
            "gameDate": nba_game.get("gameDate"),
            "matchup": f"{nba_game['awayTeam']['code']} @ {nba_game['homeTeam']['code']}",
            "awayTeam": {"code": nba_game["awayTeam"]["code"], "name": away_name},
            "homeTeam": {"code": nba_game["homeTeam"]["code"], "name": home_name},
            "nbaScore": nba_score,
            "espnScore": espn_score,
            "scoreValuesPresent": score_values_present,
            "scoreMismatch": bool(mismatch),
            "matchStatus": match_status,
            "period": nba_game.get("period") or (espn_game or {}).get("period"),
            "clock": nba_game.get("clock") or (espn_game or {}).get("clock"),
            "statusText": nba_game.get("statusText") or "",
            "espnStatusText": (espn_game or {}).get("statusText") or "",
            "nbaStatusBucket": nba_game.get("statusBucket"),
            "espnStatusBucket": (espn_game or {}).get("statusBucket"),
            "nbaSourceUrl": NBA_SCOREBOARD_URL,
            "espnSourceUrl": ESPN_SCOREBOARD_URL,
        })
    return comparisons


def parse_pbp_context(payload: dict[str, Any], limit: int = 8) -> list[dict[str, Any]]:
    game = payload.get("game", payload)
    actions = game.get("actions") if isinstance(game, dict) else None
    if not isinstance(actions, list):
        return []
    context: list[dict[str, Any]] = []
    for action in actions[-limit:]:
        if not isinstance(action, dict):
            continue
        context.append({
            "period": score_value(action.get("period")),
            "clock": action.get("clock"),
            "description": action.get("description") or action.get("actionType") or "Play description unavailable",
            "playerName": action.get("playerName") or action.get("playerNameI"),
            "homeScore": score_value(action.get("scoreHome")),
            "awayScore": score_value(action.get("scoreAway")),
        })
    return context


def _source_observation(comparison: dict[str, Any], observed_at: str) -> dict[str, Any]:
    return {
        "observedAt": observed_at,
        "nbaGameId": comparison["nbaGameId"],
        "gameDate": comparison.get("gameDate"),
        "matchup": comparison.get("matchup"),
        "nbaScore": comparison.get("nbaScore"),
        "espnScore": comparison.get("espnScore"),
        "period": comparison.get("period"),
        "clock": comparison.get("clock"),
        "nbaStatusText": comparison.get("statusText"),
        "espnStatusText": comparison.get("espnStatusText"),
        "nbaSourceUrl": comparison.get("nbaSourceUrl"),
        "espnSourceUrl": comparison.get("espnSourceUrl"),
    }


def _comparison_signature(comparison: dict[str, Any]) -> dict[str, Any]:
    return {
        "nbaScore": comparison.get("nbaScore"),
        "espnScore": comparison.get("espnScore"),
        "nbaStatusBucket": comparison.get("nbaStatusBucket"),
        "espnStatusBucket": comparison.get("espnStatusBucket"),
        "period": comparison.get("period"),
        "scoreMismatch": comparison.get("scoreMismatch"),
    }


def _load_json(path: Path, default: dict[str, Any]) -> dict[str, Any]:
    if not path.exists():
        return default
    try:
        with path.open(encoding="utf-8") as handle:
            result = json.load(handle)
        return result if isinstance(result, dict) else default
    except (json.JSONDecodeError, OSError):
        return default


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(path)


def _append_jsonl(path: Path, events: list[dict[str, Any]]) -> None:
    if not events:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        for event in events:
            handle.write(json.dumps(event, ensure_ascii=False, sort_keys=True) + "\n")


def _fetch_pbp(game_id: str, fetch_json: JsonFetcher) -> dict[str, Any]:
    url = NBA_PBP_URL.format(game_id=urllib.parse.quote(game_id, safe=""))
    try:
        payload = fetch_json(url)
        actions = parse_pbp_context(payload)
        return {
            "url": url,
            "mode": "nearby_feed_context_not_causal",
            "actions": actions,
            "note": "Nearby official-feed actions are context only; temporal proximity does not establish cause.",
            "retrievalError": None if actions else "Feed returned no recognized action rows.",
        }
    except Exception as exc:
        return {
            "url": url,
            "mode": "nearby_feed_context_not_causal",
            "actions": [],
            "note": "Play-by-play retrieval failed; no cause is inferred.",
            "retrievalError": _safe_error(exc),
        }


def update_durable_observations(
    root: Path,
    comparisons: list[dict[str, Any]],
    observed_at: str,
    fetch_json: JsonFetcher,
    include_pbp: bool = True,
) -> tuple[list[dict[str, Any]], bool]:
    """Append score/status transitions and maintain candidate lifecycle state."""
    monitor_dir = root / "data" / "monitor"
    state_path = monitor_dir / "state.json"
    candidates_path = monitor_dir / "candidates.json"
    state = _load_json(state_path, {"schemaVersion": 1, "lastEventAt": None, "games": {}})
    if not isinstance(state.get("games"), dict):
        state["games"] = {}
    container = _load_json(candidates_path, {"schemaVersion": 1, "candidates": []})
    if not isinstance(container.get("candidates"), list):
        container["candidates"] = []
    candidates: list[dict[str, Any]] = container["candidates"]
    candidate_by_game = {item.get("nbaGameId"): item for item in candidates if isinstance(item, dict)}
    events: list[dict[str, Any]] = []
    changed = False

    for comparison in comparisons:
        if comparison.get("matchStatus") != "matched" or not comparison.get("scoreValuesPresent"):
            # Missing/unmatched values are not interpreted as zero or as convergence.
            continue
        game_id = comparison["nbaGameId"]
        previous = state["games"].get(game_id, {})
        signature = _comparison_signature(comparison)
        signature_changed = signature != previous.get("signature")
        mismatch = bool(comparison.get("scoreMismatch"))
        was_active = bool(previous.get("activeDivergence"))
        candidate = candidate_by_game.get(game_id)
        is_new_candidate = candidate is None
        observation = _source_observation(comparison, observed_at)
        event_kind: str | None = None

        if mismatch:
            starting_episode = not was_active
            if candidate is None:
                candidate = {
                    "id": f"nba-feed-divergence-{game_id}",
                    "nbaGameId": game_id,
                    "gameDate": comparison.get("gameDate"),
                    "matchup": comparison.get("matchup"),
                    "awayTeam": comparison.get("awayTeam"),
                    "homeTeam": comparison.get("homeTeam"),
                    "firstDetectedAt": observed_at,
                    "latestObservationAt": observed_at,
                    "monitorStatus": "active_source_divergence",
                    "reviewStatus": "unverified",
                    "investigationStatus": "needs_review",
                    "reviewer": None,
                    "reviewedAt": None,
                    "resolution": None,
                    "resolutionSourceIds": [],
                    "monitorNote": "No source has been declared wrong; feed latency, provider error, or a league-record issue remain possible.",
                    "episodes": [],
                    "sourceUrls": {"nbaScoreboard": NBA_SCOREBOARD_URL, "espnScoreboard": ESPN_SCOREBOARD_URL},
                }
                candidates.append(candidate)
                candidate_by_game[game_id] = candidate
                starting_episode = True
                changed = True
            if starting_episode:
                episode: dict[str, Any] = {
                    "startedAt": observed_at,
                    "feedConvergedAt": None,
                    "observations": [observation],
                    "playByPlayContext": _fetch_pbp(game_id, fetch_json) if include_pbp else {
                        "url": NBA_PBP_URL.format(game_id=game_id),
                        "mode": "nearby_feed_context_not_causal",
                        "actions": [],
                        "note": "Play-by-play context not requested for this run.",
                        "retrievalError": None,
                    },
                }
                candidate.setdefault("episodes", []).append(episode)
                candidate["monitorStatus"] = "active_source_divergence"
                candidate["monitorNote"] = "A source divergence is currently observed; no source has been declared wrong. Any previous feed convergence did not settle the research question."
                candidate["latestObservationAt"] = observed_at
                candidate["awayTeam"] = comparison.get("awayTeam")
                candidate["homeTeam"] = comparison.get("homeTeam")
                if not is_new_candidate and candidate.get("investigationStatus") in {
                    "resolved_nba_correction", "resolved_secondary_source_only",
                    "resolved_feed_or_match_error", "closed_unresolved",
                }:
                    review_record = {
                        "archivedAt": observed_at,
                        "reviewStatus": candidate.get("reviewStatus"),
                        "investigationStatus": candidate.get("investigationStatus"),
                        "reviewer": candidate.get("reviewer"),
                        "reviewedAt": candidate.get("reviewedAt"),
                        "resolution": candidate.get("resolution"),
                        "resolutionSourceIds": candidate.get("resolutionSourceIds", []),
                    }
                    candidate.setdefault("reviewHistory", []).append(review_record)
                    candidate["reviewStatus"] = "unverified"
                    candidate["investigationStatus"] = "needs_review"
                    candidate["reviewer"] = None
                    candidate["reviewedAt"] = None
                    candidate["resolution"] = None
                    candidate["resolutionSourceIds"] = []
                event_kind = "candidate_detected"
                changed = True
            elif signature_changed:
                episode = candidate["episodes"][-1]
                episode["observations"].append(observation)
                if include_pbp:
                    episode["playByPlayContext"] = _fetch_pbp(game_id, fetch_json)
                candidate["latestObservationAt"] = observed_at
                candidate["monitorStatus"] = "active_source_divergence"
                event_kind = "candidate_observation_changed"
                changed = True
        else:
            if was_active and candidate is not None:
                episode = candidate["episodes"][-1]
                episode["feedConvergedAt"] = observed_at
                episode["observations"].append(observation)
                candidate["monitorStatus"] = "feed_converged"
                candidate["latestObservationAt"] = observed_at
                candidate["monitorNote"] = "The two feeds later agreed. This is an operational convergence only; the original divergence's correctness and cause remain unverified."
                event_kind = "feeds_converged_unverified"
                changed = True
            elif signature_changed:
                event_kind = "source_score_snapshot_changed"

        if signature_changed or event_kind:
            state["games"][game_id] = {
                "signature": signature,
                "activeDivergence": mismatch,
                "lastEventAt": observed_at if event_kind else previous.get("lastEventAt"),
            }
            if event_kind:
                state["lastEventAt"] = observed_at
                event = dict(observation)
                event["kind"] = event_kind
                event["scoreMismatch"] = mismatch
                events.append(event)
                changed = True
        # If a poll repeats the same state, no timestamps are rewritten. This keeps
        # the durable branch quiet while the live monitor still emits a fresh snapshot.

    candidates.sort(key=lambda item: str(item.get("firstDetectedAt", "")), reverse=True)
    if changed:
        _write_json(state_path, state)
        _write_json(candidates_path, {"schemaVersion": 1, "candidates": candidates})
        _append_jsonl(monitor_dir / "observations.jsonl", events)
    return candidates, changed


def _safe_error(exc: Exception) -> str:
    text = str(exc).replace("\n", " ").strip()
    return text[:300] or exc.__class__.__name__


def _source_state(ok: bool, url: str, **extras: Any) -> dict[str, Any]:
    return {"ok": ok, "url": url, **extras}


def run_monitor(
    root: Path,
    now: datetime | None = None,
    fetch_json: JsonFetcher | None = None,
    include_pbp: bool = True,
) -> dict[str, Any]:
    now = now or utc_now()
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    now = now.astimezone(timezone.utc)
    observed_at = as_utc_string(now)
    fetch_json = fetch_json or http_get_json

    nba_games: list[dict[str, Any]] = []
    espn_games: list[dict[str, Any]] = []
    nba_status: dict[str, Any]
    espn_status: dict[str, Any]
    try:
        payload = fetch_json(NBA_SCOREBOARD_URL)
        nba_games = parse_nba_scoreboard(payload)
        nba_status = _source_state(True, NBA_SCOREBOARD_URL, eventCount=len(nba_games))
    except Exception as exc:
        nba_status = _source_state(False, NBA_SCOREBOARD_URL, error=_safe_error(exc))
    try:
        espn_games, espn_status = fetch_espn_games(now, fetch_json)
    except Exception as exc:
        espn_status = _source_state(False, ESPN_SCOREBOARD_URL, error=_safe_error(exc), eventCount=0)

    comparisons = compare_scoreboards(nba_games, espn_games)
    both_ok = nba_status["ok"] and espn_status["ok"]
    has_warnings = bool(nba_status.get("warnings") or espn_status.get("warnings"))
    status = "ok" if both_ok and not has_warnings else ("partial" if nba_status["ok"] or espn_status["ok"] else "error")
    candidates: list[dict[str, Any]] = []
    persisted_change = False
    if both_ok:
        candidates, persisted_change = update_durable_observations(
            root=root,
            comparisons=comparisons,
            observed_at=observed_at,
            fetch_json=fetch_json,
            include_pbp=include_pbp,
        )

    active = [row for row in comparisons if row.get("scoreMismatch")]
    notes = [
        "A score mismatch is an unverified disagreement between source observations; no source is presumed correct.",
        "Nearby NBA play-by-play rows, if present, are context only and are not assigned as the cause.",
        "No match, missing score, or source outage is not interpreted as a zero or as resolution.",
    ]
    if not both_ok:
        notes.append("Durable candidates were not advanced because both current score sources were not successfully available.")
    if nba_status.get("warnings") or espn_status.get("warnings"):
        notes.append("One or more source/date queries returned warnings; inspect sourceStatus before treating the comparison as complete.")

    result = {
        "schemaVersion": 1,
        "status": status,
        "generatedAt": observed_at,
        "lastSuccessfulAt": observed_at if both_ok else None,
        "pollIntervalMinutes": POLL_INTERVAL_MINUTES,
        "sourceStatus": {"nba_official": nba_status, "espn_secondary": espn_status},
        "games": comparisons,
        "activeDiscrepancies": active,
        "durableStateChanged": persisted_change,
        "notes": notes,
    }
    _write_json(root / "data" / "monitor" / "current.json", result)
    return result


def http_get_json(url: str) -> dict[str, Any]:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    with urllib.request.urlopen(request, timeout=20) as response:
        raw = response.read(8_000_000)
    payload = json.loads(raw.decode("utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("source returned a non-object JSON payload")
    return payload


def parse_cli_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    parsed = parse_datetime(value)
    if parsed is None:
        raise argparse.ArgumentTypeError("--now must be an ISO date/time, for example 2026-10-07T12:00:00Z")
    return parsed


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1], help="repository root")
    parser.add_argument("--now", help="override the poll timestamp (ISO 8601; primarily for reproducible tests)")
    parser.add_argument("--no-pbp", action="store_true", help="skip optional play-by-play context retrieval")
    args = parser.parse_args()
    try:
        result = run_monitor(args.root.resolve(), now=parse_cli_datetime(args.now), include_pbp=not args.no_pbp)
    except Exception as exc:
        print(f"monitor failed: {_safe_error(exc)}", file=sys.stderr)
        return 1
    print(f"monitor status={result['status']} games={len(result['games'])} active_divergences={len(result['activeDiscrepancies'])} durable_change={result['durableStateChanged']}")
    for key, source in result["sourceStatus"].items():
        label = "ok" if source.get("ok") else "unavailable"
        suffix = f" ({source.get('error')})" if source.get("error") else ""
        print(f"{key}: {label}{suffix}")
    # Source outages are captured in current.json and should not turn an ordinary
    # scheduled poll into a failed deployment. Unexpected script errors still fail.
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
