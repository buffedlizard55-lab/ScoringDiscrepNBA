from __future__ import annotations

import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import validate_data  # noqa: E402


class ResearchDataTests(unittest.TestCase):
    def test_curated_database_passes_integrity_validation(self):
        self.assertEqual(validate_data.validate(ROOT), [])

    def test_only_two_confirmed_records_and_population_statistics_remain_unknown(self):
        data = json.loads((ROOT / "data/cases.json").read_text(encoding="utf-8"))
        self.assertEqual(len(data["cases"]), 2)
        self.assertEqual(data["coverage"]["confirmedCaseCount"], 2)
        self.assertIsNone(data["coverage"]["populationDenominator"])
        self.assertIsNone(data["coverage"]["populationRate"])
        self.assertIsNone(data["coverage"]["durationStatistic"])
        self.assertTrue(all(case["correctionType"] == "made_free_throw_recorded_missed" for case in data["cases"]))

    def test_kpj_and_213_214_leads_are_unverified_and_excluded(self):
        leads = json.loads((ROOT / "data/leads.json").read_text(encoding="utf-8"))["leads"]
        self.assertEqual({lead["id"] for lead in leads}, {
            "unidentified-213-vs-214-final-score",
            "kevin-porter-jr-2021-10-22-stat-correction",
        })
        for lead in leads:
            self.assertEqual(lead["status"], "unverified_lead")
            self.assertFalse(lead["includeInConfirmedStatistics"])
            self.assertIsNone(lead["game"])

    def test_terminal_candidate_requires_matching_review_state_and_citations(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            shutil.copytree(ROOT / "data", root / "data")
            candidate = {
                "id": "fixture-candidate",
                "nbaGameId": "fixture-game",
                "monitorStatus": "feed_converged",
                "investigationStatus": "closed_unresolved",
                "reviewStatus": "reviewed_unresolved",
                "reviewer": "Fixture reviewer",
                "reviewedAt": "2026-10-07T00:00:00Z",
                "resolution": "Reviewed; available sources did not establish which feed was first correct.",
                "resolutionSourceIds": ["nba-live-scoreboard-feed"],
            }
            path = root / "data/monitor/candidates.json"
            path.write_text(json.dumps({"schemaVersion": 1, "candidates": [candidate]}, indent=2), encoding="utf-8")
            self.assertEqual(validate_data.validate(root), [])

            candidate["reviewStatus"] = "unverified"
            path.write_text(json.dumps({"schemaVersion": 1, "candidates": [candidate]}, indent=2), encoding="utf-8")
            errors = validate_data.validate(root)
            self.assertTrue(any("requires reviewStatus reviewed_unresolved" in error for error in errors))


if __name__ == "__main__":
    unittest.main()
