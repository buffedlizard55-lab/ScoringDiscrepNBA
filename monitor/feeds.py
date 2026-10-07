"""Small, dependency-free adapters for the live score sources.

The NBA CDN response is treated as the primary *feed being observed*, not as
infallible truth. ESPN is a secondary comparison feed. A disagreement alone is
never upgraded to a confirmed historical error.
"""

from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

NBA_SCOREBOARD_URL = "https://cdn.nba.com/static/json/liveData/scoreboard/todaysScoreboard_00.json"
NBA_PLAY_BY_PLAY_URL = "https://cdn.nba.com/static/json/liveData/playbyplay/playbyplay_{game_id}.json"
ESPN_SCOREBOARD_URL = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard"

# ESPN and NBA use a few different display abbreviations. Canonical codes are
# NBA codes. Unknown abbreviations are retained (and can still be compared if
# both feeds use the same code).
TEAM_CODE_ALIASES = {
    "GS": "GSW",
    "GSW": "GSW",
    "NO": "NOP",
    "NOP": "NOP",
    "NY": "NYK",
    "NYK": "NYK",
    "SA": "SAS",
    "SAS": "SAS",
    "UTAH": "UTA",
    "UTA": "UTA",
    "WSH": "WAS",
    "WAS": "WAS",
}


class FeedError(RuntimeError):
    """Raised when an upstream response is unavailable or malformed."""


def utc_now() -> str:
    """Return a stable ISO-8601 UTC timestamp."""
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def fetch_json(url: str, timeout: int = 15) -> tuple[dict[str, Any], dict[str, str | None]]:
    """Fetch JSON with a clear user-agent and retain a response hash for provenance."""
    request = Request(
        url,
        headers={
            "Accept": "application/json",
            "Cache-Control": "no-cache",
            "User-Agent": "ScoringDiscrepNBA-monitor/0.1 (+https://github.com/buffedlizard55-lab/ScoringDiscrepNBA)",
        },
    )
    try:
        with urlopen(request, timeout=timeout) as response:
            body = response.read()
            status = getattr(response, "status", 200)
            if status < 200 or status >= 300:
                raise FeedError(f"Upstream returned HTTP {status}")
            payload = json.loads(body.decode("utf-8"))
            if not isinstance(payload, dict):
                raise FeedError("Upstream JSON root must be an object")
            metadata = {
                "sha256": hashlib.sha256(body).hexdigest(),
                "etag": response.headers.get("ETag"),
                "last_modified": response.headers.get("Last-Modified"),
            }
            return payload, metadata
    except (HTTPError, URLError, TimeoutError, OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise FeedError(f"Could not fetch or decode upstream JSON: {type(exc).__name__}") from exc


def _canonical_code(value: Any) -> str | None:
    if value is None:
        return None
    code = str(value).strip().upper()
    if not code:
        return None
    return TEAM_CODE_ALIASES.get(code, code)


def _int_or_none(value: Any) -> int | None:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, int):
        return value if value >= 0 else None
    text = str(value).strip()
    if not text or text in {"-", "--", "None", "null"}:
        return None
    try:
        parsed = int(text)
    except ValueError:
        return None
    return parsed if parsed >= 0 else None


def _status_from_nba(game: dict[str, Any]) -> str:
    raw_status = game.get("gameStatus")
    if raw_status is not None:
        try:
            value = int(raw_status)
        except (TypeError, ValueError):
            value = None
        if value == 1:
            return "scheduled"
        if value == 2:
            return "live"
        if value == 3:
            return "final"
    text = str(game.get("gameStatusText") or "").strip().lower()
    if "final" in text:
        return "final"
    if any(token in text for token in ("qtr", "quarter", "half", "ot", "live", "end")):
        return "live"
    if text or game.get("gameTimeUTC"):
        return "scheduled"
    return "unknown"


def _status_from_espn(event: dict[str, Any], competition: dict[str, Any]) -> str:
    status = event.get("status")
    if not isinstance(status, dict) or not status:
        status = competition.get("status")
    if not isinstance(status, dict):
        status = {}
    status_type = status.get("type")
    if not isinstance(status_type, dict):
        status_type = {}
    state = str(status_type.get("state") or "").lower()
    if state == "post" or status_type.get("completed") is True:
        return "final"
    if state == "in":
        return "live"
    if state == "pre":
        return "scheduled"
    return "unknown"


