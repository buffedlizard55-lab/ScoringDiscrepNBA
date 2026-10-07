"""Command-line entry point: python -m monitor."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .alerts import resolve_alert
from .dispatch import dispatch_pending
from .feeds import utc_now
from .runner import run_live, run_with_payloads
from .validation import DataValidationError, load_state, validate_repository_data, write_json


def _load_fixture(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise DataValidationError(f"Could not read fixture {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise DataValidationError("Fixture root must be a JSON object")
    return data


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m monitor",
        description="Validate evidence data or run one NBA scoring-monitor cycle.",
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check-data", action="store_true", help="validate repository JSON and evidence links")
    mode.add_argument("--live", action="store_true", help="poll NBA and ESPN public scoreboards")
    mode.add_argument("--fixtures", type=Path, help="run a deterministic local poll from a fixture JSON file")
    mode.add_argument(
        "--dispatch-alerts",
        action="store_true",
        help="queue (default) or deliver (with --apply) notifications for pending alerts",
    )
    mode.add_argument(
        "--resolve-alert",
        metavar="ALERT_ID",
        help="close one alert by hand after review, recording the reason",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="with --dispatch-alerts: actually deliver notifications (default is a dry run)",
    )
    parser.add_argument("--note", help="with --resolve-alert: the review note recorded on the alert")
    parser.add_argument("--root", type=Path, default=Path("."), help="repository or output root (default: current directory)")
    args = parser.parse_args(argv)

    try:
        if args.check_data:
            errors = validate_repository_data(args.root)
            if errors:
                for error in errors:
                    print(f"ERROR: {error}", file=sys.stderr)
                return 1
            cases = json.loads((args.root / "data" / "reviewed-cases.json").read_text(encoding="utf-8"))["cases"]
            leads = json.loads((args.root / "data" / "leads.json").read_text(encoding="utf-8"))["leads"]
            print(f"Data checks passed: {len(cases)} reviewed cases; {len(leads)} explicitly unverified lead(s).")
            return 0

        if args.fixtures:
            fixture = _load_fixture(args.fixtures)
            state, feed = run_with_payloads(
                fixture.get("nba_payload"),
                fixture.get("espn_payload"),
                root=args.root,
                observed_at=fixture.get("observed_at"),
                nba_hash=fixture.get("nba_hash"),
                espn_hash=fixture.get("espn_hash"),
                pbp_payloads=fixture.get("pbp_payloads"),
                source_errors=fixture.get("source_errors"),
                response_metadata=fixture.get("response_metadata"),
                pbp_metadata=fixture.get("pbp_metadata"),
                summary_payloads=fixture.get("summary_payloads"),
                source_diagnostics=fixture.get("source_diagnostics"),
            )
            print(
                f"Fixture poll saved: feed={feed.get('status')}, "
                f"games={len(feed.get('games', []))}, "
                f"investigations={len(state.get('investigations', []))}."
            )
            return 0

        if args.dispatch_alerts:
            result = dispatch_pending(root=args.root, apply=args.apply)
            mode_text = "delivered" if result["applied"] else "planned (dry run)"
            print(
                f"Alert dispatch {mode_text}: {len(result['results'])} action(s), "
                f"webhook_configured={result['webhook_configured']}, gh_available={result['gh_available']}."
            )
            for entry in result["results"]:
                print(
                    f"  {entry.get('alert_id')}: {entry.get('action')} -> {entry.get('result')}"
                    + (f" ({entry.get('title')})" if entry.get("title") else "")
                    + (f" ({entry.get('detail')})" if entry.get("result") in {"failed", "skipped"} else "")
                )
            if not result["results"]:
                print("  No pending notifications. Nothing was sent.")
            return 0

        if args.resolve_alert:
            alerts_path = args.root / "data" / "alerts.json"
            book = json.loads(alerts_path.read_text(encoding="utf-8"))
            note = args.note or "Closed during review; see the investigation ledger for the sources checked."
            updated = resolve_alert(book, args.resolve_alert, note, utc_now(), reviewer="agent")
            write_json(alerts_path, updated)
            print(f"Alert {args.resolve_alert} closed with note: {note}")
            return 0

        state, feed = run_live(root=args.root)
        print(
            f"Live poll saved: feed={feed.get('status')}, "
            f"games={len(feed.get('games', []))}, "
            f"investigations={len(state.get('investigations', []))}, "
            f"last_material_change={feed.get('last_updated_at')}."
        )
        for source, health in feed.get("source_health", {}).items():
            print(f"  {source}: {health.get('status')} ({health.get('url')})")
        for source, attempts in (feed.get("source_diagnostics") or {}).items():
            for attempt in attempts:
                if isinstance(attempt, dict) and "profile" in attempt:
                    print(
                        f"  {source} attempt profile={attempt.get('profile')}: "
                        f"{attempt.get('outcome')} {attempt.get('error') or attempt.get('http_status')}"
                    )
        alerts_path = args.root / "data" / "alerts.json"
        if alerts_path.exists():
            book = json.loads(alerts_path.read_text(encoding="utf-8"))
            counts = book.get("counts") or {}
            print(
                f"  alerts: {counts.get('open', 0)} open "
                f"(critical={((counts.get('open_by_severity') or {}).get('critical', 0))}, "
                f"high={((counts.get('open_by_severity') or {}).get('high', 0))}, "
                f"medium={((counts.get('open_by_severity') or {}).get('medium', 0))}), "
                f"{counts.get('pending_dispatch', 0)} pending notification(s)."
            )
        if feed.get("status") != "healthy":
            print("WARNING: one or more feeds were unavailable or invalid; this is not evidence of no games or no discrepancies.")
        return 0
    except DataValidationError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    except Exception as exc:  # the scheduler needs a readable failure, never a false 'no anomalies' status
        print(f"ERROR: monitor run failed safely: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
