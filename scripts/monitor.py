#!/usr/bin/env python3
"""Continuous NBA score-discrepancy monitor (stdlib only).

Compares, per game:
  1. ESPN scoreboard API (secondary source) vs NBA CDN boxscore (authoritative-leaning)
     -> check: cross-source-total-mismatch
  2. Each source's quarter/period linescores summed vs its own totals
     -> check: quarter-sum-mismatch
  3. NBA play-by-play final running score vs NBA boxscore totals
     -> check: pbp-recompute-mismatch

Results are recorded in data/investigations.json with lifecycle:
  detected -> investigating -> correction-observed | explained-no-error -> resolved
Human review is REQUIRED before anything becomes a case in data/cases/.
Source outages are reported in the run summary (not recorded as scoring discrepancies).

Endpoints:
  ESPN:  https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard?dates=YYYYMMDD
  NBA liveData scoreboard: https://cdn.nba.com/static/json/liveData/scoreboard/{season}/GameScoreboard_{season}.json
  NBA liveData boxscore:   https://cdn.nba.com/static/json/liveData/boxscore/boxscore_{gameId}.json
  NBA liveData playbyplay: https://cdn.nba.com/static/json/liveData/playbyplay/playbyplay_{gameId}.json

Usage:
  python3 scripts/monitor.py --date 20250115 [--lookback 1]
  python3 scripts/monitor.py --self-test   # offline fixture test, no network
"""
import argparse
import datetime as dt
import json
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INV_PATH = ROOT / "data" / "investigations.json"
FIX_DIR = Path(__file__).resolve().parent / "fixtures"

ESPN_URL = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard?dates={datestr}"
NBA_SCOREBOARD_URL = "https://cdn.nba.com/static/json/liveData/scoreboard/{season}/GameScoreboard_{season}.json"
NBA_BOXSCORE_URL = "https://cdn.nba.com/static/json/liveData/boxscore/boxscore_{game_id}.json"
NBA_PBP_URL = "https://cdn.nba.com/static/json/liveData/playbyplay/playbyplay_{game_id}.json"

UA = {"User-Agent": "ScoringDiscrepNBA-monitor/1.0 (+https://github.com/buffedlizard55-lab/ScoringDiscrepNBA)"}
TRICODE_ALIASES = {"BROOKLYN": "BKN", "BRK": "BKN", "PHOENIX": "PHX", "PHO": "PHX",
                   "NEW ORLEANS": "NOP", "NO": "NOP", "SAN ANTONIO": "SAS", "SA": "SAS",
                   "GOLDEN STATE": "GSW", "GS": "GSW", "NEW YORK": "NYK", "NY": "NYK",
                   "OKLAHOMA CITY": "OKC", "UTAH": "UTA", "UTAH JAZZ": "UTA"}


def norm_team(code):
    code = (code or "").upper().strip()
    return TRICODE_ALIASES.get(code, code)


def fetch_json(url, timeout=25):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def season_year_for(datestr):
    """NBA season starts in ~October: season label year = year of tip-off autumn."""
    d = dt.datetime.strptime(datestr, "%Y%m%d").date()
    return d.year if d.month >= 9 else d.year - 1


# ---------------- source parsers ----------------

def safe_int(value):
    """Parse an integer observation without treating missing/invalid data as zero."""
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
        parsed = float(raw)
    except (TypeError, ValueError):
        return None
    if parsed < 0 or not parsed.is_integer():
        return None
    return int(parsed)


def _parse_periods(team, key="periods"):
    periods = team.get(key) or []
    if not isinstance(periods, list):
        return []
    return [safe_int(row.get("score")) for row in periods if isinstance(row, dict)]


def parse_espn(scoreboard):
    """Return normalized ESPN games keyed by 'AWY@HME'; unknown values remain None."""
    games = {}
    for ev in scoreboard.get("events", []):
        try:
            comp = ev["competitions"][0]
            teams = {t["homeAway"]: t for t in comp["competitors"]}
            a, h = teams["away"], teams["home"]
            a_code = norm_team(a["team"].get("abbreviation") or a["team"].get("shortDisplayName"))
            h_code = norm_team(h["team"].get("abbreviation") or h["team"].get("shortDisplayName"))
            if not a_code or not h_code:
                continue
            status = comp.get("status") or {}
            status_type = status.get("type") or {}
            a_lines = a.get("linescores") or []
            h_lines = h.get("linescores") or []
            games[f"{a_code}@{h_code}"] = {
                "away": a_code, "home": h_code,
                "away_score": safe_int(a.get("score")), "home_score": safe_int(h.get("score")),
                "status": status_type.get("name", "UNKNOWN"),
                "quarters": [safe_int(ls.get("value")) for ls in a_lines if isinstance(ls, dict)],
                "home_quarters": [safe_int(ls.get("value")) for ls in h_lines if isinstance(ls, dict)],
                "source": "espn",
            }
        except (KeyError, ValueError, TypeError, AttributeError):
            continue
    return games