def parse_nba_scoreboard(payload: dict[str, Any]) -> list[dict[str, Any]]:
    """Normalize the NBA public live scoreboard; reject unknown top-level shapes."""
    scoreboard = payload.get("scoreboard")
    if not isinstance(scoreboard, dict) or not isinstance(scoreboard.get("games"), list):
        raise FeedError("NBA scoreboard payload is missing scoreboard.games")

    normalized: list[dict[str, Any]] = []
    for index, game in enumerate(scoreboard["games"]):
        if not isinstance(game, dict):
            raise FeedError(f"NBA scoreboard game at index {index} is not an object")
        home_raw = game.get("homeTeam")
        away_raw = game.get("awayTeam")
        if not isinstance(home_raw, dict) or not isinstance(away_raw, dict):
            raise FeedError(f"NBA scoreboard game at index {index} is missing a team object")
        home_code = _canonical_code(home_raw.get("teamTricode") or home_raw.get("teamAbbreviation"))
        away_code = _canonical_code(away_raw.get("teamTricode") or away_raw.get("teamAbbreviation"))
        if not home_code or not away_code:
            raise FeedError(f"NBA scoreboard game at index {index} is missing a team abbreviation")
        game_date = str(
            game.get("gameEt") or game.get("gameDateEst") or game.get("gameDate") or ""
        )
        if len(game_date) >= 10:
            game_date = game_date[:10]
        else:
            game_date = None
        normalized.append(
            {
                "game_id": str(game.get("gameId") or "").strip() or None,
                "game_date": game_date,
                "status": _status_from_nba(game),
                "status_text": str(game.get("gameStatusText") or ""),
                "period": _int_or_none(game.get("period")),
                "clock": str(game.get("gameClock") or "").strip() or None,
                "away_team": {
                    "name": str(away_raw.get("teamName") or away_raw.get("teamCity") or away_code),
                    "abbreviation": away_code,
                    "score": _int_or_none(away_raw.get("score")),
                },
                "home_team": {
                    "name": str(home_raw.get("teamName") or home_raw.get("teamCity") or home_code),
                    "abbreviation": home_code,
                    "score": _int_or_none(home_raw.get("score")),
                },
                "source_url": NBA_SCOREBOARD_URL,
            }
        )
    return normalized


def parse_espn_scoreboard(payload: dict[str, Any]) -> list[dict[str, Any]]:
    """Normalize ESPN's public scoreboard response for cross-source comparison."""
    events = payload.get("events")
    if not isinstance(events, list):
        raise FeedError("ESPN scoreboard payload is missing events")

    normalized: list[dict[str, Any]] = []
    for index, event in enumerate(events):
        if not isinstance(event, dict):
            raise FeedError(f"ESPN scoreboard event at index {index} is not an object")
        competitions = event.get("competitions")
        if not isinstance(competitions, list) or not competitions or not isinstance(competitions[0], dict):
            raise FeedError(f"ESPN scoreboard event at index {index} is missing a competition")
        competition = competitions[0]
        competitors = competition.get("competitors")
        if not isinstance(competitors, list):
            raise FeedError(f"ESPN scoreboard event at index {index} is missing competitors")
        by_side: dict[str, dict[str, Any]] = {}
        for competitor in competitors:
            if not isinstance(competitor, dict):
                raise FeedError(f"ESPN scoreboard event at index {index} has an invalid competitor")
            side = str(competitor.get("homeAway") or "").lower()
            if side in {"home", "away"}:
                if side in by_side:
                    raise FeedError(f"ESPN scoreboard event at index {index} has duplicate {side} teams")
                by_side[side] = competitor
        home_raw = by_side.get("home")
        away_raw = by_side.get("away")
        if not isinstance(home_raw, dict) or not isinstance(away_raw, dict):
            raise FeedError(f"ESPN scoreboard event at index {index} is missing home/away roles")
        home_team = home_raw.get("team")
        away_team = away_raw.get("team")
        if not isinstance(home_team, dict) or not isinstance(away_team, dict):
            raise FeedError(f"ESPN scoreboard event at index {index} is missing a team object")
        home_code = _canonical_code(home_team.get("abbreviation"))
        away_code = _canonical_code(away_team.get("abbreviation"))
        if not home_code or not away_code:
            raise FeedError(f"ESPN scoreboard event at index {index} is missing a team abbreviation")
        event_date = str(event.get("date") or "")
        event_status = event.get("status")
        if not isinstance(event_status, dict) or not event_status:
            event_status = competition.get("status")
        if not isinstance(event_status, dict):
            event_status = {}
        event_status_type = event_status.get("type")
        if not isinstance(event_status_type, dict):
            event_status_type = {}
        normalized.append(
            {
                "game_id": str(event.get("id") or "").strip() or None,
                "game_date": event_date[:10] if len(event_date) >= 10 else None,
                "status": _status_from_espn(event, competition),
                "status_text": str(event_status_type.get("shortDetail") or ""),
                "period": _int_or_none(event_status.get("period")),
                "clock": str(event_status.get("displayClock") or "").strip() or None,
                "away_team": {
                    "name": str(away_team.get("displayName") or away_team.get("name") or away_code),
                    "abbreviation": away_code,
                    "score": _int_or_none(away_raw.get("score")),
                },
                "home_team": {
                    "name": str(home_team.get("displayName") or home_team.get("name") or home_code),
                    "abbreviation": home_code,
                    "score": _int_or_none(home_raw.get("score")),
                },
                "source_url": ESPN_SCOREBOARD_URL,
            }
        )
    return normalized


