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
A 'feed-unavailable' record is logged (not a discrepancy) when a source is unreachable.

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

def parse_espn(scoreboard):
    """Return {key: {away, home, away_score, home_score, status, quarters}} keyed 'AWY@HME'."""
    games = {}
    for ev in scoreboard.get("events", []):
        try:
            comp = ev["competitions"][0]
            teams = {t["homeAway"]: t for t in comp["competitors"]}
            a, h = teams["away"], teams["home"]
            a_code = norm_team(a["team"].get("abbreviation") or a["team"].get("shortDisplayName"))
            h_code = norm_team(h["team"].get("abbreviation") or h["team"].get("shortDisplayName"))
            games[f"{a_code}@{h_code}"] = {
                "away": a_code, "home": h_code,
                "away_score": int(a.get("score", 0)), "home_score": int(h.get("score", 0)),
                "status": comp.get("status", {}).get("type", {}).get("name", "UNKNOWN"),
                "quarters": [int(ls.get("value", 0)) for ls in a.get("linescores", [])],
                "home_quarters": [int(ls.get("value", 0)) for ls in h.get("linescores", [])],
                "source": "espn",
            }
        except (KeyError, ValueError, TypeError):
            continue
    return games


def parse_nba_scoreboard(sb):
    """Return {gameId: meta} from NBA liveData scoreboard; meta includes tricode matchup + status."""
    games = {}
    board = sb.get("scoreboard", sb)
    for g in board.get("games", []):
        try:
            gid = g.get("gameId")
            a_code = norm_team(g.get("awayTeam", {}).get("teamTricode"))
            h_code = norm_team(g.get("homeTeam", {}).get("teamTricode"))
            games[gid] = {
                "away": a_code, "home": h_code,
                "status": str(g.get("gameStatusText", "")),
                "is_final": bool(g.get("gameStatus") == 3 or "final" in str(g.get("gameStatusText", "")).lower()),
            }
        except (AttributeError, TypeError):
            continue
    return games


