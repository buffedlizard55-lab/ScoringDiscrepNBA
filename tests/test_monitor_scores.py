from __future__ import annotations

import json
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import monitor_scores as monitor  # noqa: E402

FIXTURES = ROOT / "tests" / "fixtures"


def fixture(name: str):
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


class ScoreParsingTests(unittest.TestCase):
    def test_nba_scoreboard_normalises_and_preserves_scores(self):
        games = monitor.parse_nba_scoreboard(fixture("nba-scoreboard.json"))
        self.assertEqual(len(games), 1)
        self.assertEqual(games[0]["nbaGameId"], "0022500029")
        self.assertEqual(games[0]["awayTeam"]["code"], "CLE")
        self.assertEqual(games[0]["homeTeam"]["code"], "WAS")
        self.assertEqual(games[0]["homeTeam"]["score"], 115)
        self.assertEqual(games[0]["statusBucket"], "post")

    def test_espn_home_away_order_and_aliases(self):
        games = monitor.parse_espn_scoreboard(fixture("espn-scoreboard.json"))
        self.assertEqual(len(games), 1)
        self.assertEqual(games[0]["homeTeam"]["code"], "WAS")
        self.assertEqual(games[0]["awayTeam"]["code"], "CLE")
        self.assertEqual(games[0]["homeTeam"]["score"], 114)

    def test_missing_score_is_not_zero(self):
        self.assertIsNone(monitor.score_value(None))
        self.assertIsNone(monitor.score_value(""))
        self.assertEqual(monitor.score_value("0"), 0)
        self.assertIsNone(monitor.score_value("1.5"))
        self.assertIsNone(monitor.score_value(-1))

    def test_team_aliases(self):
        self.assertEqual(monitor.normalise_team_code("GS"), "GSW")
        self.assertEqual(monitor.normalise_team_code("WSH"), "WAS")
        self.assertEqual(monitor.normalise_team_code("NY"), "NYK")

    def test_scoreboard_comparison_flags_difference_without_assigning_fault(self):
        nba = monitor.parse_nba_scoreboard(fixture("nba-scoreboard.json"))
        espn = monitor.parse_espn_scoreboard(fixture("espn-scoreboard.json"))
        rows = monitor.compare_scoreboards(nba, espn)
        self.assertEqual(len(rows), 1)
        self.assertTrue(rows[0]["scoreMismatch"])
        self.assertEqual(rows[0]["nbaScore"], {"away": 148, "home": 115})
        self.assertEqual(rows[0]["espnScore"], {"away": 148, "home": 114})
        self.assertEqual(rows[0]["matchStatus"], "matched")
        self.assertNotIn("fault", rows[0])

    def test_unmatched_and_ambiguous_games_are_not_compared(self):
        nba = monitor.parse_nba_scoreboard(fixture("nba-scoreboard.json"))
        espn = monitor.parse_espn_scoreboard(fixture("espn-scoreboard.json"))
        self.assertEqual(monitor.compare_scoreboards(nba, [])[0]["matchStatus"], "no_secondary_match")
        duplicate = [dict(espn[0]), dict(espn[0], espnEventId="duplicate")]
        rows = monitor.compare_scoreboards(nba, duplicate)
        self.assertEqual(rows[0]["matchStatus"], "ambiguous_secondary_match")
        self.assertFalse(rows[0]["scoreMismatch"])

    def test_pbp_context_is_limited_and_labels_are_only_raw_context(self):
        actions = monitor.parse_pbp_context(fixture("nba-pbp.json"), limit=8)
        self.assertEqual(len(actions), 8)
        self.assertEqual(actions[0]["clock"], "8:15")
        self.assertEqual(actions[0]["description"], "Tre Johnson Free Throw 1 of 2")


class MonitorLifecycleTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        (self.root / "data/monitor").mkdir(parents=True)
        self.nba = fixture("nba-scoreboard.json")
        self.espn = fixture("espn-scoreboard.json")
        self.pbp = fixture("nba-pbp.json")

    def tearDown(self):
        self.temp.cleanup()

    def fetcher(self, nba=None, espn=None):
        nba = nba or self.nba
        espn = espn or self.espn

        def get_json(url):
            if url == monitor.NBA_SCOREBOARD_URL:
                return nba
            if url.startswith(monitor.ESPN_SCOREBOARD_URL):
                query = parse_qs(urlparse(url).query)
                self.assertIn("dates", query)
                return espn
            if "/playbyplay/" in url:
                return self.pbp
            raise AssertionError(f"Unexpected URL in fixture test: {url}")

        return get_json

    def test_mismatch_is_saved_as_unverified_then_feed_convergence_is_not_research_resolution(self):
        first = monitor.run_monitor(
            self.root,
            datetime(2025, 11, 8, 17, 0, tzinfo=timezone.utc),
            fetch_json=self.fetcher(),
            include_pbp=True,
        )
        self.assertEqual(first["status"], "ok")
        self.assertEqual(len(first["activeDiscrepancies"]), 1)
        self.assertTrue(first["durableStateChanged"])

        candidates_path = self.root / "data/monitor/candidates.json"
        candidates = json.loads(candidates_path.read_text(encoding="utf-8"))["candidates"]
        self.assertEqual(len(candidates), 1)
        candidate = candidates[0]
        self.assertEqual(candidate["reviewStatus"], "unverified")
        self.assertEqual(candidate["investigationStatus"], "needs_review")
        self.assertEqual(candidate["monitorStatus"], "active_source_divergence")
        self.assertEqual(candidate["episodes"][0]["playByPlayContext"]["mode"], "nearby_feed_context_not_causal")
        self.assertEqual(len(candidate["episodes"][0]["playByPlayContext"]["actions"]), 8)
        self.assertEqual(len((self.root / "data/monitor/observations.jsonl").read_text().splitlines()), 1)

        repeated = monitor.run_monitor(
            self.root,
            datetime(2025, 11, 8, 17, 15, tzinfo=timezone.utc),
            fetch_json=self.fetcher(),
            include_pbp=True,
        )
        self.assertFalse(repeated["durableStateChanged"], "unchanged polls must not generate timestamp-only commits")
        self.assertEqual(len((self.root / "data/monitor/observations.jsonl").read_text().splitlines()), 1)

        converged_espn = fixture("espn-scoreboard.json")
        converged_espn["events"][0]["competitions"][0]["competitors"][0]["score"] = "115"
        resolved = monitor.run_monitor(
            self.root,
            datetime(2025, 11, 8, 17, 30, tzinfo=timezone.utc),
            fetch_json=self.fetcher(espn=converged_espn),
            include_pbp=False,
        )
        self.assertEqual(resolved["activeDiscrepancies"], [])
        self.assertTrue(resolved["durableStateChanged"])
        candidate = json.loads(candidates_path.read_text(encoding="utf-8"))["candidates"][0]
        self.assertEqual(candidate["monitorStatus"], "feed_converged")
        self.assertEqual(candidate["reviewStatus"], "unverified")
        self.assertEqual(candidate["investigationStatus"], "needs_review")
        self.assertIn("operational convergence only", candidate["monitorNote"])
        self.assertIsNotNone(candidate["episodes"][0]["feedConvergedAt"])
        self.assertEqual(len((self.root / "data/monitor/observations.jsonl").read_text().splitlines()), 2)

        # Simulate a source-backed manual close through a reviewed repository edit,
        # then verify a genuinely new divergence archives that disposition and reopens.
        candidate["reviewStatus"] = "reviewed_unresolved"
        candidate["investigationStatus"] = "closed_unresolved"
        candidate["reviewer"] = "Fixture reviewer"
        candidate["reviewedAt"] = "2025-11-08T17:32:00Z"
        candidate["resolution"] = "Fixture review could not establish which provider was first correct."
        candidate["resolutionSourceIds"] = ["nba-live-scoreboard-feed"]
        candidates_path.write_text(json.dumps({"schemaVersion": 1, "candidates": [candidate]}, indent=2) + "\n", encoding="utf-8")
        reopened = monitor.run_monitor(
            self.root,
            datetime(2025, 11, 8, 17, 45, tzinfo=timezone.utc),
            fetch_json=self.fetcher(),
            include_pbp=False,
        )
        self.assertTrue(reopened["durableStateChanged"])
        candidate = json.loads(candidates_path.read_text(encoding="utf-8"))["candidates"][0]
        self.assertEqual(candidate["monitorStatus"], "active_source_divergence")
        self.assertEqual(candidate["investigationStatus"], "needs_review")
        self.assertEqual(candidate["reviewStatus"], "unverified")
        self.assertEqual(len(candidate["episodes"]), 2)
        self.assertEqual(candidate["reviewHistory"][0]["resolution"], "Fixture review could not establish which provider was first correct.")
        self.assertEqual(len((self.root / "data/monitor/observations.jsonl").read_text().splitlines()), 3)

    def test_failed_source_does_not_resolve_candidate(self):
        initial = monitor.run_monitor(
            self.root,
            datetime(2025, 11, 8, 17, 0, tzinfo=timezone.utc),
            fetch_json=self.fetcher(),
            include_pbp=False,
        )
        self.assertEqual(initial["status"], "ok")
        candidates_path = self.root / "data/monitor/candidates.json"
        before = candidates_path.read_text(encoding="utf-8")

        def fail(_url):
            raise OSError("fixture outage")

        failed = monitor.run_monitor(
            self.root,
            datetime(2025, 11, 8, 17, 15, tzinfo=timezone.utc),
            fetch_json=fail,
            include_pbp=False,
        )
        self.assertEqual(failed["status"], "error")
        self.assertEqual(candidates_path.read_text(encoding="utf-8"), before)
        self.assertEqual(len(failed["activeDiscrepancies"]), 0)

    def test_no_score_and_no_match_never_open_candidate(self):
        nba = fixture("nba-scoreboard.json")
        nba["scoreboard"]["games"][0]["homeTeam"]["score"] = None
        result = monitor.run_monitor(
            self.root,
            datetime(2025, 11, 8, 17, 0, tzinfo=timezone.utc),
            fetch_json=self.fetcher(nba=nba),
            include_pbp=False,
        )
        self.assertEqual(result["activeDiscrepancies"], [])
        candidates_path = self.root / "data/monitor/candidates.json"
        candidates = json.loads(candidates_path.read_text())["candidates"] if candidates_path.exists() else []
        self.assertEqual(candidates, [])

    def test_partial_espn_date_queries_are_reported_as_partial(self):
        nba = self.nba
        espn = self.espn
        first_query = True

        def partial_fetch(url):
            nonlocal first_query
            if url == monitor.NBA_SCOREBOARD_URL:
                return nba
            if url.startswith(monitor.ESPN_SCOREBOARD_URL):
                if first_query:
                    first_query = False
                    return espn
                raise OSError("one date query unavailable")
            raise AssertionError(f"Unexpected URL in fixture test: {url}")

        result = monitor.run_monitor(
            self.root,
            datetime(2025, 11, 8, 17, 0, tzinfo=timezone.utc),
            fetch_json=partial_fetch,
            include_pbp=False,
        )
        self.assertEqual(result["status"], "partial")
        self.assertTrue(result["sourceStatus"]["espn_secondary"]["ok"])
        self.assertEqual(len(result["sourceStatus"]["espn_secondary"]["warnings"]), 2)
        self.assertTrue(result["activeDiscrepancies"])
        self.assertIn("before treating the comparison as complete", " ".join(result["notes"]))


if __name__ == "__main__":
    unittest.main()
