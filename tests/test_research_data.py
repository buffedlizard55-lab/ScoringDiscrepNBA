from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class ResearchDataTests(unittest.TestCase):
    def test_canonical_validator_passes(self):
        result = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "validate.py")],
            cwd=ROOT, text=True, capture_output=True, check=False,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_unverified_leads_are_visible_but_excluded_from_confirmed_statistics(self):
        cases = json.loads((ROOT / "data/cases.json").read_text(encoding="utf-8"))["cases"]
        stats = json.loads((ROOT / "data/stats.json").read_text(encoding="utf-8"))
        by_id = {case["id"]: case for case in cases}
        expected_leads = {
            "0000-00-00-originating-213-vs-214-report",
            "0000-00-00-kpj-player-stat-correction-lead",
        }
        self.assertTrue(expected_leads.issubset(by_id))
        for case_id in expected_leads:
            case = by_id[case_id]
            self.assertEqual(case["status"], "unverified")
            self.assertEqual(case["verification_level"], "unverified-report")
            self.assertIsNone(case["game_date"])
            self.assertEqual(case["classification"]["layer"], "unresolved")
            self.assertEqual(case["official_record_was_wrong"], "undetermined")
            self.assertTrue(case["open_questions"])
        self.assertEqual(stats["verified_count"], 12)
        self.assertEqual(stats["status_counts"]["unverified"], 2)
        self.assertEqual(stats["collection_size"], 14)
        self.assertNotIn("0000-00-00-kpj-player-stat-correction-lead", stats["final_score_changed_ids"])
        self.assertNotIn("0000-00-00-originating-213-vs-214-report", stats["one_point_total_change_ids"])

    def test_legacy_numeric_statistics_are_superseded_and_both_leads_excluded(self):
        legacy = json.loads((ROOT / "data/statistics.json").read_text(encoding="utf-8"))
        self.assertEqual(legacy["status"], "superseded-audit-flagged")
        self.assertEqual(legacy["superseded_by"], "data/stats.json")
        excluded = set(legacy["unverified_leads_excluded"])
        self.assertIn("0000-00-00-originating-213-vs-214-report", excluded)
        self.assertIn("0000-00-00-kpj-player-stat-correction-lead", excluded)
        self.assertNotIn("verified_count", legacy)
        self.assertNotIn("verification_rate", legacy)

    def test_kpj_lead_does_not_repeat_unverified_legacy_claims(self):
        legacy = json.loads((ROOT / "data/discrepancies.json").read_text(encoding="utf-8"))
        record = next(item for item in legacy if item["id"] == "DISC-20211022-PORTER-STAT-001")
        self.assertEqual(record["verification_status"], "unverified")
        self.assertIsNone(record["date"])
        self.assertIsNone(record["game_id"])
        self.assertIsNone(record["original_value"]["player_stat"])
        self.assertIsNone(record["corrected_value"]["player_stat"])
        self.assertIsNone(record["nba_official_record_incorrect"])
        self.assertEqual(record["investigation_status"], "investigating")

    def test_primary_correction_sources_are_present_in_case_records(self):
        cases = json.loads((ROOT / "data/cases.json").read_text(encoding="utf-8"))["cases"]
        by_id = {case["id"]: case for case in cases}
        warriors_urls = {s["url"] for s in by_id["2024-10-23-gsw-por-melton-ft"]["sources"]}
        cavs_urls = {s["url"] for s in by_id["2025-11-07-cle-was-johnson-ft"]["sources"]}
        self.assertIn("https://www.nbcsportsbayarea.com/nba/golden-state-warriors/nba-error-score-change-trail-blazers/1797765/", warriors_urls)
        self.assertIn("https://x.com/NBAOfficial/status/1987199646020870516", cavs_urls)
        self.assertEqual(by_id["2025-11-07-cle-was-johnson-ft"]["verification_level"], "official-nba-confirmed")
        self.assertIn("arithmetic-derived", by_id["2024-10-23-gsw-por-melton-ft"]["score_after_play"])
        self.assertIn("no live-feed observation", by_id["2025-11-07-cle-was-johnson-ft"]["score_after_play"])


    def test_stats_have_explicit_collection_only_caveat_and_denominators(self):
        stats = json.loads((ROOT / "data/stats.json").read_text(encoding="utf-8"))
        self.assertIn("collection", stats["scope_caveat"].lower())
        self.assertEqual(stats["verified_count"], sum(stats["verified_type_counts"].values()))
        self.assertEqual(stats["collection_size"], sum(stats["status_counts"].values()))
        self.assertEqual(stats["fully_verified_count"], 0)
        self.assertEqual(stats["verified_partial_count"], 12)
        self.assertIn("not a count of fully verified cases", stats["verified_count_scope"])


if __name__ == "__main__":
    unittest.main()
