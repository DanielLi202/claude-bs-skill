#!/usr/bin/env python3
"""Compute the bs-skill release baseline and candidate version before backtest.

This is intentionally read-only. Stage 4 calls it after acquiring SKILL.lock and
before running backtest so the report can prove it used the fresh max release tag.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import re
import subprocess
from datetime import datetime, timezone

import yaml

TAG_RE = re.compile(r"^v(\d+)\.(\d+)\.(\d+)$")


def run(cmd: list[str], *, cwd: pathlib.Path) -> str:
    return subprocess.check_output(cmd, cwd=cwd, text=True).strip()


def semver(tag: str) -> tuple[int, int, int] | None:
    m = TAG_RE.match(tag)
    if not m:
        return None
    return tuple(int(x) for x in m.groups())


def latest_tag(skill: pathlib.Path) -> str:
    tags = run(["git", "tag", "--list", "v[0-9]*.[0-9]*.[0-9]*"], cwd=skill).splitlines()
    parsed = [(semver(t), t) for t in tags]
    parsed = [(v, t) for v, t in parsed if v is not None]
    if not parsed:
        raise SystemExit("release-plan failed: no vX.Y.Z release tags found")
    return max(parsed, key=lambda item: item[0])[1]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--skill", required=True, type=pathlib.Path)
    ap.add_argument("--out", type=pathlib.Path)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    skill = args.skill.resolve()
    baseline = latest_tag(skill)
    major, minor, patch = semver(baseline) or (0, 0, 0)
    candidate = f"v{major}.{minor}.{patch + 1}"
    payload = {
        "baseline_ref": baseline,
        "baseline_sha": run(["git", "rev-parse", baseline], cwd=skill),
        "candidate_version": candidate,
        "planned_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")
    if args.json or not args.out:
        print(json.dumps(payload, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
