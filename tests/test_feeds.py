from __future__ import annotations

import json
import unittest
from pathlib import Path

from monitor.feeds import (
    FeedError,
    build_observations,
    extract_latest_scoring_play,
    match_scoreboards,
    parse_espn_scoreboard,
    parse_nba_scoreboard,
)

FIXTURES = Path(__file__).parent / "fixtures"


def fixture(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


class FeedParsingTests(unittest.TestCase):
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
