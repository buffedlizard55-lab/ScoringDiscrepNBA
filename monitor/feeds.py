"""Small, dependency-free adapters for the live score sources.

The NBA CDN response is treated as the primary *feed being observed*, not as
infallible truth. ESPN is a secondary comparison feed. A disagreement alone is
never upgraded to a confirmed historical error.
"""

from __future__ import annotations

import hashlib
import json
import time
from datetime import datetime, timezone
from typing import Any
from zoneinfo import ZoneInfo
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

NBA_SCOREBOARD_URL = "https://cdn.nba.com/static/json/liveData/scoreboard/todaysScoreboard_00.json"
NBA_PLAY_BY_PLAY_URL = "https://cdn.nba.com/static/json/liveData/playbyplay/playbyplay_{game_id}.json"
ESPN_SCOREBOARD_URL = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard"
ESPN_SUMMARY_URL = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/summary?event={game_id}"

# Request header profiles. The default profile identifies the project honestly.
# The browser profile exists only because some provider CDNs are known to reject
# non-browser user agents; every attempt is recorded in data/live-feed.json
# (source_diagnostics) so a blocked or degraded source is visible rather than
# silently assumed healthy.
HEADER_PROFILES: dict[str, dict[str, str]] = {
    "monitor": {
        "Accept": "application/json",
        "Cache-Control": "no-cache",
        "User-Agent": "ScoringDiscrepNBA-monitor/0.1 (+https://github.com/buffedlizard55-lab/ScoringDiscrepNBA)",
    },
    "browser": {
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "en-US,en;q=0.9",
        "Cache-Control": "no-cache",
        "Origin": "https://www.nba.com",
        "Referer": "https://www.nba.com/",
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
        ),
    },
}

DEFAULT_PROFILE_ORDER = ("monitor", "browser")

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


def _error_detail(exc: Exception) -> str:
    """Include the HTTP status code so a blocked source is diagnosable."""
    if isinstance(exc, HTTPError):
        reason = getattr(exc, "reason", None)
        return f"HTTP {exc.code}" + (f" {reason}" if reason else "")
    return type(exc).__name__


def fetch_json(
    url: str, timeout: int = 15, profile: str = "monitor"
) -> tuple[dict[str, Any], dict[str, str | None]]:
    """Fetch JSON with a named header profile and retain a response hash for provenance."""
    request = Request(url, headers=dict(HEADER_PROFILES.get(profile, HEADER_PROFILES["monitor"])))
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
                "profile": profile,
            }
            return payload, metadata
    except (HTTPError, URLError, TimeoutError, OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise FeedError(
            f"Could not fetch or decode upstream JSON: {type(exc).__name__} ({_error_detail(exc)})"
        ) from exc


def fetch_with_fallbacks(
    url: str,
    timeout: int = 15,
    profiles: tuple[str, ...] = DEFAULT_PROFILE_ORDER,
) -> tuple[dict[str, Any] | None, dict[str, str | None], list[dict[str, Any]]]:
    """Try each header profile in order, recording one diagnostic row per attempt.

    Returns ``(payload, metadata, attempts)``. ``payload`` is ``None`` only when
    every attempt failed, and ``attempts`` is always populated so the reason is
    reviewable from the published snapshot.
    """
    attempts: list[dict[str, Any]] = []
    for profile in profiles:
        started = time.monotonic()
        try:
            payload, metadata = fetch_json(url, timeout=timeout, profile=profile)
        except FeedError as exc:
            attempts.append(
                {
                    "profile": profile,
                    "outcome": "failed",
                    "error": str(exc),
                    "duration_ms": int((time.monotonic() - started) * 1000),
                }
            )
            continue
        attempts.append(
            {
                "profile": profile,
                "outcome": "ok",
                "http_status": 200,
                "sha256": metadata.get("sha256"),
                "etag": metadata.get("etag"),
                "last_modified": metadata.get("last_modified"),
                "duration_ms": int((time.monotonic() - started) * 1000),
            }
        )
        return payload, metadata, attempts
    return None, {}, attempts


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


def _eastern_game_date(value: Any) -> str | None:
    """Normalize a provider tipoff to NBA's Eastern calendar, not UTC date.

    A date-only value is already a calendar date. Naive datetimes and malformed
    values cannot establish a timezone and therefore do not establish a join.
    """
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if len(value) == 10:
            return parsed.date().isoformat()
        if parsed.tzinfo is None:
            return None
        return parsed.astimezone(ZoneInfo("America/New_York")).date().isoformat()
    except ValueError:
        return None


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
            game.get("gameEt") or game.get("gameDateEst") or game.get("gameDate")
            or scoreboard.get("gameDate") or ""
        )
        if len(game_date) >= 10:
            game_date = _eastern_game_date(game_date[:10])
        else:
            game_date = _eastern_game_date(game.get("gameTimeUTC"))
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
                "game_date": _eastern_game_date(event_date),
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
    def key(game):
        pair = _team_pair(game)
        date = game.get("game_date")
        return (pair, date) if pair and date else None

    result = []
    for nba_game in nba_games:
        identity = key(nba_game)
        candidates = [g for g in espn_games if key(g) == identity] if identity else []
        primary_count = sum(key(g) == identity for g in nba_games)
        match = candidates[0] if len(candidates) == 1 and primary_count == 1 else None
        result.append((nba_game, match))
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


