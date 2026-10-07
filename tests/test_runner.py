from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from monitor.runner import run_with_payloads
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

    def test_failed_feed_keeps_empty_result_explicitly_degraded(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            state, feed = run_with_payloads(
                None,
                read_fixture("espn-scoreboard.json"),
                root=directory,
                observed_at="2026-10-07T04:00:00Z",
                source_errors={"nba": "network unavailable"},
            )
            self.assertEqual(feed["status"], "degraded")
            self.assertEqual(feed["games"], [])
            self.assertEqual(feed["source_health"]["nba"]["status"], "unavailable")
            self.assertEqual(state["investigations"], [])
            self.assertIn("not evidence", feed["note"])

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
