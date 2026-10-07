"""Tests for alert notification delivery.

The GitHub CLI is replaced with a stub script on disk, so the tests exercise
the real subprocess path (argument passing, body on stdin, URL parsing, failure
handling) without touching any repository.
"""

from __future__ import annotations

import json
import os
import stat
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

from monitor.dispatch import build_issue, dispatch_pending
from monitor.alerts import resolve_alert, update_book
from monitor.engine import empty_state, update_state

HEALTHY = {
    "nba": {"status": "ok", "url": "https://cdn.nba.com/example"},
    "espn": {"status": "ok", "url": "https://site.api.espn.com/example"},
}


def observation(at: str, nba: tuple[int, int], espn: tuple[int, int], status: str = "final") -> dict:
    return {
        "observed_at": at,
        "game_id": "0022600072",
        "game_date": "2026-10-07",
        "status": status,
        "period": 4,
        "clock": None,
        "away_team": {"name": "Golden State Warriors", "abbreviation": "GSW"},
        "home_team": {"name": "Portland Trail Blazers", "abbreviation": "POR"},
        "scores": {
            "nba": {"away": nba[0], "home": nba[1], "source_url": "https://cdn.nba.com/example"},
            "espn": {"away": espn[0], "home": espn[1], "source_url": "https://site.api.espn.com/example"},
        },
        "score_mismatch": nba != espn,
        "source_hashes": {"nba": "abc", "espn": "def"},
        "latest_official_scoring_play": None,
        "play_by_play_source_url": None,
    }


def feed_health() -> dict:
    return {"status": "healthy", "source_health": HEALTHY, "games": []}


def revision_book(root: Path) -> dict:
    first = observation("2026-10-07T04:00:00Z", (139, 104), (139, 104))
    state = update_state(empty_state(), [first], first["observed_at"], HEALTHY)
    revised = observation("2026-10-07T04:05:00Z", (140, 104), (140, 104))
    state = update_state(state, [revised], revised["observed_at"], HEALTHY)
    book, _ = update_book(None, state, feed_health(), revised["observed_at"])
    (root / "data").mkdir(parents=True, exist_ok=True)
    (root / "data" / "alerts.json").write_text(json.dumps(book, indent=2), encoding="utf-8")
    return book


def save_alert_book(root: Path, book: dict) -> None:
    (root / "data" / "alerts.json").write_text(json.dumps(book, indent=2), encoding="utf-8")


