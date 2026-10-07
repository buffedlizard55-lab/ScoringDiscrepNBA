#!/usr/bin/env python3
"""Compare material monitor state with HEAD, ignoring five-minute heartbeat fields.

The scheduled workflow deploys each poll so Pages can show a fresh attempt time
and game clock, but only commits score, source-health, lifecycle, or other
material changes. This keeps the current feed fresh without a Git commit every
five minutes when nothing material changed.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
MONITOR_FILES = ("data/live-feed.json", "data/monitor-state.json")


def _read_json_bytes(raw: bytes, label: str) -> Any:
    try:
        return json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"Cannot compare invalid JSON in {label}: {exc}") from exc


def _committed_file(path: str, root: Path) -> Any | None:
    result = subprocess.run(
        ["git", "show", f"HEAD:{path}"],
        cwd=root,
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if result.returncode != 0:
        return None
    return _read_json_bytes(result.stdout, f"HEAD:{path}")


def _working_file(path: str, root: Path) -> Any:
    try:
        raw = (root / path).read_bytes()
    except OSError as exc:
        raise ValueError(f"Cannot read working file {path}: {exc}") from exc
    return _read_json_bytes(raw, path)


def _material_projection(path: str, value: Any) -> Any:
    if not isinstance(value, dict):
        return value
    projected = dict(value)
    if path == "data/live-feed.json":
        # These are refreshed and deployed on every schedule, but do not
        # warrant repository history entries by themselves.
        projected.pop("last_poll_attempt_at", None)
        projected.pop("last_successful_comparison_at", None)
        games = projected.get("games")
        if isinstance(games, list):
            stable_games = []
            for game in games:
                if not isinstance(game, dict):
                    stable_games.append(game)
                    continue
                stable = dict(game)
                for volatile in (
                    "observed_at",
                    "clock",
                    "status_text",
                    "latest_official_scoring_play",
                    "play_by_play_source_url",
                ):
                    stable.pop(volatile, None)
                stable_games.append(stable)
            projected["games"] = stable_games
    return projected


def has_material_changes(root: str | Path = ROOT) -> bool:
    root_path = Path(root)
    for relative_path in MONITOR_FILES:
        current = _material_projection(relative_path, _working_file(relative_path, root_path))
        committed = _committed_file(relative_path, root_path)
        if committed is None or current != _material_projection(relative_path, committed):
            return True
    return False


def main() -> int:
    try:
        print("true" if has_material_changes(ROOT) else "false")
        return 0
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
