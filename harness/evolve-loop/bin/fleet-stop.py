#!/usr/bin/env python3
"""Create STOP tombstones for all or selected projects in a local fleet."""
from __future__ import annotations

import argparse
import pathlib

import yaml


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--fleet", required=True, type=pathlib.Path)
    ap.add_argument("--slug", action="append")
    args = ap.parse_args()
    data = yaml.safe_load(args.fleet.read_text(encoding="utf-8")) if args.fleet.exists() else {}
    projects = (data or {}).get("projects") or {}
    wanted = set(args.slug or projects.keys())
    stopped = []
    for slug, row in projects.items():
        if slug not in wanted:
            continue
        config = pathlib.Path(row["config"]).resolve()
        stop = config.parent / "STOP"
        stop.parent.mkdir(parents=True, exist_ok=True)
        stop.write_text("stopped by fleet-stop\n", encoding="utf-8")
        stopped.append(slug)
    print("stopped: " + ",".join(sorted(stopped)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
