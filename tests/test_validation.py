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

    def test_missing_data_file_is_reported(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(DataValidationError):
                validate_repository_data(directory)


if __name__ == "__main__":
    unittest.main()
