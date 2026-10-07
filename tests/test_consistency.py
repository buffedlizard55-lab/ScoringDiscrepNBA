"""Tests for the single-provider arithmetic consistency check.

Provenance of ``tests/fixtures/espn-summary-401809511.json``: it is a trimmed
excerpt of the live ESPN summary response for event 401809511 (Cleveland
Cavaliers at Washington Wizards, 2025-11-07), retrieved from
https://site.api.espn.com/apis/site/v2/sports/basketball/nba/summary?event=401809511
on 2026-10-07. Every number kept in the fixture (FG 52-110 / 20-45 / 24-31 for
Cleveland; 41-91 / 15-41 / 18-23 for Washington) is the value that response
contained. Unused sections were dropped; no value was invented.

Cleveland: 2 * (52 - 20) + 3 * 20 + 24 = 64 + 60 + 24 = 148
Washington: 2 * (41 - 15) + 3 * 15 + 18 = 52 + 45 + 18 = 115
Both match the corrected final 148-115 recorded in data/reviewed-cases.json.
"""

from __future__ import annotations

import json
import unittest
from pathlib import Path

from monitor.consistency import (
    derive_points_from_components,
    espn_consistency_checks,
    espn_team_components,
)

FIXTURES = Path(__file__).parent / "fixtures"


def fixture() -> dict:
    return json.loads((FIXTURES / "espn-summary-401809511.json").read_text(encoding="utf-8"))


class ArithmeticTests(unittest.TestCase):
    def test_derived_points_formula(self) -> None:
        self.assertEqual(
            derive_points_from_components(
                {"fieldGoals": (52, 110), "threePointers": (20, 45), "freeThrows": (24, 31)}
            ),
            148,
        )
        self.assertEqual(
            derive_points_from_components(
                {"fieldGoals": (41, 91), "threePointers": (15, 41), "freeThrows": (18, 23)}
            ),
            115,
        )

    def test_impossible_components_are_not_derived(self) -> None:
        self.assertIsNone(
            derive_points_from_components(
                {"fieldGoals": (10, 50), "threePointers": (12, 45), "freeThrows": (5, 6)}
            )
        )


class EspnSummaryTests(unittest.TestCase):
    def test_components_are_read_from_the_provider_payload(self) -> None:
        sides = espn_team_components(fixture())
        self.assertEqual(sides["away"]["team"], "CLE")
        self.assertEqual(sides["away"]["components"]["fieldGoals"], (52, 110))
        self.assertEqual(sides["home"]["components"]["freeThrows"], (18, 23))

    def test_matching_final_is_consistent_and_still_labelled_a_candidate_rate(self) -> None:
        check = espn_consistency_checks(
            fixture(),
            {"away": 148, "home": 115},
            source_url="https://site.api.espn.com/apis/site/v2/sports/basketball/nba/summary?event=401809511",
            game_id="401809511",
        )
        self.assertEqual(check["status"], "consistent")
        self.assertEqual(check["assessment"], "candidate_requires_review")
        self.assertEqual(check["checks"][0]["derived_points"], 148)
        self.assertEqual(check["checks"][1]["derived_points"], 115)
        self.assertIn("cannot detect an error the provider propagated consistently", check["note"])

    def test_scoreboard_that_disagrees_with_its_own_box_score_is_flagged(self) -> None:
        payload = fixture()
        # Constructed variant for the test: Washington's made free throws reduced
        # by one, which is what a "made free throw recorded as a miss" error looks
        # like inside a provider's own numbers. This is a test input, not a claim
        # that ESPN ever published 114 for this game.
        payload["boxscore"]["teams"][1]["statistics"][3]["displayValue"] = "17-23"
        check = espn_consistency_checks(
            payload,
            {"away": 148, "home": 115},
            source_url="https://example.invalid/summary",
            game_id="401809511",
        )
        self.assertEqual(check["status"], "inconsistent")
        self.assertEqual(check["differences"][0]["side"], "home")
        self.assertEqual(check["differences"][0]["derived_points"], 114)
        self.assertEqual(check["differences"][0]["provider_reported_final"], 115)
        self.assertEqual(check["differences"][0]["difference"], -1)
        self.assertIn("does not establish which value", check["note"])

    def test_a_consistently_propagated_error_is_a_documented_blind_spot(self) -> None:
        # This test exists to keep the limitation honest: when a provider's
        # scoreboard and its own box score are wrong in the same direction, this
        # check reports "consistent" and cannot catch it.
        payload = fixture()
        payload["boxscore"]["teams"][1]["statistics"][3]["displayValue"] = "17-23"
        check = espn_consistency_checks(
            payload,
            {"away": 148, "home": 114},
            source_url="https://example.invalid/summary",
            game_id="401809511",
        )
        self.assertEqual(check["status"], "consistent")
        self.assertEqual(check["checks"][1]["derived_points"], 114)
        self.assertIn("propagated consistently", check["note"])

    def test_missing_components_return_not_checkable_instead_of_a_guess(self) -> None:
        payload = {"boxscore": {"teams": [{"homeAway": "home", "statistics": []}]}}
        check = espn_consistency_checks(
            payload, {"away": 100, "home": 100}, source_url="https://example.invalid", game_id="1"
        )
        self.assertEqual(check["status"], "not_checkable")
        self.assertIn("not evidence that the numbers are consistent", check["note"])

    def test_missing_scoreboard_value_returns_not_checkable(self) -> None:
        check = espn_consistency_checks(
            fixture(), {"away": None, "home": 115}, source_url="https://example.invalid", game_id="1"
        )
        self.assertEqual(check["status"], "not_checkable")
        self.assertIn("did not publish both final scores", check["reason"])

    def test_no_boxscore_section_returns_not_checkable(self) -> None:
        check = espn_consistency_checks(
            {}, {"away": 90, "home": 91}, source_url="https://example.invalid", game_id="1"
        )
        self.assertEqual(check["status"], "not_checkable")
        self.assertIn("boxscore.teams", check["reason"])


if __name__ == "__main__":
    unittest.main()
