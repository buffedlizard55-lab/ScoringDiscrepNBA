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
        self.skip_link_found = False
        self.document_language: str | None = None

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        if tag == "html":
            self.document_language = attributes.get("lang")
        if tag == "label":
            self.label_depth += 1
        element_id = attributes.get("id")
        if element_id:
            if element_id in self.ids:
                self.duplicates.add(element_id)
            self.ids.add(element_id)
        if tag == "a" and (attributes.get("href") or "").startswith("#"):
            self.local_links.append(attributes["href"][1:])
            if "skip-link" in (attributes.get("class") or "").split():
                self.skip_link_found = True
        if attributes.get("aria-labelledby"):
            self.labelled_by.extend(attributes["aria-labelledby"].split())
        if tag in {"input", "select", "textarea", "button"}:
            has_native_label = (
                self.label_depth > 0
                or bool(attributes.get("aria-label"))
                or bool(attributes.get("aria-labelledby"))
            )
            self.controls.append((tag, attributes.get("id"), has_native_label, attributes.get("type") == "hidden"))

    def handle_endtag(self, tag):
        if tag == "label" and self.label_depth:
            self.label_depth -= 1


class AccessibilityContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html = (ROOT / "docs/index.html").read_text(encoding="utf-8")
        cls.javascript = (ROOT / "docs/app.js").read_text(encoding="utf-8")
        cls.parser = MarkupContract()
        cls.parser.feed(cls.html)

    def test_document_language_skip_link_and_internal_references(self):
        self.assertEqual(self.parser.document_language, "en")
        self.assertTrue(self.parser.skip_link_found, "keyboard users need a skip-to-main-content link")
        self.assertFalse(self.parser.duplicates, f"duplicate IDs: {self.parser.duplicates}")
        missing_links = set(self.parser.local_links) - self.parser.ids
        self.assertFalse(missing_links, f"unresolved local links: {missing_links}")
        missing_labels = set(self.parser.labelled_by) - self.parser.ids
        self.assertFalse(missing_labels, f"unresolved aria-labelledby references: {missing_labels}")
        self.assertIn('id="main-content"', self.html)

    def test_search_and_filter_controls_have_accessible_names(self):
        unlabeled = [tag for tag, _element_id, labelled, hidden in self.parser.controls if not labelled and not hidden]
        self.assertEqual(unlabeled, [])
        self.assertIn('aria-live="polite"', self.html)
        self.assertIn('aria-label="Case evidence details"', self.html)

    def test_dynamic_case_cards_support_keyboard_and_dialog_focus(self):
        self.assertIn('e.key === "Enter" || e.key === " "', self.javascript)
        self.assertIn('closeButton.focus()', self.javascript)
        self.assertIn('LAST_FOCUSED_CARD.focus()', self.javascript)
        self.assertIn('e.key !== "Tab"', self.javascript)
        selectors = set(re.findall(r'el\("([A-Za-z0-9_-]+)"\)', self.javascript))
        dynamic_targets = {"detail-close", "clear-filters"}
        missing = selectors - self.parser.ids - dynamic_targets
        self.assertFalse(missing, f"JavaScript targets without HTML IDs: {missing}")

    def test_site_links_to_review_workflow_and_source_data(self):
        self.assertIn('href="INVESTIGATION_WORKFLOW.md"', self.html)
        for payload in ("data/cases.json", "data/stats.json", "data/investigations.json"):
            self.assertIn(payload, self.html)
        self.assertIn('rel="noopener"', self.javascript)


class RootDashboardAccessibilityContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html = (ROOT / "index.html").read_text(encoding="utf-8")
        cls.javascript = (ROOT / "assets/app.js").read_text(encoding="utf-8")
        cls.parser = MarkupContract()
        cls.parser.feed(cls.html)

    def test_root_dashboard_has_language_skip_link_and_valid_references(self):
        self.assertEqual(self.parser.document_language, "en")
        self.assertTrue(self.parser.skip_link_found)
        self.assertFalse(self.parser.duplicates, f"duplicate root IDs: {self.parser.duplicates}")
        self.assertIn("main", self.parser.ids)
        self.assertEqual(set(self.parser.local_links) - self.parser.ids, set())
        self.assertEqual(set(self.parser.labelled_by) - self.parser.ids, set())

    def test_root_filter_controls_have_names_and_live_regions(self):
        unlabeled = [tag for tag, _element_id, labelled, hidden in self.parser.controls if not labelled and not hidden]
        self.assertEqual(unlabeled, [])
        self.assertIn('aria-live="polite"', self.html)
        self.assertIn('id="leadList"', self.html)
        self.assertIn("Excluded from confirmed-case metrics", self.html)

    def test_dynamic_root_rendering_escapes_text_and_limits_external_links(self):
        self.assertIn('const escapeHtml', self.javascript)
        self.assertIn('const safeExternalUrl', self.javascript)
        self.assertIn('rel="noopener noreferrer"', self.javascript)
        self.assertIn('data/leads.json', self.javascript)



if __name__ == "__main__":
    unittest.main()