def parse_nba_scoreboard(sb):
    """Return {gameId: meta} from NBA liveData scoreboard; omit unidentifiable rows."""
    games = {}
    board = sb.get("scoreboard", sb)
    if not isinstance(board, dict):
        return games
    for g in board.get("games", []):
        if not isinstance(g, dict):
            continue
        away = g.get("awayTeam") or {}
        home = g.get("homeTeam") or {}
        if not isinstance(away, dict) or not isinstance(home, dict):
            continue
        gid = str(g.get("gameId") or "").strip()
        a_code = norm_team(away.get("teamTricode"))
        h_code = norm_team(home.get("teamTricode"))
        if not gid or not a_code or not h_code:
            continue
        status_text = str(g.get("gameStatusText", ""))
        games[gid] = {
            "away": a_code, "home": h_code,
            "status": status_text,
            "is_final": bool(g.get("gameStatus") == 3 or "final" in status_text.lower()),
        }
    return games


def parse_nba_boxscore(bx):
    game = bx.get("game", bx)
    a = game.get("awayTeam", {}) or {}
    h = game.get("homeTeam", {}) or {}
    return {
        "away": norm_team(a.get("teamTricode")), "home": norm_team(h.get("teamTricode")),
        "away_score": safe_int(a.get("score")), "home_score": safe_int(h.get("score")),
        "quarters": _parse_periods(a), "home_quarters": _parse_periods(h), "source": "nba-cdn",
    }


def parse_nba_pbp_final(pbp):
    """Return final running (away, home) from the last scoring action carrying running totals."""
    game = pbp.get("game", pbp)
    actions = game.get("actions", [])
    for act in reversed(actions):
        sa, sh = act.get("scoreAway"), act.get("scoreHome")
        if sa not in (None, "") and sh not in (None, ""):
            try:
                return int(sa), int(sh)
            except (ValueError, TypeError):
                continue
    return None


# ---------------- checks ----------------

def _complete_score_pair(side):
    return all(isinstance(side.get(key), int) and not isinstance(side.get(key), bool)
               for key in ("away_score", "home_score"))


def check_cross_source(espn, nba, is_final):
    """Compare only when both sources supplied two parseable scores."""
    if not _complete_score_pair(espn) or not _complete_score_pair(nba):
        return None
    if espn["away_score"] != nba["away_score"] or espn["home_score"] != nba["home_score"]:
        return {
            "check": "cross-source-total-mismatch",
            "scope": "cross-source",
            "severity": "warn" if is_final else "info",
            "detail": (f"ESPN {espn['away']} {espn['away_score']} @ {espn['home']} {espn['home_score']} "
                       f"(total {espn['away_score'] + espn['home_score']}) vs NBA-CDN "
                       f"{nba['away_score']}-{nba['home_score']} (total {nba['away_score'] + nba['home_score']}). "
                       + ("FINAL — possible source conflict." if is_final else "Live game — may be feed lag; recheck at final.")),
            "observation": {
                "espn": {key: espn.get(key) for key in ("away", "home", "away_score", "home_score", "status")},
                "nba_cdn": {key: nba.get(key) for key in ("away", "home", "away_score", "home_score")},
            },
        }
    return None


def quarter_sum_observations(side, label):
    """Return completed away/home checks; incomplete feed data is not a passing check."""
    results = []
    for side_name, score_key, periods_key in (
        ("away", "away_score", "quarters"),
        ("home", "home_score", "home_quarters"),
    ):
        score = side.get(score_key)
        periods = side.get(periods_key) or []
        if (not isinstance(score, int) or isinstance(score, bool) or not periods
                or any(not isinstance(value, int) or isinstance(value, bool) for value in periods)):
            continue
        period_total = sum(periods)
        scope = f"{side.get('source', label.lower())}-{side_name}"
        evidence = {
            "source": side.get("source", label.lower()),
            "team": side.get(side_name),
            "score": score,
            "period_scores": periods,
            "period_sum": period_total,
        }
        finding = None
        if period_total != score:
            finding = {
                "check": "quarter-sum-mismatch",
                "scope": scope,
                "severity": "warn",
                "detail": f"{label} {side_name} quarters {periods} sum to {period_total} != total {score}",
                "observation": evidence,
            }
        results.append({"scope": scope, "evidence": evidence, "finding": finding})
    return results


