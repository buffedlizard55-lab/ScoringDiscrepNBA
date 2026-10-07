from __future__ import annotations

import unittest

from monitor.alerts import empty_book, resolve_alert, update_book
from monitor.engine import empty_state, update_state

HEALTHY = {
    "nba": {"status": "ok", "url": "https://cdn.nba.com/example"},
    "espn": {"status": "ok", "url": "https://site.api.espn.com/example"},
}
NBA_DOWN = {
    "nba": {"status": "unavailable", "url": "https://cdn.nba.com/example", "error": "Could not fetch: HTTP 403"},
    "espn": {"status": "ok", "url": "https://site.api.espn.com/example"},
}


def observation(at: str, nba: tuple[int, int], espn: tuple[int, int], status: str = "live") -> dict:
    mismatch = nba != espn
    return {
        "observed_at": at,
        "game_id": "0022600001",
        "game_date": "2026-10-07",
        "status": status,
        "period": 2,
        "clock": "PT08M15.00S",
        "away_team": {"name": "Away Club", "abbreviation": "AAA"},
        "home_team": {"name": "Home Club", "abbreviation": "BBB"},
        "scores": {
            "nba": {"away": nba[0], "home": nba[1], "source_url": "https://cdn.nba.com/example"},
            "espn": {"away": espn[0], "home": espn[1], "source_url": "https://site.api.espn.com/example"},
        },
        "score_mismatch": mismatch,
        "source_hashes": {"nba": "abc", "espn": "def"},
        "latest_official_scoring_play": None,
        "play_by_play_source_url": None,
    }


def feed_health(health: dict) -> dict:
    return {"status": "healthy" if all(v.get("status") == "ok" for v in health.values()) else "degraded",
            "source_health": health, "games": []}


def consistency_check(status: str = "inconsistent") -> dict:
    return {
        "schema_version": 1,
        "source_key": "espn",
        "game_id": "0022600001",
        "game_key": "0022600001",
        "source_url": "https://site.api.espn.com/summary?event=1",
        "method": "2 * (FGM - 3PM) + 3 * 3PM + FTM, using the provider's own box-score components",
        "status": status,
        "provider_reported": {"away": 148, "home": 115},
        "checks": [
            {
                "side": "home",
                "team": "WSH",
                "provider_reported_final": 115,
                "derived_points": 114,
                "difference": -1,
                "components": {
                    "fieldGoalsMade-attempted": (41, 91),
                    "threePointersMade-attempted": (15, 41),
                    "freeThrowsMade-attempted": (17, 23),
                },
            }
        ],
        "assessment": "candidate_requires_review",
        "note": "The provider's reported final does not follow from the box-score components it publishes.",
    }