def parse_nba_boxscore(bx):
    game = bx.get("game", bx)
    a = game.get("awayTeam", {})
    h = game.get("homeTeam", {})
    aq = [int(p.get("score", 0)) for p in a.get("periods", [])]
    hq = [int(p.get("score", 0)) for p in h.get("periods", [])]
    return {
        "away": norm_team(a.get("teamTricode")), "home": norm_team(h.get("teamTricode")),
        "away_score": int(a.get("score", 0)), "home_score": int(h.get("score", 0)),
        "quarters": aq, "home_quarters": hq, "source": "nba-cdn",
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

def check_cross_source(espn, nba, is_final):
    if espn["away_score"] != nba["away_score"] or espn["home_score"] != nba["home_score"]:
        return {
            "check": "cross-source-total-mismatch",
            "severity": "warn" if is_final else "info",
            "detail": (f"ESPN {espn['away']} {espn['away_score']} @ {espn['home']} {espn['home_score']} "
                       f"(total {espn['away_score'] + espn['home_score']}) vs NBA-CDN "
                       f"{nba['away_score']}-{nba['home_score']} (total {nba['away_score'] + nba['home_score']}). "
                       + ("FINAL — possible 213-vs-214-class conflict." if is_final else "Live game — may be feed lag; recheck at final.")),
        }
    return None


def check_quarter_sum(side, label):
    if side["quarters"] and sum(side["quarters"]) != side["away_score"]:
        return {"check": "quarter-sum-mismatch",
                "severity": "warn",
                "detail": f"{label} away quarters {side['quarters']} sum to {sum(side['quarters'])} != total {side['away_score']}"}
    if side["home_quarters"] and sum(side["home_quarters"]) != side["home_score"]:
        return {"check": "quarter-sum-mismatch",
                "severity": "warn",
                "detail": f"{label} home quarters {side['home_quarters']} sum to {sum(side['home_quarters'])} != total {side['home_score']}"}
    return None


def check_pbp(nba_box, pbp_final):
    if pbp_final is None:
        return None
    if pbp_final[0] != nba_box["away_score"] or pbp_final[1] != nba_box["home_score"]:
        return {"check": "pbp-recompute-mismatch",
                "severity": "warn",
                "detail": (f"NBA PBP final running score {pbp_final[0]}-{pbp_final[1]} != "
                           f"NBA boxscore {nba_box['away_score']}-{nba_box['home_score']}. Internal inconsistency in league data.")}
    return None


# ---------------- investigation store ----------------

def load_investigations():
    data = json.loads(INV_PATH.read_text())
    data.setdefault("records", [])
    return data


def save_investigations(data):
    INV_PATH.write_text(json.dumps(data, indent=2) + "\n")


def upsert(data, new):
    for rec in data["records"]:
        if rec["id"] == new["id"]:
            rec["last_seen_utc"] = new["last_seen_utc"]
            rec["evidence"] = new["evidence"]
            rec["history"].append({"at": new["last_seen_utc"], "note": "Mismatch still present on re-check."})
            return "updated"
    data["records"].append(new)
    return "created"


def resolve_if_cleared(data, ok_keys, now):
    """Advance detected/investigating records to correction-observed when a check that
    was actually performed in this run now agrees. Checks not performed (e.g. PBP on
    live games, games absent from this run's date) never trigger advancement."""
    n = 0
    for rec in data["records"]:
        if rec["status"] not in ("detected", "investigating"):
            continue
        key = (rec["game_date"], rec["game_key"], rec["check"])
        if key in ok_keys:
            rec["status"] = "correction-observed"
            rec["history"].append({"at": now, "note": "Sources agree again — possible correction or transient feed lag cleared. Needs human review before resolving."})
            n += 1
    return n


# ---------------- main flow ----------------

def monitor_date(datestr, live_fetch=True):
    now = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    data = load_investigations()
    summary = {"date": datestr, "games": 0, "mismatches": 0, "created": 0, "updated": 0, "feeds_ok": {}}
    try:
        espn_raw = fetch_json(ESPN_URL.format(datestr=datestr)) if live_fetch else json.loads((FIX_DIR / "espn_sample.json").read_text())
        summary["feeds_ok"]["espn"] = True
    except Exception as exc:  # noqa: BLE001
        summary["feeds_ok"]["espn"] = f"UNAVAILABLE: {exc}"
        save_investigations(data)
        return summary
    espn_games = parse_espn(espn_raw)
    try:
        season = season_year_for(datestr)
        if live_fetch:
            nba_sb = parse_nba_scoreboard(fetch_json(NBA_SCOREBOARD_URL.format(season=season)))
        else:
            nba_sb = json.loads((FIX_DIR / "nba_scoreboard_sample.json").read_text())
        summary["feeds_ok"]["nba-cdn"] = True
    except Exception as exc:  # noqa: BLE001
        summary["feeds_ok"]["nba-cdn"] = f"UNAVAILABLE: {exc}"
        nba_sb = {}

    by_matchup = {}
    for gid, meta in nba_sb.items():
        if gid.startswith("_") or not isinstance(meta, dict):
            continue
        by_matchup[f"{meta['away']}@{meta['home']}"] = (gid, meta)

    ok_keys = set()
    for key, espn in espn_games.items():
        summary["games"] += 1
        is_final = "final" in espn["status"].lower()
        findings = []
        performed = set()
        q = check_quarter_sum(espn, "ESPN")
        performed.add("quarter-sum-mismatch")
        if q:
            findings.append(q)
        nba_box = None
        if key in by_matchup:
            gid, meta = by_matchup[key]
            final = is_final or meta.get("is_final", False)
            try:
                if live_fetch:
                    nba_box = parse_nba_boxscore(fetch_json(NBA_BOXSCORE_URL.format(game_id=gid)))
                else:
                    nba_box = json.loads((FIX_DIR / "nba_boxscore_sample.json").read_text())
                q2 = check_quarter_sum(nba_box, "NBA-CDN")
                if q2:
                    findings.append(q2)
                c = check_cross_source(espn, nba_box, final)
                performed.add("cross-source-total-mismatch")
                if c:
                    findings.append(c)
                if final:
                    try:
                        pbp = fetch_json(NBA_PBP_URL.format(game_id=gid)) if live_fetch else json.loads((FIX_DIR / "nba_pbp_sample.json").read_text())
                        p = check_pbp(nba_box, parse_nba_pbp_final(pbp))
                        performed.add("pbp-recompute-mismatch")
                        if p:
                            findings.append(p)
                    except Exception as exc:  # noqa: BLE001
                        findings.append({"check": "feed-unavailable", "severity": "info",
                                         "detail": f"NBA PBP fetch failed for {gid}: {exc}"})
            except Exception as exc:  # noqa: BLE001
                findings.append({"check": "feed-unavailable", "severity": "info",
                                 "detail": f"NBA boxscore fetch failed for {gid}: {exc}"})
        for f in findings:
            if f["check"] == "feed-unavailable":
                continue  # feeds failing is operational noise, not a discrepancy
            summary["mismatches"] += 1
            rid = f"{datestr}-{key}-{f['check']}"
            rec = {"id": rid, "created_utc": now, "last_seen_utc": now, "game_date": datestr,
                   "away_team": espn["away"], "home_team": espn["home"], "game_key": key,
                   "check": f["check"], "severity": f["severity"], "status": "detected",
                   "evidence": {"espn": {k: espn[k] for k in ("away_score", "home_score", "status")},
                                "nba_cdn": ({k: nba_box[k] for k in ("away_score", "home_score")} if nba_box else None),
                                "detail": f["detail"]},
                   "history": [{"at": now, "note": "Auto-detected by monitor.py. Human review required."}]}
            res = upsert(data, rec)
            summary[res] += 1
        failed = {f["check"] for f in findings if f["check"] != "feed-unavailable"}
        for chk in performed - failed:
            ok_keys.add((datestr, key, chk))
    data["records"].sort(key=lambda r: r["created_utc"], reverse=True)
    summary["auto_advanced_to_correction_observed"] = resolve_if_cleared(data, ok_keys, now)
    save_investigations(data)
    return summary


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
    print("SELF-TEST PASS: 213-vs-214 fixture detected; quarter + PBP checks behave.")
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
    for d in dates:
        s = monitor_date(d)
        print(json.dumps(s, indent=2))
        if "UNAVAILABLE" in json.dumps(s["feeds_ok"]):
            all_ok = False
    return 0 if all_ok else 2


if __name__ == "__main__":
    sys.exit(main())
