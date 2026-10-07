"""I/O orchestration for scheduled and local fixture-driven monitor runs."""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any

from .engine import active_investigations, update_state
from .feeds import (
    ESPN_SCOREBOARD_URL,
    NBA_PLAY_BY_PLAY_URL,
    NBA_SCOREBOARD_URL,
    FeedError,
    build_observations,
    extract_latest_scoring_play,
    fetch_json,
    parse_espn_scoreboard,
    parse_nba_scoreboard,
    utc_now,
)
from .validation import DataValidationError, load_state, write_json


def _read_optional_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return deepcopy(default)
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        raise DataValidationError(f"Cannot safely update malformed feed snapshot {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise DataValidationError(f"Cannot safely update non-object feed snapshot {path}")
    return value


def _source_status(url: str, status: str, **extra: Any) -> dict[str, Any]:
    result = {"status": status, "url": url}
    result.update(extra)
    return result


def _published_game(observation: dict[str, Any], prior_game: dict[str, Any] | None, now: str) -> dict[str, Any]:
    game = {
        "game_id": observation.get("game_id"),
        "game_date": observation.get("game_date"),
        "status": observation.get("status"),
        "status_text": observation.get("status_text"),
        "period": observation.get("period"),
        "clock": observation.get("clock"),
        "away_team": deepcopy(observation.get("away_team")),
        "home_team": deepcopy(observation.get("home_team")),
        "scores": deepcopy(observation.get("scores")),
        "score_mismatch": observation.get("score_mismatch"),
        "latest_official_scoring_play": deepcopy(observation.get("latest_official_scoring_play")),
        "play_by_play_source_url": observation.get("play_by_play_source_url"),
    }
    material = (
        game.get("status"),
        game.get("period"),
        (game.get("scores", {}).get("nba") or {}).get("away"),
        (game.get("scores", {}).get("nba") or {}).get("home"),
        (game.get("scores", {}).get("espn") or {}).get("away"),
        (game.get("scores", {}).get("espn") or {}).get("home"),
        game.get("score_mismatch"),
    )
    prior_material = None
    if prior_game:
        prior_material = (
            prior_game.get("status"),
            prior_game.get("period"),
            (prior_game.get("scores", {}).get("nba") or {}).get("away"),
            (prior_game.get("scores", {}).get("nba") or {}).get("home"),
            (prior_game.get("scores", {}).get("espn") or {}).get("away"),
            (prior_game.get("scores", {}).get("espn") or {}).get("home"),
            prior_game.get("score_mismatch"),
        )
    if prior_game and material == prior_material:
        # The snapshot's timestamp applies to every displayed field. Do not
        # silently replace only the clock while keeping an older timestamp.
        game["observed_at"] = prior_game.get("observed_at")
        game["clock"] = prior_game.get("clock")
        game["status_text"] = prior_game.get("status_text")
        game["latest_official_scoring_play"] = deepcopy(
            prior_game.get("latest_official_scoring_play")
        )
        game["play_by_play_source_url"] = prior_game.get("play_by_play_source_url")
    else:
        game["observed_at"] = now
    return game


def _feed_material_signature(feed: dict[str, Any]) -> str:
    rows = []
    for game in feed.get("games", []):
        scores = game.get("scores") or {}
        nba_score = scores.get("nba") or {}
        espn_score = scores.get("espn") or {}
        rows.append(
            {
                "game_id": game.get("game_id"),
                "status": game.get("status"),
                "period": game.get("period"),
                "nba": [nba_score.get("away"), nba_score.get("home")],
                "espn": [espn_score.get("away"), espn_score.get("home")],
                "mismatch": game.get("score_mismatch"),
            }
        )
    return json.dumps(
        {
            "status": feed.get("status"),
            "health": feed.get("source_health"),
            "games": rows,
            "last_state_change_at": feed.get("last_state_change_at"),
        },
        sort_keys=True,
        separators=(",", ":"),
    )


def _build_feed(
    previous_feed: dict[str, Any],
    observations: list[dict[str, Any]],
    source_health: dict[str, Any],
    state: dict[str, Any],
    now: str,
    nba_ok: bool,
) -> dict[str, Any]:
    prior_games = {
        str(game.get("game_id")): game
        for game in previous_feed.get("games", [])
        if game.get("game_id") is not None
    }
    if nba_ok:
        games = [
            _published_game(observation, prior_games.get(str(observation.get("game_id"))), now)
            for observation in observations
        ]
        # Keep in-progress mismatch samples visibly fresh even if the point
        # totals have not changed since the last poll.
        open_mismatch_ids = {
            item.get("game_id")
            for item in active_investigations(state)
            if item.get("detection_type") == "cross_source_score_mismatch"
        }
        observation_by_id = {str(item.get("game_id")): item for item in observations}
        for game in games:
            if game.get("game_id") in open_mismatch_ids:
                current = observation_by_id.get(str(game.get("game_id")), {})
                game["observed_at"] = now
                game["clock"] = current.get("clock")
                game["status_text"] = current.get("status_text")
                game["latest_official_scoring_play"] = deepcopy(
                    current.get("latest_official_scoring_play")
                )
                game["play_by_play_source_url"] = current.get("play_by_play_source_url")
    else:
        games = deepcopy(previous_feed.get("games", []))
        for game in games:
            game["stale"] = True

    both_ok = all((source_health.get(name) or {}).get("status") == "ok" for name in ("nba", "espn"))
    any_ok = any((source_health.get(name) or {}).get("status") == "ok" for name in ("nba", "espn"))
    source_was_checked = any(
        (source_health.get(name) or {}).get("status") != "not_checked"
        for name in ("nba", "espn")
    )
    if not any_ok and not source_was_checked:
        status = "not_started"
    elif both_ok:
        status = "healthy"
    else:
        status = "degraded"

    feed = {
        "schema_version": 1,
        "status": status,
        "source_health": deepcopy(source_health),
        "games": games,
        "active_investigation_count": len(active_investigations(state)),
        "last_state_change_at": state.get("last_state_change_at"),
        "last_updated_at": previous_feed.get("last_updated_at"),
        "last_material_signature": previous_feed.get("last_material_signature"),
        "note": (
            "NBA and ESPN feed values are observations, not a determination of which source is correct. "
            "A score difference is an unverified candidate until independent evidence is reviewed."
        ),
    }
    if not nba_ok:
        feed["note"] += " The current NBA poll failed; any displayed games are the last saved snapshot and may be stale. An empty list in this state is not evidence of no games or no discrepancies."
    if both_ok and not games:
        feed["note"] += " Both sources returned successfully with no NBA games in the matched snapshot; this is not evidence of no discrepancy outside the returned feeds."

    new_signature = _feed_material_signature(feed)
    if new_signature != previous_feed.get("last_material_signature"):
        feed["last_updated_at"] = now
        feed["last_material_signature"] = new_signature
    return feed


def run_with_payloads(
    nba_payload: dict[str, Any] | None,
    espn_payload: dict[str, Any] | None,
    root: str | Path = ".",
    observed_at: str | None = None,
    nba_hash: str | None = None,
    espn_hash: str | None = None,
    pbp_payloads: dict[str, dict[str, Any]] | None = None,
    source_errors: dict[str, str] | None = None,
    response_metadata: dict[str, dict[str, str | None]] | None = None,
    pbp_metadata: dict[str, dict[str, str | None]] | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Run a deterministic cycle from supplied JSON payloads (also used by tests)."""
    root_path = Path(root)
    observed_at = observed_at or utc_now()
    source_errors = source_errors or {}
    response_metadata = response_metadata or {}
    pbp_metadata = pbp_metadata or {}
    nba_games: list[dict[str, Any]] = []
    espn_games: list[dict[str, Any]] = []
    source_health: dict[str, Any] = {}

    if nba_payload is not None:
        try:
            nba_games = parse_nba_scoreboard(nba_payload)
            source_health["nba"] = _source_status(NBA_SCOREBOARD_URL, "ok")
        except FeedError as exc:
            source_health["nba"] = _source_status(
                NBA_SCOREBOARD_URL,
                "invalid",
                error=str(exc),
            )
    else:
        source_health["nba"] = _source_status(
            NBA_SCOREBOARD_URL,
            "unavailable",
            error=source_errors.get("nba", "NBA source was not supplied"),
        )

    if espn_payload is not None:
        try:
            espn_games = parse_espn_scoreboard(espn_payload)
            source_health["espn"] = _source_status(ESPN_SCOREBOARD_URL, "ok")
        except FeedError as exc:
            source_health["espn"] = _source_status(
                ESPN_SCOREBOARD_URL,
                "invalid",
                error=str(exc),
            )
    else:
        source_health["espn"] = _source_status(
            ESPN_SCOREBOARD_URL,
            "unavailable",
            error=source_errors.get("espn", "ESPN source was not supplied"),
        )

    hashes = {"nba": nba_hash, "espn": espn_hash}
    observations = build_observations(nba_games, espn_games, observed_at, hashes)
    for observation in observations:
        game_id = observation.get("game_id")
        metadata = {
            source: deepcopy(response_metadata[source])
            for source in ("nba", "espn")
            if source in response_metadata
        }
        if game_id and str(game_id) in pbp_metadata:
            metadata["nba_pbp"] = deepcopy(pbp_metadata[str(game_id)])
            pbp_hash = pbp_metadata[str(game_id)].get("sha256")
            if pbp_hash:
                observation["source_hashes"]["nba_pbp"] = pbp_hash
        if metadata:
            observation["source_metadata"] = metadata
        if not game_id or observation.get("score_mismatch") is not True:
            continue
        pbp = (pbp_payloads or {}).get(str(game_id))
        play_url = NBA_PLAY_BY_PLAY_URL.format(game_id=game_id)
        observation["play_by_play_source_url"] = play_url
        if pbp is not None:
            play = extract_latest_scoring_play(pbp)
            if play:
                play["source_url"] = play_url
                observation["latest_official_scoring_play"] = play

    state_path = root_path / "data" / "monitor-state.json"
    feed_path = root_path / "data" / "live-feed.json"
    previous_state = load_state(state_path)
    previous_feed = _read_optional_json(feed_path, {"games": [], "source_health": {}})
    state = update_state(previous_state, observations, observed_at, source_health)
    feed = _build_feed(
        previous_feed,
        observations,
        source_health,
        state,
        observed_at,
        nba_ok=source_health.get("nba", {}).get("status") == "ok",
    )
    write_json(state_path, state)
    write_json(feed_path, feed)
    return state, feed


def run_live(root: str | Path = ".") -> tuple[dict[str, Any], dict[str, Any]]:
    """Poll the two configured public scoreboards and PBP for mismatched games."""
    observed_at = utc_now()
    payloads: dict[str, dict[str, Any] | None] = {"nba": None, "espn": None}
    hashes: dict[str, str | None] = {"nba": None, "espn": None}
    response_metadata: dict[str, dict[str, str | None]] = {}
    errors: dict[str, str] = {}
    for key, url in (("nba", NBA_SCOREBOARD_URL), ("espn", ESPN_SCOREBOARD_URL)):
        try:
            payload, metadata = fetch_json(url)
            payloads[key] = payload
            hashes[key] = metadata.get("sha256")
            response_metadata[key] = metadata
        except FeedError as exc:
            errors[key] = str(exc)

    # Obtain official play context only after a score divergence is found. The
    # action is descriptive context, not automatically labelled as its cause.
    pbp_payloads: dict[str, dict[str, Any]] = {}
    pbp_metadata: dict[str, dict[str, str | None]] = {}
    if payloads["nba"] is not None and payloads["espn"] is not None:
        try:
            nba_games = parse_nba_scoreboard(payloads["nba"])
            espn_games = parse_espn_scoreboard(payloads["espn"])
            mismatches = [
                item
                for item in build_observations(nba_games, espn_games, observed_at)
                if item.get("score_mismatch") is True and item.get("game_id")
            ]
        except FeedError:
            mismatches = []
        for item in mismatches:
            game_id = str(item["game_id"])
            try:
                pbp_payloads[game_id], pbp_metadata[game_id] = fetch_json(
                    NBA_PLAY_BY_PLAY_URL.format(game_id=game_id)
                )
            except FeedError:
                # Missing PBP is a source-availability limitation, not proof of
                # a missing scoring action. The investigation remains open.
                continue

    return run_with_payloads(
        payloads["nba"],
        payloads["espn"],
        root=root,
        observed_at=observed_at,
        nba_hash=hashes["nba"],
        espn_hash=hashes["espn"],
        pbp_payloads=pbp_payloads,
        source_errors=errors,
        response_metadata=response_metadata,
        pbp_metadata=pbp_metadata,
    )