SOURCE_LABELS = {"nba": "NBA", "espn": "ESPN", "yahoo": "Yahoo"}


def source_label(source_key: str) -> str:
    """Human-readable label for a configured source key."""
    return SOURCE_LABELS.get(source_key, source_key.upper())


def build_observations_from_sources(
    source_games: dict[str, list[dict[str, Any]]],
    observed_at: str,
    source_hashes: dict[str, str | None] | None = None,
) -> list[dict[str, Any]]:
    """Union every source's games into one row per game, retaining missing values.

    The first source that lists a game supplies the row identity, so a joined
    game keeps the primary feed's game id exactly as before. Each source's score
    is stored side by side under ``scores`` and ``score_mismatch`` stays ``None``
    until two sources publish both sides of the same game: a comparison that
    could not run is not agreement.

    Building the union (instead of driving everything from the primary feed)
    matters because the primary NBA CDN feed has been unavailable to the
    scheduled runner: without this, a reachable secondary source published
    nothing at all and its single-provider arithmetic checks never ran.
    """
    hashes = source_hashes or {}
    source_hash_view = {key: hashes.get(key) for key in source_games}
    observations: list[dict[str, Any]] = []
    # A date and unique ordered team pair per source are required. Never guess
    # which duplicate row represents a game or compare different game dates.
    counts = {}
    for source, games in source_games.items():
        for game in games or []:
            key = (source, _team_pair(game), game.get("game_date"))
            counts[key] = counts.get(key, 0) + 1
    for source_key, games in source_games.items():
        for game in games or []:
            pair = _team_pair(game)
            if pair is None:
                continue
            date = game.get("game_date")
            unique = bool(date) and counts[(source_key, pair, date)] == 1
            row = next(
                (
                    candidate
                    for candidate in observations
                    if unique and candidate["_joinable"]
                    and candidate["_team_pair"] == pair
                    and candidate["game_date"] == date
                    and source_key not in candidate["scores"]
                ),
                None,
            )
            if row is None:
                row = {
                    "_team_pair": pair,
                    "_joinable": unique,
                    "observed_at": observed_at,
                    "game_id": game.get("game_id"),
                    "game_date": game.get("game_date"),
                    "status": game.get("status", "unknown"),
                    "status_text": game.get("status_text"),
                    "period": game.get("period"),
                    "clock": game.get("clock"),
                    "away_team": game.get("away_team"),
                    "home_team": game.get("home_team"),
                    "scores": {},
                    "score_sources": [],
                    "score_mismatch": None,
                    "source_hashes": deepcopy_source_hashes(source_hash_view),
                    "latest_official_scoring_play": None,
                    "play_by_play_source_url": None,
                }
                observations.append(row)
            row["scores"][source_key] = {
                "away": (game.get("away_team") or {}).get("score"),
                "home": (game.get("home_team") or {}).get("score"),
                "source_url": game.get("source_url"),
                "game_id": game.get("game_id"),
                "game_date": date,
                "status": game.get("status"),
                "period": game.get("period"),
                "clock": game.get("clock"),
            }
    for row in observations:
        published = {
            key: value
            for key, value in row["scores"].items()
            if value.get("away") is not None and value.get("home") is not None
        }
        row["score_sources"] = sorted(published)
        if len(published) < 2:
            row["score_mismatch"] = None
        else:
            reference = next(iter(published.values()))
            row["score_mismatch"] = any(
                (value["away"], value["home"]) != (reference["away"], reference["home"])
                for value in published.values()
            )
        row.pop("_team_pair", None)
        row.pop("_joinable", None)
    return observations


def deepcopy_source_hashes(source_hash_view: dict[str, Any]) -> dict[str, Any]:
    """Copy a per-source hash mapping without importing deepcopy for one use."""
    return {key: value for key, value in source_hash_view.items()}


def build_observations(
    nba_games: list[dict[str, Any]],
    espn_games: list[dict[str, Any]],
    observed_at: str,
    source_hashes: dict[str, str | None] | None = None,
) -> list[dict[str, Any]]:
    """Backwards-compatible two-source wrapper around the union builder."""
    return build_observations_from_sources(
        {"nba": nba_games, "espn": espn_games}, observed_at, source_hashes
    )
