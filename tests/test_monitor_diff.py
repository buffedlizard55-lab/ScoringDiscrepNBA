from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from scripts.monitor_diff import has_material_changes


class MaterialMonitorDiffTests(unittest.TestCase):
    def make_repository(self, root: Path) -> tuple[dict, dict]:
        feed = {
            "status": "healthy",
            "last_updated_at": "2026-10-07T04:00:00Z",
            "last_poll_attempt_at": "2026-10-07T04:00:00Z",
            "last_successful_comparison_at": "2026-10-07T04:00:00Z",
            "games": [
                {
                    "game_id": "0022600001",
                    "status": "live",
                    "period": 2,
                    "clock": "PT08M15.00S",
                    "status_text": "Q2",
                    "observed_at": "2026-10-07T04:00:00Z",
                    "score_mismatch": False,
                    "scores": {"nba": {"away": 50, "home": 39}, "espn": {"away": 50, "home": 39}},
                    "latest_official_scoring_play": None,
                    "play_by_play_source_url": None,
                }
            ],
        }
        state = {"last_state_change_at": None, "investigations": [], "source_health": {}}
        for relative, value in (
            ("data/live-feed.json", feed),
            ("data/monitor-state.json", state),
        ):
            path = root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(value), encoding="utf-8")
        subprocess.run(["git", "init", "-q", str(root)], check=True)
        subprocess.run(["git", "-C", str(root), "config", "user.name", "Fixture"], check=True)
        subprocess.run(["git", "-C", str(root), "config", "user.email", "fixture@example.invalid"], check=True)
        subprocess.run(["git", "-C", str(root), "add", "data"], check=True)
        subprocess.run(["git", "-C", str(root), "commit", "-qm", "fixture baseline"], check=True)
        return feed, state

    def test_heartbeat_and_clock_updates_do_not_create_repository_commits(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            feed, _ = self.make_repository(root)
            feed["last_poll_attempt_at"] = "2026-10-07T04:05:00Z"
            feed["last_successful_comparison_at"] = "2026-10-07T04:05:00Z"
            feed["games"][0]["observed_at"] = "2026-10-07T04:05:00Z"
            feed["games"][0]["clock"] = "PT08M10.00S"
            feed["games"][0]["status_text"] = "Q2 8:10"
            (root / "data/live-feed.json").write_text(json.dumps(feed), encoding="utf-8")

            self.assertFalse(has_material_changes(root))

    def test_score_health_or_lifecycle_change_is_persisted(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            feed, state = self.make_repository(root)
            feed["games"][0]["scores"]["nba"]["away"] = 51
            (root / "data/live-feed.json").write_text(json.dumps(feed), encoding="utf-8")
            self.assertTrue(has_material_changes(root))

            subprocess.run(["git", "-C", str(root), "checkout", "--", "data/live-feed.json"], check=True)
            state["investigations"] = [{"id": "candidate-1", "status": "detected"}]
            (root / "data/monitor-state.json").write_text(json.dumps(state), encoding="utf-8")
            self.assertTrue(has_material_changes(root))


if __name__ == "__main__":
    unittest.main()
