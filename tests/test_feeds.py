from __future__ import annotations

import json
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError

from monitor.feeds import (
    FeedError,
    build_observations,
    extract_latest_scoring_play,
    fetch_json,
    match_scoreboards,
    parse_espn_scoreboard,
    parse_nba_scoreboard,
)

FIXTURES = Path(__file__).parent / "fixtures"


def fixture(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


class FeedParsingTests(unittest.TestCase):
    def test_http_error_preserves_status_code_for_source_health_diagnostics(self) -> None:
        error = HTTPError("https://nba.example/scoreboard", 403, "Forbidden", None, None)
        with patch("monitor.feeds.urlopen", side_effect=error):
            with self.assertRaisesRegex(FeedError, "HTTP 403"):
                fetch_json("https://nba.example/scoreboard")

    def test_nba_scoreboard_normalizes_teams_and_clock(self) -> None:
        games = parse_nba_scoreboard(fixture("nba-scoreboard.json"))
        self.assertEqual(len(games), 1)
        game = games[0]
        self.assertEqual(game["game_id"], "0022500029")
        self.assertEqual(game["game_date"], "2025-11-07")
        self.assertEqual(game["status"], "live")
        self.assertEqual(game["period"], 2)
        self.assertEqual(game["away_team"]["abbreviation"], "CLE")
        self.assertEqual(game["home_team"]["score"], 39)

    def test_espn_scoreboard_normalizes_abbreviation_and_score(self) -> None:
        games = parse_espn_scoreboard(fixture("espn-scoreboard.json"))
        self.assertEqual(len(games), 1)
        game = games[0]
        self.assertEqual(game["home_team"]["abbreviation"], "WAS")
        self.assertEqual(game["home_team"]["score"], 38)
        self.assertEqual(game["status"], "live")

    def test_join_detects_difference_without_declaring_which_source_is_correct(self) -> None:
        nba = parse_nba_scoreboard(fixture("nba-scoreboard.json"))
        espn = parse_espn_scoreboard(fixture("espn-scoreboard.json"))
        joined = match_scoreboards(nba, espn)
        self.assertEqual(len(joined), 1)
        observations = build_observations(nba, espn, "2026-10-07T04:00:00Z")
        self.assertTrue(observations[0]["score_mismatch"])
        self.assertEqual(observations[0]["scores"]["nba"]["home"], 39)
        self.assertEqual(observations[0]["scores"]["espn"]["home"], 38)
        self.assertNotIn("verification_status", observations[0])  # differences are not auto-verified

    def test_dates_use_eastern_calendar_including_dst(self):
        payload = fixture("espn-scoreboard.json")
        for timestamp, expected in [("2025-11-08T00:00Z", "2025-11-07"),
                                    ("2025-07-02T03:30Z", "2025-07-01"),
                                    ("2025-01-02T04:30Z", "2025-01-01")]:
            payload["events"][0]["date"] = timestamp
            self.assertEqual(parse_espn_scoreboard(payload)[0]["game_date"], expected)

    def test_different_day_or_unknown_date_is_not_compared(self):
        nba = parse_nba_scoreboard(fixture("nba-scoreboard.json"))
        espn = parse_espn_scoreboard(fixture("espn-scoreboard.json"))
        for date in ["2025-11-08", None]:
            espn[0]["game_date"] = date
            rows = build_observations(nba, espn, "2026-10-07T04:00:00Z")
            self.assertEqual(len(rows), 2)
            self.assertTrue(all(row["score_mismatch"] is None for row in rows))
            self.assertIsNone(match_scoreboards(nba, espn)[0][1])

    def test_active_union_rejects_duplicates_in_either_provider(self):
        nba = parse_nba_scoreboard(fixture("nba-scoreboard.json"))
        espn = parse_espn_scoreboard(fixture("espn-scoreboard.json"))
        for primary, secondary in [(nba * 2, espn), (nba, espn * 2)]:
            rows = build_observations(primary, secondary, "2026-10-07T04:00:00Z")
            self.assertEqual(len(rows), 3)
            self.assertTrue(all(row["score_mismatch"] is None for row in rows))
            self.assertTrue(all(match is None for _, match in match_scoreboards(primary, secondary)))

    def test_provider_context_is_preserved_for_latency_review(self):
        nba = parse_nba_scoreboard(fixture("nba-scoreboard.json"))
        espn = parse_espn_scoreboard(fixture("espn-scoreboard.json"))
        row = build_observations(nba, espn, "2026-10-07T04:00:00Z")[0]
        self.assertEqual(row["scores"]["espn"]["game_id"], "401809511")
        self.assertEqual(row["scores"]["espn"]["clock"], "8:15")
        self.assertEqual(row["scores"]["nba"]["status"], "live")

    def test_nba_scoreboard_date_fallback(self):
        payload = fixture("nba-scoreboard.json")
        game = payload["scoreboard"]["games"][0]
        for key in ["gameEt", "gameDateEst", "gameDate"]:
            game.pop(key, None)
        payload["scoreboard"]["gameDate"] = "2025-11-07"
        self.assertEqual(parse_nba_scoreboard(payload)[0]["game_date"], "2025-11-07")

    def test_pbp_uses_explicit_scoring_flag_only(self) -> None:
        latest = extract_latest_scoring_play(fixture("nba-pbp.json"))
        self.assertIsNotNone(latest)
        self.assertEqual(latest["player"], "Tre Johnson")
        self.assertEqual(latest["score_home"], 40)
        self.assertEqual(latest["description"], "Tre Johnson makes free throw 1 of 2")

    def test_unknown_pbp_shape_has_no_invented_play(self) -> None:
        self.assertIsNone(extract_latest_scoring_play({"game": {"actions": []}}))
        self.assertIsNone(extract_latest_scoring_play({"unexpected": []}))

    def test_invalid_top_level_shapes_fail_closed(self) -> None:
        with self.assertRaises(FeedError):
            parse_nba_scoreboard({"scoreboard": {"games": "not-a-list"}})
        with self.assertRaises(FeedError):
            parse_espn_scoreboard({"events": None})

    def test_ambiguous_duplicate_pair_is_not_guessed(self) -> None:
        nba = parse_nba_scoreboard(fixture("nba-scoreboard.json"))
        espn = parse_espn_scoreboard(fixture("espn-scoreboard.json"))
        duplicate = dict(espn[0])
        duplicate["game_id"] = "another-event"
        matches = match_scoreboards(nba, espn + [duplicate])
        self.assertIsNone(matches[0][1])

    def test_reversed_home_away_roles_are_not_joined_as_a_score_difference(self) -> None:
        nba = parse_nba_scoreboard(fixture("nba-scoreboard.json"))
        espn_payload = fixture("espn-scoreboard.json")
        competitors = espn_payload["events"][0]["competitions"][0]["competitors"]
        competitors[0]["homeAway"], competitors[1]["homeAway"] = "home", "away"
        espn = parse_espn_scoreboard(espn_payload)
        observation = build_observations(nba, espn, "2026-10-07T04:00:00Z")[0]
        self.assertIsNone(observation["score_mismatch"])
        self.assertIsNone(match_scoreboards(nba, espn)[0][1])

    def test_malformed_game_rows_fail_closed_instead_of_being_silently_dropped(self) -> None:
        nba_payload = fixture("nba-scoreboard.json")
        nba_payload["scoreboard"]["games"][0]["homeTeam"] = None
        with self.assertRaises(FeedError):
            parse_nba_scoreboard(nba_payload)

        espn_payload = fixture("espn-scoreboard.json")
        espn_payload["events"][0]["competitions"][0]["competitors"] = []
        with self.assertRaises(FeedError):
            parse_espn_scoreboard(espn_payload)


if __name__ == "__main__":
    unittest.main()
