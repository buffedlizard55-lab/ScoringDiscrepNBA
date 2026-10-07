from __future__ import annotations

import unittest

from monitor.engine import active_investigations, empty_state, update_state


HEALTHY = {
    "nba": {"status": "ok", "url": "https://nba.example/scoreboard"},
    "espn": {"status": "ok", "url": "https://espn.example/scoreboard"},
}


def observation(at: str, nba_away: int, nba_home: int, espn_away: int, espn_home: int, status: str = "live") -> dict:
    mismatch = nba_away != espn_away or nba_home != espn_home
    return {
        "observed_at": at,
        "game_id": "0022600001",
        "game_date": "2026-10-07",
        "status": status,
        "period": 2,
        "clock": "PT08M15.00S",
        "away_team": {"name": "Away Club", "abbreviation": "AAA"},
        "home_team": {"name": "Home Club", "abbreviation": "BBB"},
        "scores": {
            "nba": {"away": nba_away, "home": nba_home, "source_url": "https://nba.example/scoreboard"},
            "espn": {"away": espn_away, "home": espn_home, "source_url": "https://espn.example/scoreboard"},
        },
        "score_mismatch": mismatch,
        "source_hashes": {"nba": "abc", "espn": "def"},
        "latest_official_scoring_play": None,
        "play_by_play_source_url": None,
    }


class InvestigationLifecycleTests(unittest.TestCase):
    def test_mismatch_moves_detected_to_investigating_and_preserves_first_value(self) -> None:
        first = observation("2026-10-07T04:00:00Z", 50, 39, 50, 38)
        state = update_state(empty_state(), [first], first["observed_at"], HEALTHY)
        event = state["investigations"][0]
        self.assertEqual(event["status"], "detected")
        self.assertEqual(event["verification_status"], "unverified")
        self.assertEqual(event["first_observation"]["scores"]["nba"]["home"], 39)
        self.assertEqual(event["first_details"]["espn_score"]["home"], 38)

        second = observation("2026-10-07T04:05:00Z", 51, 39, 51, 38)
        state = update_state(state, [second], second["observed_at"], HEALTHY)
        event = state["investigations"][0]
        self.assertEqual(event["status"], "investigating")
        self.assertEqual(event["observation_count"], 2)
        self.assertEqual(event["first_observation"]["observed_at"], "2026-10-07T04:00:00Z")
        self.assertEqual(event["latest_observation"]["scores"]["nba"]["away"], 51)
        self.assertEqual(len(active_investigations(state)), 1)

    def test_feed_convergence_closes_only_the_observed_window(self) -> None:
        state = empty_state()
        mismatch = observation("2026-10-07T04:00:00Z", 50, 39, 50, 38)
        state = update_state(state, [mismatch], mismatch["observed_at"], HEALTHY)
        matched_1 = observation("2026-10-07T04:05:00Z", 51, 39, 51, 39)
        state = update_state(state, [matched_1], matched_1["observed_at"], HEALTHY)
        self.assertEqual(state["investigations"][0]["status"], "monitoring_for_convergence")
        matched_2 = observation("2026-10-07T04:10:00Z", 52, 39, 52, 39)
        state = update_state(state, [matched_2], matched_2["observed_at"], HEALTHY)
        event = state["investigations"][0]
        self.assertEqual(event["status"], "resolved")
        self.assertEqual(event["verification_status"], "unverified")
        self.assertEqual(event["resolution"]["type"], "feeds_converged")
        self.assertIn("does not establish", event["resolution"]["note"])
        self.assertEqual(active_investigations(state), [])

    def test_missing_secondary_score_does_not_resolve_open_discrepancy(self) -> None:
        state = empty_state()
        mismatch = observation("2026-10-07T04:00:00Z", 50, 39, 50, 38)
        state = update_state(state, [mismatch], mismatch["observed_at"], HEALTHY)
        unavailable = observation("2026-10-07T04:05:00Z", 51, 39, 51, 39)
        unavailable["scores"]["espn"]["home"] = None
        unavailable["score_mismatch"] = None
        state = update_state(state, [unavailable], unavailable["observed_at"], HEALTHY)
        self.assertEqual(state["investigations"][0]["status"], "detected")
        self.assertEqual(state["investigations"][0]["consecutive_agreements"], 0)

    def test_final_score_change_is_recorded_as_unverified_revision(self) -> None:
        first = observation("2026-10-07T04:00:00Z", 100, 99, 100, 99, status="final")
        state = update_state(empty_state(), [first], first["observed_at"], HEALTHY)
        self.assertEqual(state["investigations"], [])
        self.assertIn("0022600001", state["final_score_baselines"])

        revised = observation("2026-10-07T04:05:00Z", 101, 99, 101, 99, status="final")
        state = update_state(state, [revised], revised["observed_at"], HEALTHY)
        self.assertEqual(len(state["investigations"]), 1)
        event = state["investigations"][0]
        self.assertEqual(event["detection_type"], "nba_final_feed_revision")
        self.assertEqual(event["status"], "change_observed_unverified")
        self.assertIn("not by itself proof", event["first_details"]["warning"])
        self.assertEqual(event["verification_status"], "unverified")
        self.assertEqual(event["previous_nba_feed_score"], {"away": 100, "home": 99})
        self.assertEqual(event["current_nba_feed_score"], {"away": 101, "home": 99})
        self.assertEqual(event["change_interval"]["detected_at"], "2026-10-07T04:05:00Z")

        same = observation("2026-10-07T04:10:00Z", 101, 99, 101, 99, status="final")
        state = update_state(state, [same], same["observed_at"], HEALTHY)
        self.assertEqual(len(state["investigations"]), 1)
        self.assertEqual(state["investigations"][0]["status"], "change_observed_unverified")

    def test_no_games_or_unavailable_source_does_not_claim_success_or_resolution(self) -> None:
        state = update_state(
            empty_state(),
            [],
            "2026-10-07T04:00:00Z",
            {"nba": {"status": "unavailable"}, "espn": {"status": "ok"}},
        )
        self.assertEqual(state.get("last_state_change_at"), "2026-10-07T04:00:00Z")
        self.assertNotIn("last_successful_poll_at", state)
        self.assertEqual(state["investigations"], [])


if __name__ == "__main__":
    unittest.main()