class AlertRuleTests(unittest.TestCase):
    def test_single_poll_mismatch_is_not_alerted_and_two_polls_is(self) -> None:
        first = observation("2026-10-07T04:00:00Z", (50, 39), (50, 38))
        state = update_state(empty_state(), [first], first["observed_at"], HEALTHY)
        book, changed = update_book(empty_book(), state, feed_health(HEALTHY), first["observed_at"])
        self.assertTrue(changed)
        self.assertEqual(book["alerts"], [], "a one-poll difference can just be provider lag")

        second = observation("2026-10-07T04:05:00Z", (51, 39), (51, 38))
        state = update_state(state, [second], second["observed_at"], HEALTHY)
        book, changed = update_book(book, state, feed_health(HEALTHY), second["observed_at"])
        self.assertTrue(changed)
        self.assertEqual(len(book["alerts"]), 1)
        alert = book["alerts"][0]
        self.assertEqual(alert["type"], "cross_source_score_mismatch")
        self.assertEqual(alert["severity"], "high")
        self.assertEqual(alert["status"], "open")
        self.assertEqual(alert["verification_status"], "unverified")
        self.assertTrue(alert["review_steps"])
        self.assertTrue(all(entry.get("url") for entry in alert["evidence"]))
        self.assertEqual(alert["dispatch"]["status"], "pending")
        self.assertEqual(book["counts"]["pending_dispatch"], 1)

    def test_ledger_only_changes_at_occurrence_milestones(self) -> None:
        first = observation("2026-10-07T04:00:00Z", (50, 39), (50, 38))
        state = update_state(empty_state(), [first], first["observed_at"], HEALTHY)
        book, _ = update_book(empty_book(), state, feed_health(HEALTHY), first["observed_at"])
        # Poll 2 opens the alert (a single-poll difference is treated as lag).
        second = observation("2026-10-07T04:05:00Z", (51, 39), (51, 38))
        state = update_state(state, [second], second["observed_at"], HEALTHY)
        book, changed = update_book(book, state, feed_health(HEALTHY), second["observed_at"])
        self.assertTrue(changed)
        # Poll 3 reaches the next occurrence milestone (3 saved observations).
        third = observation("2026-10-07T04:10:00Z", (51, 39), (51, 38))
        state = update_state(state, [third], third["observed_at"], HEALTHY)
        book, changed = update_book(book, state, feed_health(HEALTHY), third["observed_at"])
        self.assertTrue(changed)
        self.assertEqual(book["alerts"][0]["occurrences"], 2)
        self.assertEqual(book["alerts"][0]["occurrences_bucket"], 3)
        # A further unchanged poll is not rewritten: no new reviewable fact.
        fourth = observation("2026-10-07T04:15:00Z", (51, 39), (51, 38))
        state = update_state(state, [fourth], fourth["observed_at"], HEALTHY)
        book, changed = update_book(book, state, feed_health(HEALTHY), fourth["observed_at"])
        self.assertFalse(changed, "no new alert facts means the published file must not be rewritten")
        self.assertEqual(len(book["alerts"]), 1)

    def test_convergence_resolves_the_alert_without_claiming_a_cause(self) -> None:
        first = observation("2026-10-07T04:00:00Z", (50, 39), (50, 38))
        state = update_state(empty_state(), [first], first["observed_at"], HEALTHY)
        book, _ = update_book(empty_book(), state, feed_health(HEALTHY), first["observed_at"])
        second = observation("2026-10-07T04:05:00Z", (51, 39), (51, 38))
        state = update_state(state, [second], second["observed_at"], HEALTHY)
        book, _ = update_book(book, state, feed_health(HEALTHY), second["observed_at"])
        agree_one = observation("2026-10-07T04:10:00Z", (52, 39), (52, 39))
        state = update_state(state, [agree_one], agree_one["observed_at"], HEALTHY)
        agree_two = observation("2026-10-07T04:15:00Z", (53, 39), (53, 39))
        state = update_state(state, [agree_two], agree_two["observed_at"], HEALTHY)
        book, changed = update_book(book, state, feed_health(HEALTHY), agree_two["observed_at"])
        self.assertTrue(changed)
        alert = book["alerts"][0]
        self.assertEqual(alert["status"], "resolved")
        self.assertIn("does not establish", alert["resolution"]["note"])
        self.assertEqual(book["counts"]["open"], 0)

    def test_final_score_revision_alert_is_critical_and_carries_both_values(self) -> None:
        first = observation("2026-10-07T04:00:00Z", (139, 104), (139, 104), status="final")
        state = update_state(empty_state(), [first], first["observed_at"], HEALTHY)
        revised = observation("2026-10-07T04:05:00Z", (140, 104), (140, 104), status="final")
        state = update_state(state, [revised], revised["observed_at"], HEALTHY)
        book, _ = update_book(empty_book(), state, feed_health(HEALTHY), revised["observed_at"])
        revisions = [alert for alert in book["alerts"] if alert["type"] == "final_score_feed_revision"]
        self.assertEqual(len(revisions), 2, "each source keeps its own revision record")
        alert = next(item for item in revisions if "NBA" in item["title"])
        self.assertEqual(alert["severity"], "critical")
        self.assertEqual(alert["status"], "open")
        self.assertIn("139-104", alert["title"])
        self.assertIn("140-104", alert["title"])
        self.assertEqual(alert["dispatch"]["status"], "pending")

    def test_internal_inconsistency_alert_exposes_the_arithmetic(self) -> None:
        game = observation("2026-10-07T04:00:00Z", (148, 115), (148, 115), status="final")
        check = consistency_check("inconsistent")
        state = update_state(empty_state(), [game], game["observed_at"], HEALTHY, [check])
        book, _ = update_book(empty_book(), state, feed_health(HEALTHY), game["observed_at"])
        alerts = [alert for alert in book["alerts"] if alert["type"] == "final_score_internal_inconsistency"]
        self.assertEqual(len(alerts), 1)
        alert = alerts[0]
        self.assertEqual(alert["severity"], "critical")
        self.assertIn("114", alert["summary"])
        self.assertEqual(alert["arithmetic"][0]["derived_points"], 114)
        self.assertEqual(alert["arithmetic"][0]["provider_reported_final"], 115)
        self.assertIn("Recompute", " ".join(alert["review_steps"]))

    def test_source_outage_alert_fires_after_the_configured_window(self) -> None:
        state = empty_state()
        book = empty_book()
        # First failure is recorded immediately but is not alerted: a single
        # missed poll can be a transient timeout.
        for at in ("2026-10-07T04:00:00Z", "2026-10-07T04:05:00Z", "2026-10-07T04:10:00Z"):
            state = update_state(state, [], at, NBA_DOWN)
            book, _ = update_book(book, state, feed_health(NBA_DOWN), at)
            self.assertEqual(
                [alert for alert in book["alerts"] if alert["type"] == "source_unavailable"],
                [],
                "the authoritative source outage is not alerted before the 15-minute window",
            )
        alerted_at = "2026-10-07T04:16:00Z"
        state = update_state(state, [], alerted_at, NBA_DOWN)
        book, changed = update_book(book, state, feed_health(NBA_DOWN), alerted_at)
        self.assertTrue(changed)
        outage = [alert for alert in book["alerts"] if alert["type"] == "source_unavailable"]
        self.assertEqual(len(outage), 1)
        alert = outage[0]
        self.assertEqual(alert["severity"], "high")
        self.assertEqual(alert["dispatch"]["status"], "pending")
        self.assertIn("16 minutes", alert["title"])
        self.assertIn("not evidence that no discrepancy exists", alert["summary"])
        self.assertIn("HTTP 403", str(alert["evidence"]))

        # Recovery resolves the alert and records the blind window.
        recovered_at = "2026-10-07T04:21:00Z"
        state = update_state(state, [], recovered_at, HEALTHY)
        self.assertEqual(len(state["coverage_gaps"]), 1)
        book, changed = update_book(book, state, feed_health(HEALTHY), recovered_at)
        self.assertTrue(changed)
        alert = next(item for item in book["alerts"] if item["type"] == "source_unavailable")
        self.assertEqual(alert["status"], "resolved")
        self.assertEqual(alert["resolution"]["type"], "source_recovered")
        self.assertEqual(book["coverage_gaps"][0]["source_key"], "nba")
        self.assertIn("could not run", book["coverage_gaps"][0]["impact"])

    def test_comparator_outage_is_medium_and_not_notified_until_an_hour(self) -> None:
        espn_down = {
            "nba": {"status": "ok", "url": "https://cdn.nba.com/example"},
            "espn": {"status": "unavailable", "url": "https://site.api.espn.com/example", "error": "HTTP 500"},
        }
        state = empty_state()
        book = empty_book()
        for at in ("2026-10-07T04:00:00Z", "2026-10-07T04:16:00Z"):
            state = update_state(state, [], at, espn_down)
            book, _ = update_book(book, state, feed_health(espn_down), at)
        alert = next(item for item in book["alerts"] if item["type"] == "source_unavailable")
        self.assertEqual(alert["severity"], "medium")
        self.assertEqual(alert["dispatch"]["status"], "not_required")
        self.assertEqual(book["counts"]["pending_dispatch"], 0)

        # Past the comparator dispatch threshold the alert is queued instead of
        # being silently left on the site.
        later = "2026-10-07T05:05:00Z"
        state = update_state(state, [], later, espn_down)
        book, _ = update_book(book, state, feed_health(espn_down), later)
        alert = next(item for item in book["alerts"] if item["type"] == "source_unavailable")
        self.assertEqual(alert["dispatch"]["status"], "pending")
        self.assertEqual(book["counts"]["pending_dispatch"], 1)

    def test_detector_status_reports_what_could_not_run(self) -> None:
        state = update_state(empty_state(), [], "2026-10-07T04:00:00Z", NBA_DOWN)
        book, _ = update_book(empty_book(), state, feed_health(NBA_DOWN), "2026-10-07T04:00:00Z")
        status = book["detector_status"]["cross_source_comparison"]
        self.assertFalse(status["available"])
        self.assertIn("fewer than two sources", status["blocked_reason"])

    def test_resolve_alert_records_the_reason(self) -> None:
        first = observation("2026-10-07T04:00:00Z", (139, 104), (139, 104), status="final")
        state = update_state(empty_state(), [first], first["observed_at"], HEALTHY)
        revised = observation("2026-10-07T04:05:00Z", (140, 104), (140, 104), status="final")
        state = update_state(state, [revised], revised["observed_at"], HEALTHY)
        book, _ = update_book(empty_book(), state, feed_health(HEALTHY), revised["observed_at"])
        target = book["alerts"][0]["id"]
        updated = resolve_alert(book, target, "Checked NBA game page; correction confirmed.", "2026-10-07T05:00:00Z", reviewer="agent")
        alert = next(item for item in updated["alerts"] if item["id"] == target)
        self.assertEqual(alert["status"], "resolved")
        self.assertEqual(alert["resolution"]["type"], "closed_by_review")
        self.assertIn("correction confirmed", alert["resolution"]["note"])
        self.assertEqual(alert["lifecycle"][-1]["event"], "closed_by_review")


if __name__ == "__main__":
    unittest.main()