def check_quarter_sum(side, label):
    """Compatibility helper for the offline self-test; returns the first mismatch."""
    return next((item["finding"] for item in quarter_sum_observations(side, label)
                 if item["finding"] is not None), None)


def check_pbp(nba_box, pbp_final):
    if pbp_final is None or not _complete_score_pair(nba_box):
        return None
    if pbp_final[0] != nba_box["away_score"] or pbp_final[1] != nba_box["home_score"]:
        return {"check": "pbp-recompute-mismatch",
                "scope": "nba-pbp-vs-boxscore",
                "severity": "warn",
                "detail": (f"NBA PBP final running score {pbp_final[0]}-{pbp_final[1]} != "
                           f"NBA boxscore {nba_box['away_score']}-{nba_box['home_score']}. Internal inconsistency in league data."),
                "observation": {
                    "nba_pbp_final": list(pbp_final),
                    "nba_boxscore": {key: nba_box.get(key) for key in ("away", "home", "away_score", "home_score")},
                }}
    return None


# ---------------- investigation store ----------------

def load_investigations():
    data = json.loads(INV_PATH.read_text())
    data.setdefault("records", [])
    return data


def save_investigations(data):
    INV_PATH.write_text(json.dumps(data, indent=2) + "\n")


def _observation(record, at=None):
    return {
        "at": at or record.get("last_seen_utc") or record.get("created_utc"),
        "severity": record.get("severity"),
        "evidence": record.get("evidence", {}),
    }


def upsert(data, new):
    """Update the current view without discarding the initial or changed observations."""
    for rec in data["records"]:
        if rec["id"] != new["id"]:
            continue
        if not rec.get("observations"):
            # Migrate earlier records: the old evidence value is the first known snapshot.
            rec["observations"] = [_observation(rec, rec.get("created_utc"))]
        rec.setdefault("history", [])
        previous_evidence = rec.get("evidence", {})
        previous_severity = rec.get("severity")
        changed = previous_evidence != new.get("evidence", {}) or previous_severity != new.get("severity")
        rec["last_seen_utc"] = new["last_seen_utc"]
        rec["repeat_count"] = int(rec.get("repeat_count", 1)) + 1
        rec["check_scope"] = new.get("check_scope", rec.get("check_scope"))
        if changed:
            rec["observations"].append(_observation(new))
            rec["last_changed_utc"] = new["last_seen_utc"]
            rec["history"].append({
                "at": new["last_seen_utc"],
                "note": "Source values or severity changed; a new observation was appended.",
            })
        if rec.get("status") in ("correction-observed", "explained-no-error", "resolved", "escalated-to-case"):
            previous_status = rec["status"]
            rec["status"] = "investigating"
            rec["history"].append({
                "at": new["last_seen_utc"],
                "note": f"Mismatch reappeared after status {previous_status}; reopened for human review.",
            })
        rec["severity"] = new["severity"]
        rec["evidence"] = new["evidence"]
        return "updated"

    new.setdefault("observations", [_observation(new)])
    new.setdefault("repeat_count", 1)
    new.setdefault("check_scope", new.get("scope", "unspecified"))
    data["records"].append(new)
    return "created"


def resolve_if_cleared(data, ok_observations, now):
    """Record source convergence only when that exact check/scope was fully performed.

    Agreement is an operational observation, not proof that an earlier record was wrong
    or that a correction occurred. The persisted resolution snapshot keeps the later
    values available for human review.
    """
    n = 0
    for rec in data["records"]:
        if rec["status"] not in ("detected", "investigating"):
            continue
        scope = rec.get("check_scope")
        if not scope:
            # Legacy records without a scope cannot be safely closed by a narrower check.
            continue
        key = (rec["game_date"], rec["game_key"], rec["check"], scope)
        evidence = ok_observations.get(key)
        if evidence is not None:
            rec["status"] = "correction-observed"
            rec.setdefault("resolution_observations", []).append({"at": now, "evidence": evidence})
            rec.setdefault("history", []).append({
                "at": now,
                "note": "The exact check/scope now agrees; possible correction or transient feed lag cleared. This is not a human-confirmed resolution.",
            })
            n += 1
    return n


