from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from monitor.runner import _feed_material_signature, run_with_payloads
from monitor.validation import DataValidationError

FIXTURES = Path(__file__).parent / "fixtures"


def read_fixture(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def espn_with_home_score(score: str) -> dict:
    payload = read_fixture("espn-scoreboard.json")
    payload["events"][0]["competitions"][0]["competitors"][1]["score"] = score
    return payload


class RunnerTests(unittest.TestCase):
    def test_fixture_cycle_creates_persistent_candidate_with_pbp_context(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            state, feed = run_with_payloads(
                read_fixture("nba-scoreboard.json"),
                read_fixture("espn-scoreboard.json"),
                root=directory,
                observed_at="2026-10-07T04:00:00Z",
                nba_hash="a" * 64,
                espn_hash="b" * 64,
                pbp_payloads={"0022500029": read_fixture("nba-pbp.json")},
                response_metadata={
                    "nba": {"sha256": "a" * 64, "etag": "nba-tag", "last_modified": "Wed, 07 Oct 2026 04:00:00 GMT"},
                    "espn": {"sha256": "b" * 64, "etag": "espn-tag", "last_modified": None},
                },
                pbp_metadata={
                    "0022500029": {"sha256": "c" * 64, "etag": "pbp-tag", "last_modified": None}
                },
            )
            self.assertEqual(feed["status"], "healthy")
            self.assertEqual(feed["games"][0]["score_mismatch"], True)
            self.assertEqual(feed["games"][0]["latest_official_scoring_play"]["player"], "Tre Johnson")
            self.assertEqual(state["investigations"][0]["status"], "detected")
            self.assertEqual(state["investigations"][0]["verification_status"], "unverified")
            first_observation = state["investigations"][0]["first_observation"]
            self.assertEqual(first_observation["source_metadata"]["nba"]["last_modified"], "Wed, 07 Oct 2026 04:00:00 GMT")
            self.assertEqual(first_observation["source_metadata"]["nba_pbp"]["etag"], "pbp-tag")
            self.assertEqual(first_observation["source_hashes"]["nba_pbp"], "c" * 64)
            saved_state = json.loads((Path(directory) / "data/monitor-state.json").read_text())
            saved_feed = json.loads((Path(directory) / "data/live-feed.json").read_text())
            self.assertEqual(saved_state["investigations"][0]["observation_count"], 1)
            self.assertEqual(saved_feed["last_updated_at"], "2026-10-07T04:00:00Z")

    def test_repeated_poll_updates_mismatch_then_closes_after_two_agreements(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            nba = read_fixture("nba-scoreboard.json")
            mismatch = read_fixture("espn-scoreboard.json")
            matched = espn_with_home_score("39")
            state, _ = run_with_payloads(nba, mismatch, root=directory, observed_at="2026-10-07T04:00:00Z")
            state, _ = run_with_payloads(nba, matched, root=directory, observed_at="2026-10-07T04:05:00Z")
            state, feed = run_with_payloads(nba, matched, root=directory, observed_at="2026-10-07T04:10:00Z")
            self.assertEqual(state["investigations"][0]["status"], "resolved")
            self.assertEqual(feed["active_investigation_count"], 0)
            self.assertIn("does not establish", state["investigations"][0]["resolution"]["note"])

    def test_failed_primary_feed_still_publishes_the_reachable_source(self) -> None:
        """A down primary feed must not blank out the games another source published.

        The scheduled runner's NBA CDN feed has been returning HTTP errors, and the
        earlier design built every row from that one feed, so a perfectly reachable
        ESPN feed produced ``games: []`` and the single-provider arithmetic checks
        had no row to attach to. This test locks in the corrected behaviour: the
        reachable source is published, marked as not compared, and the snapshot
        says which source is missing.
        """
        with tempfile.TemporaryDirectory() as directory:
            state, feed = run_with_payloads(
                None,
                read_fixture("espn-scoreboard.json"),
                root=directory,
                observed_at="2026-10-07T04:00:00Z",
                source_errors={"nba": "network unavailable"},
            )
            self.assertEqual(feed["status"], "degraded")
            self.assertEqual(len(feed["games"]), 1)
            game = feed["games"][0]
            self.assertEqual(game["scores"]["espn"]["away"], 50)
            self.assertNotIn("nba", game["scores"])
            self.assertIsNone(game["score_mismatch"])
            self.assertEqual(feed["source_health"]["nba"]["status"], "unavailable")
            self.assertEqual(state["investigations"], [])
            self.assertIn("Not compared", feed["note"])
            self.assertIn("nba", feed["note"])
            self.assertIn("arithmetic", feed["note"])

    def test_single_provider_arithmetic_check_runs_while_nba_feed_is_down(self) -> None:
        """The one-provider detector is the reason this project is not blind today.

        With the NBA CDN feed unavailable, ESPN's own box score still lets the
        monitor notice a final that does not follow from the provider's published
        components. The fixture pairs the ESPN scoreboard final with the archived
        summary box score, so the two providers' numbers intentionally disagree:
        the assertion is about the mechanism firing, not about a real game.
        """
        with tempfile.TemporaryDirectory() as directory:
            espn = read_fixture("espn-scoreboard.json")
            for competitor in espn["events"][0]["competitions"][0]["competitors"]:
                competitor["score"] = "115" if competitor["homeAway"] == "away" else "114"
            espn["events"][0]["status"]["type"] = {"state": "post", "completed": True}
            espn["events"][0]["status"]["period"] = 4
            state, feed = run_with_payloads(
                None,
                espn,
                root=directory,
                observed_at="2026-10-07T04:00:00Z",
                source_errors={"nba": "HTTP 500"},
                summary_payloads={"espn:401809511": read_fixture("espn-summary-401809511.json")},
            )
            checks = state["final_game_checks"]
            self.assertEqual(len(checks), 1)
            record = next(iter(checks.values()))
            self.assertEqual(record["source_key"], "espn")
            self.assertEqual(record["status"], "inconsistent")
            derived = {entry["side"]: entry["derived_points"] for entry in record["derived"]}
            self.assertEqual(derived["away"], 148)
            self.assertEqual(derived["home"], 115)
            self.assertEqual(len(state["investigations"]), 1)
            investigation = state["investigations"][0]
            self.assertEqual(investigation["detection_type"], "final_score_internal_inconsistency")
            self.assertEqual(investigation["source_key"], "espn")
            self.assertEqual(investigation["verification_status"], "unverified")
            self.assertEqual(feed["active_investigation_count"], 1)
            self.assertEqual(
                feed["detector_status"]["cross_source_comparison_available"], False
            )

    def test_malformed_existing_feed_snapshot_is_not_overwritten(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            feed_path = Path(directory) / "data/live-feed.json"
            feed_path.parent.mkdir(parents=True)
            feed_path.write_text("{broken", encoding="utf-8")
            with self.assertRaises(DataValidationError):
                run_with_payloads(
                    read_fixture("nba-scoreboard.json"),
                    read_fixture("espn-scoreboard.json"),
                    root=directory,
                    observed_at="2026-10-07T04:00:00Z",
                )
            self.assertEqual(feed_path.read_text(encoding="utf-8"), "{broken")
            self.assertFalse((Path(directory) / "data/monitor-state.json").exists())

    def test_note_wording_is_part_of_the_material_signature(self) -> None:
        """A changed explanation must be published, not frozen behind a stable game list.

        The note is where the snapshot says which sources answered and what was
        left un-compared. If it were excluded from the material signature, a
        reader could keep seeing an explanation that no longer matches the data
        (for example the pre-union wording "the last saved snapshot" after the
        monitor started publishing a reachable source again).
        """
        base = {
            "status": "degraded",
            "source_health": {"nba": {"status": "unavailable"}, "espn": {"status": "ok"}},
            "games": [],
            "last_state_change_at": "2026-10-07T04:00:00Z",
            "source_diagnostics": {"nba": [{"profile": "monitor", "outcome": "failed"}]},
            "detector_status": {"cross_source_comparison_available": False},
            "note": "Older explanation.",
        }
        same = dict(base)
        changed = dict(base, note="New explanation of the same data.")
        self.assertEqual(_feed_material_signature(same), _feed_material_signature(base))
        self.assertNotEqual(_feed_material_signature(changed), _feed_material_signature(base))

    def test_unchanged_healthy_poll_keeps_published_snapshot_timestamp(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            nba = read_fixture("nba-scoreboard.json")
            espn = espn_with_home_score("39")
            _, first_feed = run_with_payloads(nba, espn, root=directory, observed_at="2026-10-07T04:00:00Z")
            _, second_feed = run_with_payloads(nba, espn, root=directory, observed_at="2026-10-07T04:05:00Z")
            self.assertEqual(first_feed["last_updated_at"], second_feed["last_updated_at"])
            self.assertEqual(first_feed["games"][0]["observed_at"], second_feed["games"][0]["observed_at"])


if __name__ == "__main__":
    unittest.main()

class FinalGameConsistencyTests(unittest.TestCase):
    """Single-provider arithmetic checks integrated with the runner.

    Uses the real ESPN summary excerpt for event 401809511 (CLE @ WAS,
    2025-11-07) plus a constructed one-free-throw-lower variant, which is what a
    "made free throw recorded as a miss" error looks like inside one provider's
    own numbers.
    """

    def final_espn_scoreboard(self) -> dict:
        payload = read_fixture("espn-scoreboard.json")
        event = payload["events"][0]
        event["status"]["type"] = {"state": "post", "shortDetail": "Final"}
        event["status"]["period"] = 4
        competitors = event["competitions"][0]["competitors"]
        scores = {"away": "148", "home": "115"}
        for competitor in competitors:
            competitor["score"] = scores[competitor["homeAway"]]
        return payload

    def final_nba_scoreboard(self) -> dict:
        payload = read_fixture("nba-scoreboard.json")
        game = payload["scoreboard"]["games"][0]
        game["gameStatus"] = 3
        game["gameStatusText"] = "Final"
        game["period"] = 4
        game["awayTeam"]["score"] = 148
        game["homeTeam"]["score"] = 115
        return payload

    def test_failed_summary_fetch_is_not_treated_as_a_payload(self):
        with tempfile.TemporaryDirectory() as directory:
            state, _ = run_with_payloads(
                self.final_nba_scoreboard(), self.final_espn_scoreboard(),
                root=directory, observed_at="2026-10-07T04:00:00Z",
                summary_payloads={"espn:401809511": None})
            self.assertEqual(state["final_game_checks"], {})

    def test_summary_recheck_uses_provider_id_for_joined_record(self):
        from monitor.runner import _due_for_summary_check
        with tempfile.TemporaryDirectory() as directory:
            state, _ = run_with_payloads(
                self.final_nba_scoreboard(), self.final_espn_scoreboard(),
                root=directory, observed_at="2026-10-07T04:00:00Z",
                summary_payloads={"espn:401809511": read_fixture("espn-summary-401809511.json")})
            self.assertFalse(_due_for_summary_check(
                state, "espn", "401809511", {"away": 148, "home": 115}, "2026-10-07T04:05:00Z"))
            self.assertTrue(_due_for_summary_check(
                state, "espn", "401809511", {"away": 148, "home": 116}, "2026-10-07T04:05:00Z"))

    def test_consistent_final_is_recorded_without_creating_an_investigation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            state, _ = run_with_payloads(
                self.final_nba_scoreboard(),
                self.final_espn_scoreboard(),
                root=directory,
                observed_at="2026-10-07T04:00:00Z",
                summary_payloads={"espn:401809511": read_fixture("espn-summary-401809511.json")},
            )
            self.assertEqual(state["investigations"], [])
            # The check is stored against the joined game identity (the primary
            # feed's game id), not the provider's own event id.
            record = state["final_game_checks"]["espn:0022500029"]
            self.assertEqual(record["status"], "consistent")
            self.assertEqual({entry["derived_points"] for entry in record["derived"]}, {148, 115})

    def test_one_point_box_score_conflict_creates_a_critical_alert_record(self) -> None:
        summary = read_fixture("espn-summary-401809511.json")
        summary["boxscore"]["teams"][1]["statistics"][3]["displayValue"] = "17-23"
        with tempfile.TemporaryDirectory() as directory:
            state, feed = run_with_payloads(
                self.final_nba_scoreboard(),
                self.final_espn_scoreboard(),
                root=directory,
                observed_at="2026-10-07T04:00:00Z",
                summary_payloads={"espn:401809511": summary},
            )
            investigations = [
                item
                for item in state["investigations"]
                if item["detection_type"] == "final_score_internal_inconsistency"
            ]
            self.assertEqual(len(investigations), 1)
            self.assertEqual(investigations[0]["source_key"], "espn")
            self.assertEqual(investigations[0]["status"], "detected")
            book = json.loads((Path(directory) / "data/alerts.json").read_text())
            self.assertEqual(book["counts"]["open"], 1)
            alert = book["alerts"][0]
            self.assertEqual(alert["severity"], "critical")
            self.assertEqual(alert["type"], "final_score_internal_inconsistency")
            home_check = next(entry for entry in alert["arithmetic"] if entry["side"] == "home")
            self.assertEqual(home_check["derived_points"], 114)
            self.assertEqual(home_check["provider_reported_final"], 115)
            self.assertEqual(home_check["difference"], -1)
            away_check = next(entry for entry in alert["arithmetic"] if entry["side"] == "away")
            self.assertEqual(away_check["difference"], 0)
            self.assertEqual(feed["detector_status"]["final_game_checks_recorded"], 1)

    def test_source_diagnostics_are_published_without_request_timings(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            _, feed = run_with_payloads(
                read_fixture("nba-scoreboard.json"),
                read_fixture("espn-scoreboard.json"),
                root=directory,
                observed_at="2026-10-07T04:00:00Z",
                source_diagnostics={
                    "nba": [
                        {"profile": "monitor", "outcome": "failed", "error": "HTTP 403", "duration_ms": 812},
                        {"profile": "browser", "outcome": "failed", "error": "HTTP 403", "duration_ms": 640},
                    ]
                },
            )
            attempts = feed["source_diagnostics"]["nba"]
            self.assertEqual([attempt["profile"] for attempt in attempts], ["monitor", "browser"])
            self.assertTrue(all("duration_ms" not in attempt for attempt in attempts))
            self.assertIn("HTTP 403", attempts[0]["error"])


if __name__ == "__main__":
    unittest.main()