def _team_pair(game: dict[str, Any]) -> tuple[str, str] | None:
    """Return ordered (home, away) codes so reversed matchups are never joined."""
    home = (game.get("home_team") or {}).get("abbreviation")
    away = (game.get("away_team") or {}).get("abbreviation")
    if not home or not away:
        return None
    home_code = _canonical_code(home)
    away_code = _canonical_code(away)
    if not home_code or not away_code:
        return None
    return home_code, away_code


def match_scoreboards(
    nba_games: list[dict[str, Any]], espn_games: list[dict[str, Any]]
) -> list[tuple[dict[str, Any], dict[str, Any] | None]]:
    """Join same-day feeds by home/away team pair; leave ambiguous matches unmatched."""
    espn_by_pair: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for game in espn_games:
        pair = _team_pair(game)
        if pair:
            espn_by_pair[pair].append(game)

    result: list[tuple[dict[str, Any], dict[str, Any] | None]] = []
    for nba_game in nba_games:
        pair = _team_pair(nba_game)
        candidates = espn_by_pair.get(pair, []) if pair else []
        if len(candidates) == 1:
            result.append((nba_game, candidates[0]))
            continue
        if len(candidates) > 1 and nba_game.get("game_date"):
            same_date = [g for g in candidates if g.get("game_date") == nba_game.get("game_date")]
            if len(same_date) == 1:
                result.append((nba_game, same_date[0]))
                continue
        result.append((nba_game, None))
    return result


def extract_latest_scoring_play(payload: dict[str, Any]) -> dict[str, Any] | None:
    """Extract one PBP scoring action without assigning it as the cause of a mismatch."""
    game = payload.get("game") if isinstance(payload.get("game"), dict) else payload
    actions = game.get("actions") if isinstance(game, dict) else None
    if not isinstance(actions, list):
        return None
    for action in reversed(actions):
        if not isinstance(action, dict):
            continue
        # Only use the feed's explicit scoring flag. A cumulative player/team
        # points field can be non-zero on a non-scoring action and is not enough
        # evidence to label an event a score.
        if action.get("isScoringPlay") is not True:
            continue
        return {
            "action_id": action.get("actionId"),
            "period": _int_or_none(action.get("period")),
            "clock": str(action.get("clock") or "").strip() or None,
            "team": str(action.get("teamTricode") or "").strip() or None,
            "player": str(action.get("playerName") or action.get("personName") or "").strip() or None,
            "description": str(action.get("description") or "").strip() or None,
            "score_home": _int_or_none(action.get("scoreHome")),
            "score_away": _int_or_none(action.get("scoreAway")),
            "source_url": None,
        }
    return None


def build_observations(
    nba_games: list[dict[str, Any]],
    espn_games: list[dict[str, Any]],
    observed_at: str,
    source_hashes: dict[str, str | None] | None = None,
) -> list[dict[str, Any]]:
    """Create comparable snapshots, retaining missing values instead of guessing."""
    hashes = source_hashes or {}
    observations: list[dict[str, Any]] = []
    for nba_game, espn_game in match_scoreboards(nba_games, espn_games):
        nba_home = (nba_game.get("home_team") or {}).get("score")
        nba_away = (nba_game.get("away_team") or {}).get("score")
        espn_home = (espn_game.get("home_team") or {}).get("score") if espn_game else None
        espn_away = (espn_game.get("away_team") or {}).get("score") if espn_game else None
        both_sources_have_scores = all(value is not None for value in (nba_home, nba_away, espn_home, espn_away))
        mismatch = None if not both_sources_have_scores else (nba_home != espn_home or nba_away != espn_away)
        period = nba_game.get("period")
        clock = nba_game.get("clock")
        observations.append(
            {
                "observed_at": observed_at,
                "game_id": nba_game.get("game_id"),
                "game_date": nba_game.get("game_date"),
                "status": nba_game.get("status", "unknown"),
                "status_text": nba_game.get("status_text"),
                "period": period,
                "clock": clock,
                "away_team": nba_game.get("away_team"),
                "home_team": nba_game.get("home_team"),
                "scores": {
                    "nba": {"away": nba_away, "home": nba_home, "source_url": nba_game.get("source_url")},
                    "espn": {
                        "away": espn_away,
                        "home": espn_home,
                        "source_url": espn_game.get("source_url") if espn_game else None,
                    },
                },
                "score_mismatch": mismatch,
                "source_hashes": {
                    "nba": hashes.get("nba"),
                    "espn": hashes.get("espn"),
                },
                "latest_official_scoring_play": None,
                "play_by_play_source_url": None,
            }
        )
    return observations