# ---------------- main flow ----------------

def score_block(side):
    away_score, home_score = side.get("away_score"), side.get("home_score")
    complete = _complete_score_pair(side)
    return {
        "away": away_score,
        "home": home_score,
        "total": away_score + home_score if complete else None,
    }


def monitor_date(datestr, live_fetch=True, now=None):
    now = now or dt.datetime.now(dt.timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=dt.timezone.utc)
    now = now.astimezone(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    data = load_investigations()
    summary = {
        "date": datestr, "observed_at_utc": now, "games": 0, "game_rows": [],
        "mismatches": 0, "created": 0, "updated": 0, "feeds_ok": {}, "feed_warnings": [],
    }
    try:
        espn_url = ESPN_URL.format(datestr=datestr)
        espn_raw = fetch_json(espn_url) if live_fetch else json.loads((FIX_DIR / "espn_sample.json").read_text())
        summary["feeds_ok"]["espn"] = True
    except Exception as exc:  # noqa: BLE001
        summary["feeds_ok"]["espn"] = f"UNAVAILABLE: {exc}"
        summary["feeds_ok"]["nba-cdn"] = "NOT_CHECKED: ESPN scoreboard unavailable"
        summary["feed_warnings"].append("ESPN scoreboard could not be fetched; no cross-source comparison was made.")
        save_investigations(data)
        return summary
    espn_games = parse_espn(espn_raw)
    season = season_year_for(datestr)
    nba_scoreboard_url = NBA_SCOREBOARD_URL.format(season=season)
    try:
        if live_fetch:
            nba_sb = parse_nba_scoreboard(fetch_json(nba_scoreboard_url))
        else:
            nba_sb = json.loads((FIX_DIR / "nba_scoreboard_sample.json").read_text())
        summary["feeds_ok"]["nba-cdn"] = True
    except Exception as exc:  # noqa: BLE001
        summary["feeds_ok"]["nba-cdn"] = f"UNAVAILABLE: {exc}"
        summary["feed_warnings"].append("NBA CDN scoreboard could not be fetched; no cross-source comparison was made.")
        nba_sb = {}

    by_matchup = {}
    for gid, meta in nba_sb.items():
        if not gid or str(gid).startswith("_") or not isinstance(meta, dict):
            continue
        away, home = meta.get("away"), meta.get("home")
        if away and home:
            by_matchup[f"{away}@{home}"] = (gid, meta)

    ok_observations = {}
    for key, espn in espn_games.items():
        summary["games"] += 1
        is_final = "final" in str(espn.get("status", "")).lower()
        findings = []
        row = {
            "observed_at_utc": now,
            "game_date": datestr,
            "game_key": key,
            "away_team": espn["away"],
            "home_team": espn["home"],
            "status": espn.get("status"),
            "espn": {
                "url": ESPN_URL.format(datestr=datestr),
                "score": score_block(espn),
                "status": espn.get("status"),
            },
            "nba_cdn": {
                "scoreboard_url": nba_scoreboard_url,
                "boxscore_url": None,
                "game_status": None,
                "score": None,
            },
            "comparison": "nba-scoreboard-unavailable" if not summary["feeds_ok"].get("nba-cdn") else "no-nba-match",
            "score_mismatch": False,
        }
        if not _complete_score_pair(espn):
            summary["feed_warnings"].append(f"ESPN {key}: one or more score values are missing; no cross-source comparison was made.")
        for result in quarter_sum_observations(espn, "ESPN"):
            if result["finding"] is not None:
                findings.append(result["finding"])
            else:
                ok_observations[(datestr, key, "quarter-sum-mismatch", result["scope"])] = result["evidence"]

        nba_box = None
        pbp_final = None
        if key in by_matchup:
            gid, meta = by_matchup[key]
            final = is_final or meta.get("is_final", False)
            row["nba_cdn"]["boxscore_url"] = NBA_BOXSCORE_URL.format(game_id=gid)
            row["nba_cdn"]["game_status"] = meta.get("status")
            try:
                if live_fetch:
                    nba_box = parse_nba_boxscore(fetch_json(row["nba_cdn"]["boxscore_url"]))
                else:
                    nba_box = json.loads((FIX_DIR / "nba_boxscore_sample.json").read_text())
                row["nba_cdn"]["score"] = score_block(nba_box)
                row["comparison"] = "incomplete-score-data"
                if not _complete_score_pair(nba_box):
                    summary["feed_warnings"].append(f"NBA boxscore {gid}: one or more score values are missing; no cross-source comparison was made.")

                for result in quarter_sum_observations(nba_box, "NBA-CDN"):
                    if result["finding"] is not None:
                        findings.append(result["finding"])
                    else:
                        ok_observations[(datestr, key, "quarter-sum-mismatch", result["scope"])] = result["evidence"]

                cross = check_cross_source(espn, nba_box, final)
                if cross is not None:
                    row["comparison"] = "different"
                    row["score_mismatch"] = True
                    findings.append(cross)
                elif _complete_score_pair(espn) and _complete_score_pair(nba_box):
                    row["comparison"] = "equal"
                    ok_observations[(datestr, key, "cross-source-total-mismatch", "cross-source")] = {
                        "espn": {k: espn.get(k) for k in ("away", "home", "away_score", "home_score", "status")},
                        "nba_cdn": {k: nba_box.get(k) for k in ("away", "home", "away_score", "home_score")},
                    }

                if final:
                    try:
                        row["nba_cdn"]["play_by_play_url"] = NBA_PBP_URL.format(game_id=gid)
                        pbp = fetch_json(row["nba_cdn"]["play_by_play_url"]) if live_fetch else json.loads((FIX_DIR / "nba_pbp_sample.json").read_text())
                        pbp_final = parse_nba_pbp_final(pbp)
                        row["nba_cdn"]["play_by_play_final_score"] = list(pbp_final) if pbp_final is not None else None
                        pbp_check = check_pbp(nba_box, pbp_final)
                        if pbp_check is not None:
                            findings.append(pbp_check)
                        elif pbp_final is not None and _complete_score_pair(nba_box):
                            ok_observations[(datestr, key, "pbp-recompute-mismatch", "nba-pbp-vs-boxscore")] = {
                                "nba_pbp_final": list(pbp_final),
                                "nba_boxscore": {k: nba_box.get(k) for k in ("away", "home", "away_score", "home_score")},
                            }
                    except Exception as exc:  # noqa: BLE001
                        summary["feed_warnings"].append(f"NBA PBP fetch failed for {gid}: {exc}")
                        findings.append({"check": "feed-unavailable", "severity": "info",
                                         "detail": f"NBA PBP fetch failed for {gid}: {exc}"})
            except Exception as exc:  # noqa: BLE001
                row["comparison"] = "nba-boxscore-unavailable"
                summary["feed_warnings"].append(f"NBA boxscore fetch failed for {gid}: {exc}")
                findings.append({"check": "feed-unavailable", "severity": "info",
                                 "detail": f"NBA boxscore fetch failed for {gid}: {exc}"})
        row["findings"] = [
            {k: finding.get(k) for k in ("check", "scope", "severity", "detail")}
            for finding in findings if finding.get("check") != "feed-unavailable"
        ]
        summary["game_rows"].append(row)

        for finding in findings:
            if finding["check"] == "feed-unavailable":
                continue  # source outages are operational status, never a score discrepancy
            summary["mismatches"] += 1
            scope = finding.get("scope", "unspecified")
            evidence = {"check_observation": finding.get("observation"), "detail": finding["detail"]}
            if finding["check"] == "cross-source-total-mismatch":
                evidence["espn"] = {k: espn.get(k) for k in ("away", "home", "away_score", "home_score", "status")}
                evidence["nba_cdn"] = ({k: nba_box.get(k) for k in ("away", "home", "away_score", "home_score")} if nba_box else None)
            elif finding["check"] == "quarter-sum-mismatch":
                evidence["source_snapshot"] = finding.get("observation")
            elif finding["check"] == "pbp-recompute-mismatch":
                evidence["nba_cdn_and_pbp"] = finding.get("observation")
            rid = f"{datestr}-{key}-{finding['check']}-{scope}"
            rec = {
                "id": rid, "created_utc": now, "last_seen_utc": now, "game_date": datestr,
                "away_team": espn["away"], "home_team": espn["home"], "game_key": key,
                "check": finding["check"], "check_scope": scope,
                "severity": finding["severity"], "status": "detected", "evidence": evidence,
                "history": [{"at": now, "note": "Auto-detected by monitor.py. Source disagreement is unverified; human review required."}],
            }
            res = upsert(data, rec)
            summary[res] += 1

    data["records"].sort(key=lambda r: r.get("created_utc", ""), reverse=True)
    summary["auto_advanced_to_correction_observed"] = resolve_if_cleared(data, ok_observations, now)
    save_investigations(data)
    return summary


def write_current_snapshot(summary, requested_date=None, root=ROOT):
    """Publish the latest scheduled comparison and feed health for the static site."""
    path = root / "data" / "monitor" / "current.json"
    previous = {}
    if path.exists():
        try:
            previous = json.loads(path.read_text())
        except (OSError, json.JSONDecodeError):
            previous = {}
    feeds = summary.get("feeds_ok", {})
    espn_ok = feeds.get("espn") is True
    nba_ok = feeds.get("nba-cdn") is True
    if espn_ok and nba_ok and not summary.get("feed_warnings"):
        status = "ok"
    elif espn_ok or nba_ok:
        status = "partial"
    else:
        status = "error"
    observed_at = summary.get("observed_at_utc")
    payload = {
        "schemaVersion": 1,
        "status": status,
        "generatedAt": observed_at,
        "requestedDate": requested_date or summary.get("date"),
        "monitorDate": summary.get("date"),
        "lastSuccessfulAt": observed_at if espn_ok and nba_ok else previous.get("lastSuccessfulAt"),
        "sourceStatus": feeds,
        "games": summary.get("game_rows", []),
        "activeDiscrepancies": [row for row in summary.get("game_rows", []) if row.get("findings")],
        "counts": {
            "gamesCompared": summary.get("games", 0),
            "findings": summary.get("mismatches", 0),
            "feedWarnings": len(summary.get("feed_warnings", [])),
        },
        "feedWarnings": summary.get("feed_warnings", []),
        "notes": [
            "Score values are timestamped source observations, not a determination of which provider is correct.",
            "No match, unavailable source, or missing score is not interpreted as zero or as resolution.",
            "A mismatch creates an unverified investigation; human review is required before a case is confirmed.",
        ],
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(".json.tmp")
    temp_path.write_text(json.dumps(payload, indent=2) + "\n")
    temp_path.replace(path)
    return payload


def self_test():
    espn = parse_espn(json.loads((FIX_DIR / "espn_sample.json").read_text()))
    assert espn, "ESPN fixture produced no games"
    box = json.loads((FIX_DIR / "nba_boxscore_sample.json").read_text())
    key = next(iter(espn))
    c = check_cross_source(espn[key], box, True)
    assert c and c["check"] == "cross-source-total-mismatch", "cross-source check failed to fire on fixture"
    assert "214" in c["detail"] and "213" in c["detail"], "fixture should model a 213-vs-214 conflict"
    q = check_quarter_sum(espn[key], "ESPN")
    assert q is None, "ESPN fixture quarters should sum cleanly"
    pbp = json.loads((FIX_DIR / "nba_pbp_sample.json").read_text())
    assert parse_nba_pbp_final(pbp) == (110, 103), "PBP fixture final should be 110-103"
    missing = dict(espn[key], away_score=None)
    assert check_cross_source(missing, box, True) is None, "missing score must not be treated as zero"
    incomplete = dict(espn[key], away_score=None, home_score=None, quarters=[None], home_quarters=[None])
    assert not quarter_sum_observations(incomplete, "ESPN"), "incomplete lines must not be treated as a passing check"
    print("SELF-TEST PASS: source mismatch, incomplete-score guard, quarter sums, and PBP parsing behave.")
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", help="YYYYMMDD (default: today UTC)")
    ap.add_argument("--lookback", type=int, default=0, help="also check N previous days")
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args(argv)
    if args.self_test:
        return self_test()
    base = args.date or dt.datetime.now(dt.timezone.utc).strftime("%Y%m%d")
    dates = [(dt.datetime.strptime(base, "%Y%m%d") - dt.timedelta(days=i)).strftime("%Y%m%d")
             for i in range(args.lookback + 1)]
    all_ok = True
    latest_summary = None
    for index, d in enumerate(dates):
        s = monitor_date(d)
        print(json.dumps(s, indent=2))
        if index == 0:
            latest_summary = s
        if "UNAVAILABLE" in json.dumps(s["feeds_ok"]):
            all_ok = False
    if latest_summary is not None:
        write_current_snapshot(latest_summary, requested_date=base)
    return 0 if all_ok else 2


if __name__ == "__main__":
    sys.exit(main())