def gh_calls(root: Path) -> list[dict]:
    path = root / "gh-calls.jsonl"
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def write_stub_gh(
    directory: Path,
    *,
    fail: bool = False,
    url: str = "https://github.com/buffedlizard55-lab/ScoringDiscrepNBA/issues",
) -> Path:
    calls = directory / "gh-calls.jsonl"
    state_path = directory / "gh-issues.json"
    script = directory / "gh"
    template = r'''#!/usr/bin/env python3
import json
import pathlib
import re
import sys
calls_path = pathlib.Path(__CALLS__)
state_path = pathlib.Path(__STATE__)
base_url = __URL__.rstrip("/")
fail = __FAIL__
if fail:
    sys.stderr.write("gh: simulated failure\n")
    raise SystemExit(1)
args = sys.argv[1:]
stdin = sys.stdin.read()
with calls_path.open("a", encoding="utf-8") as handle:
    handle.write(json.dumps({"argv": args, "stdin": stdin}) + "\n")
state = json.loads(state_path.read_text()) if state_path.exists() else {"next_number": 41, "issues": {}}
def get_number(ref):
    match = re.search(r"(\d+)(?:$|[/?#])", str(ref))
    return match.group(1) if match else str(ref)
if args[:2] == ["issue", "create"]:
    state["next_number"] += 1
    number = str(state["next_number"])
    title = args[args.index("--title") + 1] if "--title" in args else ""
    state["issues"][number] = {"number": int(number), "state": "OPEN", "title": title, "body": stdin, "comments": []}
    print(f"{base_url}/{number}")
elif args[:2] == ["issue", "view"]:
    number = get_number(args[2])
    issue = state["issues"].get(number)
    if issue is None:
        sys.stderr.write("issue not found\n")
        raise SystemExit(1)
    print(json.dumps(issue))
elif args[:2] == ["issue", "edit"]:
    number = get_number(args[2])
    issue = state["issues"][number]
    issue["title"] = args[args.index("--title") + 1] if "--title" in args else issue["title"]
    issue["body"] = stdin
    print("updated")
elif args[:2] == ["issue", "comment"]:
    number = get_number(args[2])
    issue = state["issues"][number]
    comment = args[args.index("--body") + 1]
    issue["comments"].append({"body": comment})
    print("commented")
elif args[:2] == ["label", "create"]:
    print("label exists")
else:
    print("ok")
state_path.write_text(json.dumps(state), encoding="utf-8")
'''
    source = (
        template.replace("__CALLS__", repr(str(calls)))
        .replace("__STATE__", repr(str(state_path)))
        .replace("__URL__", repr(url))
        .replace("__FAIL__", repr(fail))
    )
    script.write_text(source, encoding="utf-8")
    script.chmod(script.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
    return script


class DispatchTests(unittest.TestCase):
    def test_dry_run_plans_without_sending(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            revision_book(root)
            result = dispatch_pending(root=root, apply=False)
            self.assertFalse(result["applied"])
            self.assertTrue(any(entry["result"] == "planned" for entry in result["results"]))
            book = json.loads((root / "data" / "alerts.json").read_text())
            self.assertTrue(all((alert["dispatch"] or {}).get("status") == "pending" for alert in book["alerts"]))
            self.assertFalse((root / "data" / "alert-dispatch-log.json").exists())

    def test_apply_creates_issues_and_records_the_urls(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            revision_book(root)
            gh = write_stub_gh(root)
            result = dispatch_pending(root=root, apply=True, gh_path=str(gh), env={})
            self.assertTrue(result["applied"])
            self.assertTrue(all(entry["result"] == "sent" for entry in result["results"]))
            book = json.loads((root / "data" / "alerts.json").read_text())
            sent = [alert for alert in book["alerts"] if (alert["dispatch"] or {}).get("status") == "sent"]
            self.assertEqual(len(sent), len(book["alerts"]))
            for alert in sent:
                self.assertTrue(alert["dispatch"]["issue_url"].startswith("https://github.com/"))
            log = json.loads((root / "data" / "alert-dispatch-log.json").read_text())
            issue_entries = [entry for entry in log["entries"] if entry["channel"] == "github_issue"]
            self.assertTrue(issue_entries)
            self.assertTrue(all(entry["result"] == "sent" for entry in issue_entries))
            calls = [json.loads(line) for line in (root / "gh-calls.jsonl").read_text().splitlines()]
            create = [call for call in calls if call["argv"][:2] == ["issue", "create"]]
            self.assertTrue(create)
            self.assertIn("Alert id", create[0]["stdin"])
            self.assertIn("Automated candidate detection only", create[0]["stdin"])
            # A second run has nothing left to do.
            again = dispatch_pending(root=root, apply=True, gh_path=str(gh), env={})
            self.assertEqual(again["results"], [])

    def test_failed_delivery_is_recorded_and_retried_then_abandoned(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            revision_book(root)
            gh = write_stub_gh(root, fail=True)
            for attempt in range(3):
                dispatch_pending(root=root, apply=True, gh_path=str(gh), env={}, now=f"2026-10-07T05:0{attempt}:00Z")
            book = json.loads((root / "data" / "alerts.json").read_text())
            statuses = {(alert["dispatch"] or {}).get("status") for alert in book["alerts"]}
            self.assertEqual(statuses, {"failed"})
            for alert in book["alerts"]:
                self.assertEqual(len(alert["dispatch"]["attempts"]), 3)
            log = json.loads((root / "data" / "alert-dispatch-log.json").read_text())
            self.assertTrue(all(entry["result"] == "failed" for entry in log["entries"]))
            self.assertIn("simulated failure", json.dumps(log))
            # Once abandoned, nothing is retried.
            result = dispatch_pending(root=root, apply=True, gh_path=str(gh), env={})
            self.assertEqual(
                [entry for entry in result["results"] if entry["action"] == "create_issue"], []
            )

    def test_missing_gh_is_reported_not_assumed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            revision_book(root)
            result = dispatch_pending(root=root, apply=True, gh_path="", env={})
            self.assertFalse(result["gh_available"])
            book = json.loads((root / "data" / "alerts.json").read_text())
            self.assertTrue(all((alert["dispatch"] or {}).get("status") == "skipped" for alert in book["alerts"]))
            self.assertIn("gh CLI not available", json.dumps(book))

    def test_webhook_receives_the_alert_when_configured(self) -> None:
        received: list[dict] = []

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):  # noqa: N802 - stdlib naming
                length = int(self.headers.get("Content-Length", 0))
                received.append(json.loads(self.rfile.read(length).decode("utf-8")))
                self.send_response(200)
                self.end_headers()
                self.wfile.write(b"ok")

            def log_message(self, *args):  # silence test output
                return

        server = HTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            with tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                revision_book(root)
                gh = write_stub_gh(root)
                result = dispatch_pending(
                    root=root,
                    apply=True,
                    gh_path=str(gh),
                    env={"SCORING_DISCREPANCY_WEBHOOK_URL": f"http://127.0.0.1:{server.server_address[1]}/hook"},
                )
                self.assertTrue(result["webhook_configured"])
                self.assertTrue(received, "the configured webhook should receive one post per sent alert")
                self.assertIn("text", received[0])
                self.assertIn("final_score_feed_revision", json.dumps(received[0]["alert"]))
                book = json.loads((root / "data" / "alerts.json").read_text())
                self.assertTrue(
                    all((alert["dispatch"] or {}).get("webhook_status") == "sent" for alert in book["alerts"])
                )
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)

    def test_unconfigured_webhook_is_logged_as_a_skip(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            revision_book(root)
            gh = write_stub_gh(root)
            dispatch_pending(root=root, apply=True, gh_path=str(gh), env={})
            log = json.loads((root / "data" / "alert-dispatch-log.json").read_text())
            webhook_entries = [entry for entry in log["entries"] if entry["channel"] == "webhook"]
            self.assertTrue(webhook_entries)
            self.assertEqual(webhook_entries[-1]["result"], "skipped")
            self.assertIn("not configured", webhook_entries[-1]["detail"])

    def test_material_issue_change_refreshes_and_comments_once(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            revision_book(root)
            gh = write_stub_gh(root)
            dispatch_pending(root=root, apply=True, gh_path=str(gh), env={})

            book = json.loads((root / "data" / "alerts.json").read_text())
            alert = book["alerts"][0]
            issue_number = str(alert["dispatch"]["issue_number"])
            alert["summary"] += " A new evidence observation was recorded."
            save_alert_book(root, book)

            result = dispatch_pending(
                root=root, apply=True, gh_path=str(gh), env={}, now="2026-10-07T05:10:00Z"
            )
            actions = [call["argv"][:2] for call in gh_calls(root)]
            self.assertTrue(any(entry["action"] == "refresh_issue" for entry in result["results"]))
            self.assertIn(["issue", "view"], actions)
            self.assertIn(["issue", "edit"], actions)
            self.assertIn(["issue", "comment"], actions)

            state = json.loads((root / "gh-issues.json").read_text())
            issue = state["issues"][issue_number]
            self.assertIn("new evidence observation", issue["body"])
            self.assertEqual(len(issue["comments"]), 1)
            self.assertIn("scoring-discrepancy-update:", issue["comments"][0]["body"])

            calls_before = len(gh_calls(root))
            again = dispatch_pending(root=root, apply=True, gh_path=str(gh), env={})
            self.assertEqual(again["results"], [])
            self.assertEqual(len(gh_calls(root)), calls_before)

    def test_human_closed_issue_is_never_edited_commented_or_reopened(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            revision_book(root)
            gh = write_stub_gh(root)
            dispatch_pending(root=root, apply=True, gh_path=str(gh), env={})

            book = json.loads((root / "data" / "alerts.json").read_text())
            alert = book["alerts"][0]
            issue_number = str(alert["dispatch"]["issue_number"])
            alert["summary"] += " A later monitor observation requires a refresh."
            save_alert_book(root, book)
            state_path = root / "gh-issues.json"
            state = json.loads(state_path.read_text())
            state["issues"][issue_number]["state"] = "CLOSED"
            state_path.write_text(json.dumps(state), encoding="utf-8")

            result = dispatch_pending(
                root=root, apply=True, gh_path=str(gh), env={}, now="2026-10-07T05:11:00Z"
            )
            self.assertTrue(
                any(entry["action"] == "respect_human_closure" for entry in result["results"])
            )
            calls = gh_calls(root)
            self.assertTrue(any(call["argv"][:2] == ["issue", "view"] for call in calls))
            forbidden = (
                ["issue", "edit"],
                ["issue", "comment"],
                ["issue", "close"],
                ["issue", "reopen"],
            )
            self.assertFalse(any(call["argv"][:2] in forbidden for call in calls))
            updated = json.loads((root / "data" / "alerts.json").read_text())
            self.assertTrue(updated["alerts"][0]["dispatch"]["human_closed"])

            calls_before = len(calls)
            dispatch_pending(root=root, apply=True, gh_path=str(gh), env={})
            self.assertEqual(len(gh_calls(root)), calls_before)

    def test_resolution_is_a_non_causal_comment_and_leaves_issue_open(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            revision_book(root)
            gh = write_stub_gh(root)
            dispatch_pending(root=root, apply=True, gh_path=str(gh), env={})

            book = json.loads((root / "data" / "alerts.json").read_text())
            alert_id = book["alerts"][0]["id"]
            book = resolve_alert(
                book,
                alert_id,
                "The feed values converged; this is not a finding about the NBA record.",
                "2026-10-07T05:12:00Z",
                reviewer="test",
            )
            issue_number = str(
                next(alert for alert in book["alerts"] if alert["id"] == alert_id)["dispatch"]["issue_number"]
            )
            save_alert_book(root, book)

            result = dispatch_pending(
                root=root, apply=True, gh_path=str(gh), env={}, now="2026-10-07T05:13:00Z"
            )
            actions = [call["argv"][:2] for call in gh_calls(root)]
            self.assertIn(["issue", "comment"], actions)
            self.assertNotIn(["issue", "close"], actions)
            self.assertTrue(any(entry["action"] == "comment_issue" for entry in result["results"]))
            state = json.loads((root / "gh-issues.json").read_text())
            issue = state["issues"][issue_number]
            self.assertEqual(issue["state"], "OPEN")
            self.assertIn("Monitor disposition (not causal)", issue["body"])
            self.assertTrue(
                any("Non-causal monitor resolution notice" in c["body"] for c in issue["comments"])
            )

    def test_issue_body_escapes_untrusted_feed_text_and_rejects_unsafe_links(self) -> None:
        hostile = "@everyone\r\n## forged heading [click](javascript:alert(1)) <script> | _text_"
        issue = build_issue(
            {
                "id": "ALR-hostile",
                "severity": "high",
                "status": "open",
                "title": f"Home team {hostile}",
                "summary": hostile,
                "evidence": [
                    {"label": "<img src=x onerror=alert(1)>", "url": "javascript:alert(1)", "value": hostile}
                ],
                "review_steps": [hostile],
            }
        )
        self.assertNotIn("@everyone", issue["title"])
        self.assertIn("@\u200beveryone", issue["title"])
        self.assertNotIn("<script>", issue["body"])
        self.assertIn("&lt;script&gt;", issue["body"])
        self.assertNotIn("[click](javascript:", issue["body"])
        self.assertNotIn("](javascript:", issue["body"])
        self.assertNotIn("\n## forged heading", issue["body"])
        self.assertIn("@\u200beveryone", issue["body"])
        self.assertIn(r"\[click\]\(javascript:alert\(1\)\)", issue["body"])

    def test_issue_body_lists_evidence_and_limits(self) -> None:
        first = observation("2026-10-07T04:00:00Z", (139, 104), (139, 104))
        state = update_state(empty_state(), [first], first["observed_at"], HEALTHY)
        revised = observation("2026-10-07T04:05:00Z", (140, 104), (140, 104))
        state = update_state(state, [revised], revised["observed_at"], HEALTHY)
        book, _ = update_book(None, state, feed_health(), revised["observed_at"])
        issue = build_issue(book["alerts"][0])
        self.assertIn("[score-alert]", issue["title"])
        self.assertIn("score-alert", issue["labels"])
        self.assertIn("## Evidence to review", issue["body"])
        self.assertIn("## Limits of this alert", issue["body"])
        self.assertIn("not establish that any NBA record was wrong", issue["body"])


if __name__ == "__main__":
    unittest.main()
