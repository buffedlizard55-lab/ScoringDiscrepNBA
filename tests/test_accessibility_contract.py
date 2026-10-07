from __future__ import annotations

import re
import unittest
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class MarkupContract(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.ids: set[str] = set()
        self.duplicates: set[str] = set()
        self.local_links: list[str] = []
        self.labelled_by: list[str] = []
        self.controls: list[tuple[str, str | None, bool, bool]] = []
        self.label_depth = 0
        self.summary_count = 0
        self.skip_link_found = False

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        if tag == "label":
            self.label_depth += 1
        element_id = attributes.get("id")
        if element_id:
            if element_id in self.ids:
                self.duplicates.add(element_id)
            self.ids.add(element_id)
        if tag == "a" and (attributes.get("href") or "").startswith("#"):
            self.local_links.append(attributes["href"][1:])
            if attributes.get("class") == "skip-link":
                self.skip_link_found = True
        if attributes.get("aria-labelledby"):
            self.labelled_by.extend(attributes["aria-labelledby"].split())
        if tag in {"input", "select", "textarea", "button"}:
            has_native_label = self.label_depth > 0 or bool(attributes.get("aria-label")) or bool(attributes.get("aria-labelledby"))
            self.controls.append((tag, attributes.get("id"), has_native_label, bool(attributes.get("type") == "hidden")))
        if tag == "summary":
            self.summary_count += 1

    def handle_endtag(self, tag):
        if tag == "label" and self.label_depth:
            self.label_depth -= 1


class AccessibilityContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html = (ROOT / "index.html").read_text(encoding="utf-8")
        cls.parser = MarkupContract()
        cls.parser.feed(cls.html)

    def test_ids_and_internal_anchors_resolve(self):
        self.assertFalse(self.parser.duplicates, f"duplicate IDs: {self.parser.duplicates}")
        missing_links = set(self.parser.local_links) - self.parser.ids
        self.assertFalse(missing_links, f"unresolved local links: {missing_links}")
        missing_labels = set(self.parser.labelled_by) - self.parser.ids
        self.assertFalse(missing_labels, f"unresolved aria-labelledby references: {missing_labels}")

    def test_interactive_controls_have_accessible_labels_and_details(self):
        unlabeled = [tag for tag, element_id, labelled, hidden in self.parser.controls if not labelled and not hidden]
        self.assertEqual(unlabeled, [])
        self.assertTrue(self.parser.skip_link_found, "a keyboard skip link should be present")
        javascript = (ROOT / "app.js").read_text(encoding="utf-8")
        self.assertIn('node("summary"', javascript, "case evidence uses native disclosure widgets")

    def test_javascript_selectors_have_static_targets(self):
        javascript = (ROOT / "app.js").read_text(encoding="utf-8")
        selectors = set(re.findall(r'el\("#([A-Za-z0-9_-]+)"\)', javascript))
        missing = selectors - self.parser.ids
        self.assertFalse(missing, f"JavaScript targets without HTML IDs: {missing}")


if __name__ == "__main__":
    unittest.main()
