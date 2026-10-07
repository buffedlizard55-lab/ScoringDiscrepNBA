"""I/O orchestration for scheduled and local fixture-driven monitor runs."""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any

from datetime import datetime, timezone

from .alerts import update_book
from .consistency import espn_consistency_checks
from .engine import active_investigations, game_identity, update_state
from .feeds import (
    ESPN_SCOREBOARD_URL,
    ESPN_SUMMARY_URL,
    NBA_PLAY_BY_PLAY_URL,
    NBA_SCOREBOARD_URL,
    FeedError,
    build_observations,
    build_observations_from_sources,
    extract_latest_scoring_play,
    fetch_json,
    fetch_with_fallbacks,
    parse_espn_scoreboard,
    parse_nba_scoreboard,
    utc_now,
)
from .validation import DataValidationError, load_state, write_json

# Guard rails for the scheduled runner: a bounded number of per-game requests
# per poll, and a re-check interval so a settled box score is not refetched
# every five minutes.
MAX_SUMMARY_FETCHES = 8
SUMMARY_RECHECK_HOURS = 6


def _parse_iso(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


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


def _persisted_monitor_state(state: dict[str, Any]) -> dict[str, Any]:
    """Strip per-poll timestamps/durations before writing the durable ledger.

    The live state retains outage duration so alert thresholds can be evaluated,
    but serializing it would change the repository file on every five-minute
    poll even when no investigation or coverage fact changed.
    """
    persisted = deepcopy(state)
    health_state = persisted.get("source_health_state") or {}
    for entry in health_state.values():
        if isinstance(entry, dict):
            entry.pop("last_ok_at", None)
            entry.pop("unavailable_minutes", None)
    return persisted


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
        "score_sources": list(observation.get("score_sources") or []),
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


def _publishable_diagnostics(
    diagnostics: dict[str, list[dict[str, Any]]] | None,
) -> dict[str, list[dict[str, Any]]]:
    """Copy source diagnostics without per-poll noise such as request duration.

    Durations change on every request, so publishing them would make the saved
    snapshot differ on every poll even when nothing reviewable changed.
    """
    published: dict[str, list[dict[str, Any]]] = {}
    for source, attempts in sorted((diagnostics or {}).items()):
        rows: list[dict[str, Any]] = []
        rows_source = attempts if isinstance(attempts, list) else [attempts]
        for attempt in rows_source:
            if not isinstance(attempt, dict):
                continue
            rows.append({key: deepcopy(value) for key, value in attempt.items() if key != "duration_ms"})
        published[source] = rows
    return published


def _refresh_bucket(now: str | None) -> str | None:
    """Coarse time bucket so an open mismatch stays visibly current without churn."""
    parsed = _parse_iso(now)
    if parsed is None:
        return None
    minute = (parsed.minute // 15) * 15
    return parsed.replace(minute=minute, second=0, microsecond=0).isoformat()


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
    has_open_mismatch = any(row["mismatch"] is True for row in rows)
    return json.dumps(
        {
            "status": feed.get("status"),
            "health": feed.get("source_health"),
            "games": rows,
            "last_state_change_at": feed.get("last_state_change_at"),
            "diagnostics": feed.get("source_diagnostics"),
            "detector_status": feed.get("detector_status"),
            # The note is the reader's explanation of what this snapshot does and
            # does not prove (which sources answered, what was not compared), so a
            # wording change is a material change and must be published rather than
            # frozen behind an unchanged game list.
            "note": feed.get("note"),
            # Only refreshes while a mismatch window is open, at 15-minute
            # granularity, so the site can show freshness without a commit per poll.
            "mismatch_refresh_bucket": _refresh_bucket(feed.get("observed_at_for_refresh")) if has_open_mismatch else None,
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
    sources_ok: list[str],
    source_diagnostics: dict[str, list[dict[str, Any]]] | None = None,
) -> dict[str, Any]:
    prior_games = {
        str(game.get("game_id")): game
        for game in previous_feed.get("games", [])
        if game.get("game_id") is not None
    }
    if sources_ok:
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

    checked = [
        key
        for key, entry in sorted(source_health.items())
        if isinstance(entry, dict) and entry.get("status") != "not_checked"
    ]
    all_ok = bool(checked) and all(
        (source_health.get(key) or {}).get("status") == "ok" for key in checked
    )
    if not checked:
        status = "not_started"
    elif all_ok:
        status = "healthy"
    else:
        status = "degraded"

    feed = {
        "schema_version": 1,
        "status": status,
        "source_health": deepcopy(source_health),
        "source_diagnostics": _publishable_diagnostics(source_diagnostics),
        "detector_status": {
            "cross_source_comparison_available": len(sources_ok) >= 2,
            "sources_reachable": sorted(sources_ok),
            "final_game_checks_recorded": len(state.get("final_game_checks") or {}),
            "coverage_gaps_recorded": len(state.get("coverage_gaps") or []),
        },
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
    if not sources_ok:
        feed["note"] += " No configured source answered this poll; any displayed games are the last saved snapshot and may be stale. An empty list in this state is not evidence of no games or no discrepancies."
    if all_ok and not games:
        feed["note"] += " Every configured source returned successfully with no games in the matched snapshot; this is not evidence of no discrepancy outside the returned feeds."
    if not all_ok:
        missing = sorted(key for key in checked if (source_health.get(key) or {}).get("status") != "ok")
        feed["note"] += (
            f" Cross-source comparison could not run against: {', '.join(missing)}. "
            "Rows below show every source that did answer; the comparison column says 'Not compared' "
            "wherever fewer than two sources published the game. The single-provider final-score "
            "arithmetic check still ran where possible."
        )

    feed["observed_at_for_refresh"] = now
    new_signature = _feed_material_signature(feed)
    feed.pop("observed_at_for_refresh", None)
    if new_signature == previous_feed.get("last_material_signature"):
        # Nothing reviewable changed: keep the previously published snapshot
        # byte-for-byte so the scheduled runner does not rewrite (and commit)
        # identical output on every poll.
        return deepcopy(previous_feed)
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
    summary_payloads: dict[str, dict[str, Any]] | None = None,
    source_diagnostics: dict[str, list[dict[str, Any]]] | None = None,
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
    # Union the games each reachable source published: a source being down must
    # not blank out the games another source is still publishing, and the
    # single-provider arithmetic checks below need those rows to attach to.
    observations = build_observations_from_sources(
        {"nba": nba_games, "espn": espn_games}, observed_at, hashes
    )
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

    # Single-provider arithmetic checks (see monitor/consistency.py). These run
    # from the same provider's scoreboard value and box-score components, so
    # they still work when only one source is reachable.
    consistency_checks: list[dict[str, Any]] = []
    # An observation's game_id comes from the primary feed when the two feeds
    # are joined, so the ESPN game is matched by its own id first and then by
    # the team pair it belongs to.
    observations_by_pair = {
        (
            (item.get("away_team") or {}).get("abbreviation"),
            (item.get("home_team") or {}).get("abbreviation"),
        ): item
        for item in observations
    }
    espn_games_by_id = {str(game.get("game_id")): game for game in espn_games}
    for key, payload in sorted((summary_payloads or {}).items()):
        source_key, _, game_id = key.partition(":")
        if source_key != "espn" or not game_id:
            continue
        espn_game = espn_games_by_id.get(game_id)
        pair = (
            (espn_game.get("away_team") or {}).get("abbreviation"),
            (espn_game.get("home_team") or {}).get("abbreviation"),
        ) if espn_game else (None, None)
        observation = next(
            (item for item in observations if str(item.get("game_id")) == game_id), None
        ) or observations_by_pair.get(pair)
        if observation is None:
            continue
        provider_scores = {
            "away": (observation.get("scores", {}).get("espn") or {}).get("away"),
            "home": (observation.get("scores", {}).get("espn") or {}).get("home"),
        }
        check = espn_consistency_checks(
            payload,
            provider_scores,
            source_url=ESPN_SUMMARY_URL.format(game_id=game_id),
            game_id=game_id,
        )
        check["game_key"] = game_identity(observation)
        consistency_checks.append(check)

    state_path = root_path / "data" / "monitor-state.json"
    feed_path = root_path / "data" / "live-feed.json"
    alerts_path = root_path / "data" / "alerts.json"
    previous_state = load_state(state_path)
    previous_feed = _read_optional_json(feed_path, {"games": [], "source_health": {}})
    state = update_state(
        previous_state, observations, observed_at, source_health, consistency_checks
    )
    feed = _build_feed(
        previous_feed,
        observations,
        source_health,
        state,
        observed_at,
        sources_ok=[
            key
            for key, entry in sorted(source_health.items())
            if isinstance(entry, dict) and entry.get("status") == "ok"
        ],
        source_diagnostics=source_diagnostics or {},
    )
    write_json(state_path, _persisted_monitor_state(state))
    write_json(feed_path, feed)

    # Alert ledger. It is only rewritten when the alert set materially changes
    # so the scheduled runner does not commit a new revision every five minutes.
    previous_book = _read_optional_json(alerts_path, None)
    book, material_changed = update_book(previous_book, state, feed, observed_at)
    if material_changed or previous_book is None:
        write_json(alerts_path, book)
    return state, feed


def _due_for_summary_check(
    state: dict[str, Any], source_key: str, game_key: str, score: dict[str, Any], now: str
) -> bool:
    record = ((state.get("final_game_checks") or {}).get(f"{source_key}:{game_key}")) or {}
    if not record:
        return True
    if record.get("provider_reported") != {"away": score.get("away"), "home": score.get("home")}:
        return True
    checked_at = _parse_iso(record.get("checked_at"))
    now_dt = _parse_iso(now)
    if checked_at is None or now_dt is None:
        return True
    age_hours = (now_dt - checked_at).total_seconds() / 3600
    return age_hours >= SUMMARY_RECHECK_HOURS


def run_live(root: str | Path = ".") -> tuple[dict[str, Any], dict[str, Any]]:
    """Poll the configured public scoreboards, PBP for mismatches, and finals' box scores."""
    root_path = Path(root)
    observed_at = utc_now()
    payloads: dict[str, dict[str, Any] | None] = {"nba": None, "espn": None}
    hashes: dict[str, str | None] = {"nba": None, "espn": None}
    response_metadata: dict[str, dict[str, str | None]] = {}
    errors: dict[str, str] = {}
    diagnostics: dict[str, list[dict[str, Any]]] = {}
    for key, url in (("nba", NBA_SCOREBOARD_URL), ("espn", ESPN_SCOREBOARD_URL)):
        if key == "nba":
            # The NBA CDN has refused requests from this project's scheduled
            # runner, so a second header profile is attempted and every attempt
            # is published under source_diagnostics for review.
            payload, metadata, attempts = fetch_with_fallbacks(url)
            diagnostics[key] = attempts
            if payload is not None:
                payloads[key] = payload
                hashes[key] = metadata.get("sha256")
                response_metadata[key] = metadata
            else:
                errors[key] = attempts[-1].get("error", "NBA source unavailable") if attempts else "NBA source unavailable"
            continue
        try:
            payload, metadata = fetch_json(url)
            payloads[key] = payload
            hashes[key] = metadata.get("sha256")
            response_metadata[key] = metadata
            diagnostics[key] = [
                {
                    "profile": metadata.get("profile", "monitor"),
                    "outcome": "ok",
                    "http_status": 200,
                    "sha256": metadata.get("sha256"),
                    "etag": metadata.get("etag"),
                    "last_modified": metadata.get("last_modified"),
                }
            ]
        except FeedError as exc:
            errors[key] = str(exc)
            diagnostics[key] = [{"profile": "monitor", "outcome": "failed", "error": str(exc)}]

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
                for item in build_observations_from_sources(
                    {"nba": nba_games, "espn": espn_games}, observed_at
                )
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

    # Single-provider arithmetic checks for finished games. Only games whose
    # ESPN final has not already been checked (or has changed, or is older than
    # the re-check interval) are fetched, and the number of requests per poll is
    # capped so the scheduled runner stays a light client.
    summary_payloads: dict[str, dict[str, Any]] = {}
    if payloads["espn"] is not None:
        previous_state = load_state(root_path / "data" / "monitor-state.json")
        try:
            espn_games = parse_espn_scoreboard(payloads["espn"])
        except FeedError:
            espn_games = []
        due: list[dict[str, Any]] = []
        for game in espn_games:
            if game.get("status") != "final" or not game.get("game_id"):
                continue
            score = {
                "away": (game.get("away_team") or {}).get("score"),
                "home": (game.get("home_team") or {}).get("score"),
            }
            if score["away"] is None or score["home"] is None:
                continue
            if _due_for_summary_check(previous_state, "espn", str(game["game_id"]), score, observed_at):
                due.append(game)
        for game in due[:MAX_SUMMARY_FETCHES]:
            game_id = str(game["game_id"])
            try:
                summary_payloads[f"espn:{game_id}"], _, attempts = fetch_with_fallbacks(
                    ESPN_SUMMARY_URL.format(game_id=game_id)
                )
                diagnostics.setdefault("espn_summary", []).append(
                    {"game_id": game_id, "attempts": attempts}
                )
            except FeedError:
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
        summary_payloads=summary_payloads,
        source_diagnostics=diagnostics,
    )
