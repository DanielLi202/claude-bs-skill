#!/usr/bin/env python3
"""Structured release gates for bs-evolve Stage 4."""
from __future__ import annotations

import argparse
import pathlib
import subprocess
import sys
from typing import Any

import yaml

RULE_SURFACES = (
    "runtime/grade_lint.py",
    "tests/test_grade_lint.py",
    "tests/grade_lint_fixtures/",
    "harness/evolve-loop/bin/backtest.py",
)


def load(path: pathlib.Path) -> Any:
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def misfire_id(row: Any) -> str:
    if isinstance(row, dict):
        return str(row.get("id") or row.get("cycle") or row.get("name") or row)
    return str(row)


def check_g4(report_path: pathlib.Path, adj_path: pathlib.Path | None, plan_path: pathlib.Path | None) -> int:
    rep = load(report_path)
    if not rep.get("must_fire"):
        print("must_fire false")
        return 1
    if plan_path:
        plan = load(plan_path)
        if rep.get("baseline_ref") != plan.get("baseline_ref"):
            print(f"baseline_ref mismatch: report={rep.get('baseline_ref')} plan={plan.get('baseline_ref')}")
            return 1
    mis = rep.get("misfire_candidates") or []
    if not mis:
        print("g4 ok")
        return 0
    if not adj_path or not adj_path.exists():
        print(f"{len(mis)} misfire candidate(s) but no adjudication file")
        return 1
    adj = load(adj_path)
    rows = adj.get("adjudications") or adj.get("adj_verify") or []
    by_id = {str(r.get("id") or r.get("cycle")): r for r in rows if isinstance(r, dict)}
    errors = []
    for row in mis:
        mid = misfire_id(row)
        a = by_id.get(mid)
        if not a:
            errors.append(f"missing adjudication for {mid}")
            continue
        verdict = str(a.get("verdict") or a.get("adjudication") or "")
        if verdict == "false_positive":
            errors.append(f"false_positive adjudication for {mid}")
        fv = a.get("fresh_verify") or a.get("fresh_context_verify") or {}
        if not isinstance(fv, dict) or str(fv.get("status") or fv.get("verdict") or "").lower() not in {"pass", "passed", "true"}:
            errors.append(f"missing fresh-verify pass for {mid}")
    extra = sorted(set(by_id) - {misfire_id(r) for r in mis})
    if extra:
        errors.append(f"adjudication without matching misfire: {', '.join(extra)}")
    if errors:
        print("; ".join(errors))
        return 1
    print("g4 ok")
    return 0


def infer_release_base(skill: pathlib.Path) -> str | None:
    proc = subprocess.run(
        [
            "git",
            "-C",
            str(skill),
            "tag",
            "--merged",
            "HEAD",
            "--list",
            "v[0-9]*.[0-9]*.[0-9]*",
            "--sort=-v:refname",
        ],
        text=True,
        capture_output=True,
    )
    if proc.returncode == 0:
        for line in proc.stdout.splitlines():
            tag = line.strip()
            if tag:
                return tag
    proc = subprocess.run(["git", "-C", str(skill), "rev-parse", "--verify", "HEAD~1"], text=True, capture_output=True)
    if proc.returncode == 0:
        return "HEAD~1"
    return None


def changed_files(skill: pathlib.Path, anchor: str | None) -> list[str]:
    names: set[str] = set()
    commands = []
    base = anchor or infer_release_base(skill)
    if base:
        commands.append(["git", "-C", str(skill), "diff", "--name-only", f"{base}..HEAD"])
    commands.extend([
        ["git", "-C", str(skill), "diff", "--name-only"],
        ["git", "-C", str(skill), "diff", "--cached", "--name-only"],
        ["git", "-C", str(skill), "ls-files", "--others", "--exclude-standard"],
    ])
    for cmd in commands:
        proc = subprocess.run(cmd, text=True, capture_output=True)
        if proc.returncode != 0:
            raise SystemExit(proc.stderr.strip())
        names.update(line.strip() for line in proc.stdout.splitlines() if line.strip())
    return sorted(names)


def touches_rule_surface(paths: list[str]) -> bool:
    return any(path == surf.rstrip("/") or path.startswith(surf) for path in paths for surf in RULE_SURFACES)


def check_no_backtest(skill: pathlib.Path, anchor: str | None, reason: str) -> int:
    if not reason.strip():
        print("--no-backtest requires a reason")
        return 1
    if not anchor:
        print("no-backtest requires --anchor for changed-surface classification")
        return 1
    paths = changed_files(skill, anchor)
    if touches_rule_surface(paths):
        print("--no-backtest rejected: grade_lint/rule/fixture/backtest surface changed")
        return 1
    print("no-backtest ok")
    return 0


def check_near_miss(skill: pathlib.Path, anchor: str | None) -> int:
    paths = changed_files(skill, anchor)
    rule_changed = any(path in {"runtime/grade_lint.py", "tests/test_grade_lint.py"} for path in paths)
    fixture_changed = any(path.startswith("tests/grade_lint_fixtures/") and path.endswith("metadata.yaml") for path in paths)
    if rule_changed and not fixture_changed:
        print("near-miss fixture missing for grade_lint rule change")
        return 1
    print("near-miss ok")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    g4 = sub.add_parser("g4")
    g4.add_argument("--report", required=True, type=pathlib.Path)
    g4.add_argument("--adj-verify", type=pathlib.Path)
    g4.add_argument("--plan-file", type=pathlib.Path)
    nb = sub.add_parser("no-backtest")
    nb.add_argument("--skill", required=True, type=pathlib.Path)
    nb.add_argument("--anchor")
    nb.add_argument("--reason", required=True)
    nm = sub.add_parser("near-miss")
    nm.add_argument("--skill", required=True, type=pathlib.Path)
    nm.add_argument("--anchor")
    args = ap.parse_args()
    if args.cmd == "g4":
        return check_g4(args.report, args.adj_verify, args.plan_file)
    if args.cmd == "no-backtest":
        return check_no_backtest(args.skill.resolve(), args.anchor, args.reason)
    return check_near_miss(args.skill.resolve(), args.anchor)


if __name__ == "__main__":
    raise SystemExit(main())
