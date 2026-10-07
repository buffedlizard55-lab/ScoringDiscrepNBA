from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("historical_score_monitor", ROOT / "scripts" / "monitor.py")
if _spec is None or _spec.loader is None:
    raise RuntimeError("Could not load the historical monitor module")
monitor = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = monitor
_spec.loader.exec_module(monitor)

FIXTURES = ROOT / "scripts" / "fixtures"


def fixture(name: str):
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


class ScoreParsingTests(unittest.TestCase):
    def test_offline_213_214_fixture_exposes_disagreement_without_assigning_fault(self):
        espn = monitor.parse_espn(fixture("espn_sample.json"))
        nba = fixture("nba_boxscore_sample.json")
        self.assertEqual(list(espn), ["FAK@SYN"])
        finding = monitor.check_cross_source(espn["FAK@SYN"], nba, True)
        self.assertIsNotNone(finding)
        self.assertEqual(finding["check"], "cross-source-total-mismatch")
        self.assertEqual(finding["scope"], "cross-source")
        self.assertIn("213", finding["detail"])
        self.assertIn("214", finding["detail"])
        self.assertNotIn("fault", finding)

    def test_missing_or_invalid_score_is_not_coerced_to_zero(self):
        self.assertIsNone(monitor.safe_int(None))
        self.assertIsNone(monitor.safe_int(""))
        self.assertIsNone(monitor.safe_int("not-a-score"))
        self.assertIsNone(monitor.safe_int("1.5"))
        self.assertIsNone(monitor.safe_int(-1))
        self.assertEqual(monitor.safe_int(0), 0)
        self.assertEqual(monitor.safe_int("0"), 0)

        parsed = monitor.parse_espn({"events": [{
            "competitions": [{
                "status": {"type": {"name": "STATUS_SCHEDULED"}},
                "competitors": [
                    {"homeAway": "away", "team": {"abbreviation": "AAA"}, "linescores": []},
                    {"homeAway": "home", "team": {"abbreviation": "BBB"}, "score": None},
                ],
            }]
        }]})
        self.assertIsNone(parsed["AAA@BBB"]["away_score"])
        self.assertIsNone(parsed["AAA@BBB"]["home_score"])
        self.assertIsNone(monitor.check_cross_source(parsed["AAA@BBB"], {
            "away_score": 0, "home_score": 0, "away": "AAA", "home": "BBB"
        }, False))

    def test_incomplete_period_lines_do_not_count_as_a_pass(self):
        incomplete = {
            "away": "AAA", "home": "BBB", "away_score": 10, "home_score": 9,
            "quarters": [10, None], "home_quarters": [9], "source": "espn",
        }
        observations = monitor.quarter_sum_observations(incomplete, "ESPN")
        self.assertEqual(len(observations), 1)  # Only the complete home-side check ran.
        self.assertEqual(observations[0]["scope"], "espn-home")
        self.assertEqual(observations[0]["evidence"]["period_sum"], 9)

    def test_nba_boxscore_parser_preserves_missing_score(self):
        parsed = monitor.parse_nba_boxscore({"game": {
            "awayTeam": {"teamTricode": "GS", "score": None, "periods": [{"score": None}]},
            "homeTeam": {"teamTricode": "POR", "periods": []},
        }})
        self.assertEqual(parsed["away"], "GSW")
        self.assertEqual(parsed["home"], "POR")
        self.assertIsNone(parsed["away_score"])
        self.assertIsNone(parsed["home_score"])
        self.assertEqual(parsed["quarters"], [None])
        self.assertIsNone(monitor.check_quarter_sum(parsed, "NBA-CDN"))

    def test_quarter_and_pbp_checks(self):
        espn = monitor.parse_espn(fixture("espn_sample.json"))["FAK@SYN"]
        self.assertIsNone(monitor.check_quarter_sum(espn, "ESPN"))
        pbp = fixture("nba_pbp_sample.json")
        self.assertEqual(monitor.parse_nba_pbp_final(pbp), (110, 103))
        self.assertEqual(monitor.check_pbp(fixture("nba_boxscore_sample.json"), (110, 103))["check"], "pbp-recompute-mismatch")
        self.assertIsNone(monitor.parse_nba_pbp_final({"game": {"actions": []}}))


