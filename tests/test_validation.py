from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from monitor.validation import DataValidationError, validate_repository_data

ROOT = Path(__file__).resolve().parents[1]


class RepositoryDataTests(unittest.TestCase):
    def test_checked_in_seed_data_has_source_links_and_consistent_totals(self) -> None:
        errors = validate_repository_data(ROOT)
        self.assertEqual(errors, [])

    def test_schema_file_is_valid_json(self) -> None:
        schema = json.loads((ROOT / "schemas" / "case.schema.json").read_text(encoding="utf-8"))
        self.assertEqual(schema["$schema"], "https://json-schema.org/draft/2020-12/schema")
        self.assertIn("scores", schema["properties"])
        self.assertIn("sources", schema["properties"])

    def test_unverified_research_leads_are_explicit_and_excluded(self) -> None:
        leads = json.loads((ROOT / "data" / "leads.json").read_text(encoding="utf-8"))["leads"]
        by_id = {lead["id"]: lead for lead in leads}
        expected = {
            "unidentified-213-vs-214-final-total": "unidentified_unverified_lead",
            "unverified-2021-kevin-porter-jr-stat-correction": "unverified_lead",
        }
        self.assertTrue(set(expected).issubset(by_id))
        for lead_id, status in expected.items():
            self.assertEqual(by_id[lead_id]["status"], status)
            self.assertTrue(by_id[lead_id]["excluded_from_verified_statistics"])
            self.assertEqual(by_id[lead_id]["source_ids"], [])

    def test_melton_player_total_conflict_is_not_resolved_by_the_dashboard(self) -> None:
        cases = json.loads((ROOT / "data" / "reviewed-cases.json").read_text(encoding="utf-8"))["cases"]
        melton = next(case for case in cases if case["id"] == "nba-2024-10-23-gsw-por-free-throw-correction")
        impact = melton["impact"]["player_points"]
        self.assertEqual(impact["status"], "disputed_unresolved")
        self.assertEqual({entry["value"] for entry in impact["reported_values"]}, {11, 12})
        self.assertIn("NBA-verified value", impact["note"])

    def test_missing_data_file_is_reported(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(DataValidationError):
                validate_repository_data(directory)


if __name__ == "__main__":
    unittest.main()
