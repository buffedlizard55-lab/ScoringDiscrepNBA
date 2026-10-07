#!/usr/bin/env python3
"""Build a minimal static GitHub Pages artifact without exposing repository files."""
from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

ROOT_FILES = ("index.html", "styles.css", "app.js")
DATA_FILES = (
    "data/cases.json",
    "data/leads.json",
    "data/sources.json",
    "data/monitor/current.json",
    "data/monitor/candidates.json",
)


def build(root: Path, output: Path) -> None:
    root = root.resolve()
    output = output.resolve()
    if output == root or root not in output.parents:
        raise ValueError("output directory must be a child of the repository root")
    if output.exists():
        shutil.rmtree(output)
    output.mkdir(parents=True)
    for relative in ROOT_FILES + DATA_FILES:
        source = root / relative
        if not source.is_file():
            raise FileNotFoundError(f"required Pages asset missing: {relative}")
        if relative.endswith(".json"):
            with source.open(encoding="utf-8") as handle:
                json.load(handle)
        destination = output / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
    (output / ".nojekyll").write_text("", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--output", type=Path, default=Path("_site"))
    args = parser.parse_args()
    output = args.output if args.output.is_absolute() else args.root / args.output
    build(args.root, output)
    print(f"Pages artifact built at {output.resolve()}")


if __name__ == "__main__":
    main()
