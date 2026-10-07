#!/usr/bin/env python3
"""Aggregate case files into data/cases.json and mirror data payloads into docs/data/ for GitHub Pages."""
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CASES_DIR = ROOT / "data" / "cases"
DOCS_DATA = ROOT / "docs" / "data"


def main():
    cases = []
    for path in sorted(CASES_DIR.glob("*.json")):
        cases.append(json.loads(path.read_text()))
    cases.sort(key=lambda c: (c.get("game_date") or "0000-00-00", c["id"]))
    (ROOT / "data" / "cases.json").write_text(json.dumps({"cases": cases}, indent=2) + "\n")
    DOCS_DATA.mkdir(parents=True, exist_ok=True)
    for name in ("cases.json", "stats.json", "investigations.json", "sources.json"):
        src = ROOT / "data" / name
        if src.exists():
            shutil.copy(src, DOCS_DATA / name)
            print(f"mirrored {name}")
        else:
            print(f"WARNING: {name} not found, skipped")
    monitor_snapshot = ROOT / "data" / "monitor" / "current.json"
    if monitor_snapshot.exists():
        monitor_data = DOCS_DATA / "monitor"
        monitor_data.mkdir(parents=True, exist_ok=True)
        shutil.copy(monitor_snapshot, monitor_data / "current.json")
        print("mirrored monitor/current.json")
    print(f"aggregated {len(cases)} cases")


if __name__ == "__main__":
    main()
