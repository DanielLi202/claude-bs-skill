#!/usr/bin/env python3
"""Append/update local bs-evolve fleet under SKILL.lock."""
from __future__ import annotations

import argparse
import pathlib
from datetime import datetime, timezone

import yaml


def now_z() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--fleet", required=True, type=pathlib.Path)
    ap.add_argument("--slug", required=True)
    ap.add_argument("--target", required=True)
    ap.add_argument("--config", required=True)
    args = ap.parse_args()
    path = args.fleet
    path.parent.mkdir(parents=True, exist_ok=True)
    data = yaml.safe_load(path.read_text(encoding="utf-8")) if path.exists() else {}
    if not isinstance(data, dict):
        data = {}
    projects = data.setdefault("projects", {})
    projects[args.slug] = {"target_repo": args.target, "config": args.config, "updated_at": now_z()}
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(yaml.safe_dump(data, sort_keys=True), encoding="utf-8")
    tmp.replace(path)
    print(f"fleet updated: {args.slug}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
