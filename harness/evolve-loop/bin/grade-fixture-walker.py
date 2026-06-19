#!/usr/bin/env python3
"""Run committed anonymous grade_lint must-not-fire fixtures hermetically."""
from __future__ import annotations

import argparse
import pathlib
import re
import subprocess
import sys
import tempfile

import yaml

PRODUCTISH = re.compile(
    r"/(?:Users|private|tmp|var|opt|home)/"
    r"|decision[-_ ]?\w+"
    r"|\bT-\d{8,}(?:-\d+)?-[A-Za-z0-9_.-]+\b"
    r"|\b[A-Z]{1,8}-\d+[A-Za-z0-9'_.-]*\b"
    "|" + "Open" + "Symphony" + "|" + "Project" + "Zephyr",
)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--skill", required=True, type=pathlib.Path)
    ap.add_argument("--fixtures-root", type=pathlib.Path)
    args = ap.parse_args()
    skill = args.skill.resolve()
    root = (args.fixtures_root or (skill / "tests" / "grade_lint_fixtures")).resolve()
    if not root.exists() or not root.is_dir():
        print(f"fixture walker FAIL: missing fixture root {root}", file=sys.stderr)
        return 2
    fixtures = sorted(p for p in root.iterdir() if p.is_dir() and not p.name.startswith("."))
    if not fixtures:
        print("fixture walker FAIL: fixture root is empty", file=sys.stderr)
        return 2
    lint = skill / "runtime" / "grade_lint.py"
    failures: list[str] = []
    for fx in fixtures:
        meta_path = fx / "metadata.yaml"
        grade = fx / "grade.md"
        if not meta_path.exists() or not grade.exists():
            failures.append(f"{fx.name}: missing metadata.yaml or grade.md")
            continue
        meta = yaml.safe_load(meta_path.read_text(encoding="utf-8")) or {}
        if meta.get("expect") != "must_not_fire":
            failures.append(f"{fx.name}: expect must be must_not_fire")
        for path in fx.iterdir():
            if path.is_file() and PRODUCTISH.search(path.read_text(encoding="utf-8", errors="replace")):
                failures.append(f"{fx.name}: product/path/decision token in {path.name}")
        outcome = fx / "outcome.md"
        with tempfile.TemporaryDirectory() as td:
            if not outcome.exists():
                outcome = pathlib.Path(td) / "outcome.md"
                outcome.write_text("# Anonymous outcome\n", encoding="utf-8")
            evidence = pathlib.Path(td) / "grade_lint.json"
            proc = subprocess.run([
                sys.executable,
                str(lint),
                "--task-type",
                str(meta.get("task_type", "code")),
                "--risk-level",
                str(meta.get("risk_level", "low")),
                "--grade-file",
                str(grade),
                "--outcome-file",
                str(outcome),
                "--evidence-file",
                str(evidence),
            ], text=True, capture_output=True)
            if proc.returncode != 0:
                failures.append(f"{fx.name}: grade_lint rc={proc.returncode}: {(proc.stdout + proc.stderr).strip()[:500]}")
    if failures:
        print("fixture walker FAIL", file=sys.stderr)
        for f in failures:
            print(f"- {f}", file=sys.stderr)
        return 1
    print(f"fixture walker OK ({len(fixtures)} fixtures)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