class InvestigationLifecycleTests(unittest.TestCase):
    def test_upsert_preserves_original_and_changed_evidence(self):
        data = {"records": []}
        first = {
            "id": "2025-11-08-AAA-BBB-cross-source-total-mismatch-cross-source",
            "created_utc": "2025-11-08T17:00:00Z", "last_seen_utc": "2025-11-08T17:00:00Z",
            "game_date": "2025-11-08", "game_key": "AAA@BBB", "check": "cross-source-total-mismatch",
            "check_scope": "cross-source", "severity": "warn", "status": "detected",
            "evidence": {"espn": {"away_score": 110}, "nba_cdn": {"away_score": 111}, "detail": "110 vs 111"},
            "history": [],
        }
        self.assertEqual(monitor.upsert(data, dict(first)), "created")
        self.assertEqual(len(data["records"][0]["observations"]), 1)

        repeated = dict(first, last_seen_utc="2025-11-08T17:15:00Z")
        self.assertEqual(monitor.upsert(data, repeated), "updated")
        self.assertEqual(data["records"][0]["repeat_count"], 2)
        self.assertEqual(len(data["records"][0]["observations"]), 1)

        changed = dict(first, last_seen_utc="2025-11-08T17:30:00Z",
                       evidence={"espn": {"away_score": 111}, "nba_cdn": {"away_score": 112}, "detail": "111 vs 112"})
        monitor.upsert(data, changed)
        record = data["records"][0]
        self.assertEqual(len(record["observations"]), 2)
        self.assertEqual(record["observations"][0]["evidence"]["espn"]["away_score"], 110)
        self.assertEqual(record["observations"][1]["evidence"]["espn"]["away_score"], 111)
        self.assertEqual(record["last_changed_utc"], "2025-11-08T17:30:00Z")

    def test_feed_agreement_records_later_values_but_does_not_mark_resolved(self):
        record = {
            "id": "x", "game_date": "2025-11-08", "game_key": "AAA@BBB",
            "check": "cross-source-total-mismatch", "check_scope": "cross-source",
            "status": "investigating", "created_utc": "2025-11-08T17:00:00Z",
            "evidence": {"detail": "first observation"}, "history": [],
        }
        data = {"records": [record]}
        resolved_snapshot = {"espn": {"away_score": 111}, "nba_cdn": {"away_score": 111}}
        count = monitor.resolve_if_cleared(
            data,
            {("2025-11-08", "AAA@BBB", "cross-source-total-mismatch", "cross-source"): resolved_snapshot},
            "2025-11-08T17:30:00Z",
        )
        self.assertEqual(count, 1)
        self.assertEqual(record["status"], "correction-observed")
        self.assertEqual(record["resolution_observations"][0]["evidence"], resolved_snapshot)
        self.assertIn("not a human-confirmed resolution", record["history"][-1]["note"])

    def test_missing_check_scope_cannot_clear_legacy_record(self):
        record = {
            "id": "legacy", "game_date": "2025-11-08", "game_key": "AAA@BBB",
            "check": "cross-source-total-mismatch", "status": "detected", "history": [],
        }
        data = {"records": [record]}
        count = monitor.resolve_if_cleared(
            data,
            {("2025-11-08", "AAA@BBB", "cross-source-total-mismatch", "cross-source"): {}},
            "2025-11-08T17:30:00Z",
        )
        self.assertEqual(count, 0)
        self.assertEqual(record["status"], "detected")

    def test_partial_snapshot_keeps_last_successful_timestamp(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            previous_path = root / "data/monitor/current.json"
            previous_path.parent.mkdir(parents=True)
            previous_path.write_text(json.dumps({"lastSuccessfulAt": "2025-11-08T17:00:00Z"}), encoding="utf-8")
            summary = {
                "date": "20251108", "observed_at_utc": "2025-11-08T17:20:00Z",
                "games": 0, "game_rows": [], "mismatches": 0,
                "feeds_ok": {"espn": True, "nba-cdn": "UNAVAILABLE: fixture outage"},
                "feed_warnings": ["NBA scoreboard unavailable"],
            }
            snapshot = monitor.write_current_snapshot(summary, root=root)
            self.assertEqual(snapshot["status"], "partial")
            self.assertEqual(snapshot["lastSuccessfulAt"], "2025-11-08T17:00:00Z")
            self.assertEqual(snapshot["sourceStatus"]["nba-cdn"], "UNAVAILABLE: fixture outage")

    def test_monitor_persists_mismatch_then_records_convergence_values(self):
        with tempfile.TemporaryDirectory() as temporary:
            inv_path = Path(temporary) / "investigations.json"
            inv_path.write_text(json.dumps({"records": []}), encoding="utf-8")
            nba_board = {"scoreboard": {"games": [{
                "gameId": "fixture-1", "gameStatus": 3, "gameStatusText": "Final",
                "awayTeam": {"teamTricode": "FAK"}, "homeTeam": {"teamTricode": "SYN"},
            }]}}
            nba_box = {"game": {
                "awayTeam": {"teamTricode": "FAK", "score": 111,
                             "periods": [{"score": 30}, {"score": 26}, {"score": 28}, {"score": 27}]},
                "homeTeam": {"teamTricode": "SYN", "score": 103,
                             "periods": [{"score": 25}, {"score": 26}, {"score": 24}, {"score": 28}]},
            }}
            espn_first = fixture("espn_sample.json")
            pbp = fixture("nba_pbp_sample.json")

            def fetch(url):
                if url.startswith(monitor.ESPN_URL.split("?dates=")[0]):
                    return espn_first
                if url.startswith("https://cdn.nba.com/static/json/liveData/scoreboard/"):
                    return nba_board
                if "/boxscore/" in url:
                    return nba_box
                if "/playbyplay/" in url:
                    return pbp
                raise AssertionError(f"Unexpected fixture URL: {url}")

            with patch.object(monitor, "INV_PATH", inv_path), patch.object(monitor, "fetch_json", side_effect=fetch):
                first = monitor.monitor_date("20251108", now=datetime(2025, 11, 8, 17, 0, tzinfo=timezone.utc))
                self.assertEqual(first["mismatches"], 2)  # Cross-feed difference and PBP/boxscore difference.
                self.assertEqual(first["game_rows"][0]["comparison"], "different")
                self.assertEqual(first["game_rows"][0]["espn"]["score"]["total"], 213)
                current = monitor.write_current_snapshot(first, requested_date="20251108", root=Path(temporary))
                self.assertEqual(current["status"], "ok")
                self.assertEqual(current["counts"]["gamesCompared"], 1)
                self.assertEqual(current["activeDiscrepancies"][0]["game_key"], "FAK@SYN")
                data = json.loads(inv_path.read_text(encoding="utf-8"))
                cross = next(r for r in data["records"] if r["check"] == "cross-source-total-mismatch")
                self.assertEqual(cross["status"], "detected")
                self.assertEqual(cross["observations"][0]["evidence"]["espn"]["away_score"], 110)
                self.assertEqual(cross["observations"][0]["evidence"]["nba_cdn"]["away_score"], 111)

                espn_converged = json.loads(json.dumps(espn_first))
                away = next(t for t in espn_converged["events"][0]["competitions"][0]["competitors"] if t["homeAway"] == "away")
                away["score"] = "111"
                away["linescores"][0]["value"] = 31

                def fetch_converged(url):
                    if url.startswith(monitor.ESPN_URL.split("?dates=")[0]):
                        return espn_converged
                    return fetch(url)

                with patch.object(monitor, "fetch_json", side_effect=fetch_converged):
                    second = monitor.monitor_date("20251108", now=datetime(2025, 11, 8, 17, 20, tzinfo=timezone.utc))
                self.assertEqual(second["auto_advanced_to_correction_observed"], 1)
                data = json.loads(inv_path.read_text(encoding="utf-8"))
                cross = next(r for r in data["records"] if r["check"] == "cross-source-total-mismatch")
                self.assertEqual(cross["status"], "correction-observed")
                self.assertEqual(cross["observations"][0]["evidence"]["espn"]["away_score"], 110)
                self.assertEqual(cross["resolution_observations"][0]["evidence"]["espn"]["away_score"], 111)
                self.assertEqual(cross["resolution_observations"][0]["evidence"]["nba_cdn"]["away_score"], 111)
                self.assertTrue(any("not a human-confirmed resolution" in item["note"] for item in cross["history"]))


if __name__ == "__main__":
    unittest.main()
